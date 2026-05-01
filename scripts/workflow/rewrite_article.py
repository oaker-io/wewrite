"""rewrite_article.py · 给 sources(Twitter packages) + idea title · LLM 洗稿成 markdown。

核心设计:
  - 不让 LLM 从 0 编 · 全程基于真实素材(原帖文字 + 真实图片)
  - 智辰 IP voice(工程派 + 反共识 + 哈工大背景 + 半导体 6 年)
  - 7 大主题守门(必命中 1 个 · 拒新闻资讯)
  - humanize 14 条(反 AI 检测)
  - 引用图:必须用 source_fetcher 下载的 local_path(不靠 LLM 自己生)
  - 必须有 ≥ 1 处反共识 take(避免变成纯复述)

输出:
  output/{date}-{slug}.md
  含 cover-square 不在此模块 · 走主链 publish.py 时再生成
  (cover 用第一张原图居中裁 · 见 fetch 后 caller 处理)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
sys.path.insert(0, str(ROOT))  # for lib/

from lib import llm_service  # noqa: E402 · 统一接 cpa.gateway


SYSTEM_PROMPT = """你是「智辰 / 宸的 AI 掘金笔记」公众号作者智辰。

人设:哈工大本硕 + 6 年半导体工艺工程师 → 转 AI 创业实战派。
读者:AI 一线工程师 + AI 副业从业者 + AI 创业者。

写作 7 大主题(必命中 ≥1 · 越界等于废稿):
  1. AI 干货 — know-how / 框架 / 模板
  2. AI 教程 — step-by-step
  3. AI 赚钱 — 副业 / 变现 / 月入 / ROI
  4. AI 创业 — 0→1 / SaaS / Indie
  5. AI 真实测评 — 实测 / 横评 / 数据
  6. AI 踩坑 — 翻车 / 教训 / 复盘
  7. AI 感悟 — 反共识 / 长期视角

🚫 严禁:
  - 写新闻播报(「刚刚 X 发布」「重磅速看」「X 大新功能」)
  - 直接复述原文 · 必须改写改组织
  - 写「AI 让生活更美好」式空 hype
  - 政治 / 币圈 / 同行八卦 / 个人感情 / 写作鸡汤(粥左罗式)

✅ 必做(humanize 14 条 · 反 AI 检测):
  1. 句长方差 — 短句 + 长句穿插 · 不要全长句
  2. 禁用「首先 / 其次 / 总而言之 / 综上所述」连接词
  3. 真实数字带波动:不写「100 元」写「80-200 元」/「3000 多块」
  4. 1-3 处地点-时间-人名锚点(「我朋友 4/16 凌晨打来电话」)
  5. 段落不均 — 1 段 1 行也允许 · 不要全 5 行段
  6. emoji 少(全文 ≤ 2 个 · 或 0 个)
  7. 偶尔自我怀疑句(「我也不确定」「这个观察可能片面」)
  8. 段尾偶尔不完整 · 留半句
  9. 反共识开头 — 第 1-3 段必有 1 处反主流 take
  10. 技术术语口语化 · 避免「上下文窗口」全用「能记住多少字」
  11. 失败 / 踩坑披露(必有 ≥ 1 处「我自己翻车」)
  12. 无意义短句允许(「就这样。」「真的。」)
  13. 用真实工具品牌名(「我用 Cursor + Claude Code」 不写「某 AI 工具」)
  14. 文末固定 IP 落款:智辰 / 宸的 AI 掘金笔记 / AI 红利,看智辰

格式要求:
  - 1500-2500 字
  - 每张原图必须用上(放在最贴主题段落)· 用 markdown:`![desc](path)`
  - 不写 H1 标题(微信草稿自带 · 写 H1 会重复)· 直接正文
  - 用 `## 场景 N` `## 反共识 take` 这类小标题
  - 文末加:`::: author-card\n:::` 这一行(自动展开作者卡)
"""

USER_PROMPT_TEMPLATE = """选题:{idea_title}

下面是 Twitter / X 上的真实素材(原帖文字 + 原图本地路径)· 请你基于这些洗稿出 1 篇文章。

──── 素材 ────
{sources_block}

──── 任务 ────
1. 洗稿(不是复述)· 智辰 voice + humanize 14 条
2. **必须用上每一张原图**(共 {n_images} 张)· 用 markdown 引用
3. **图片路径硬规则:严格使用素材里给出的 `local_path` 字段值 · 但去掉 `output/` 前缀**
   - 例:素材 `local_path` 是 `output/images/abc/source_1.jpg`
   - md 里写 `![描述](images/abc/source_1.jpg)`
   - **绝对不要**自己编 slug 名 · 必须用素材里给的精确路径
4. 必须有 ≥ 1 处反共识 take(可以放开头或正文中段)
5. 命中 7 大主题之一 · 不要写新闻播报
6. 文末固定:智辰 IP 落款 + author-card 容器(`::: author-card\\n:::`)

直接给我 markdown 输出 · 不要 ```markdown 代码块包裹 · 不要解释 · 不要前后说明。
"""


def _format_sources(packages: list[dict]) -> tuple[str, int]:
    """packages → 给 LLM 看的素材 markdown · 同时返图片总数。"""
    parts: list[str] = []
    n_images = 0
    for i, p in enumerate(packages, 1):
        if not p.get("ok"):
            parts.append(f"### Source {i}(失败 · 跳过)\n")
            continue
        author = p.get("author") or {}
        parts.append(f"### Source {i} · @{author.get('screen_name','?')}({author.get('name','')})")
        parts.append(f"URL: {p.get('url','')}")
        parts.append(f"赞数: {p.get('favorite_count', 0)}")
        parts.append(f"原文:\n{p.get('text','')}")
        if p.get("images"):
            parts.append(f"\n图片({len(p['images'])} 张):")
            for j, img in enumerate(p["images"], 1):
                parts.append(f"  - `{img['local_path']}` ({img.get('width','?')}×{img.get('height','?')})")
                n_images += 1
        if p.get("quoted"):
            qt = p["quoted"]
            parts.append(f"\nQuoted Tweet @{qt.get('author',{}).get('screen_name','?')}:")
            parts.append(f"  {qt.get('text','')}")
            for j, img in enumerate(qt.get("images") or [], 1):
                parts.append(f"  · `{img['local_path']}` ({img.get('width','?')}×{img.get('height','?')})")
                n_images += 1
        if p.get("article"):
            art = p["article"]
            parts.append(f"\nX 长文(只有摘要):")
            parts.append(f"  标题: {art.get('title','')}")
            parts.append(f"  预览: {art.get('preview_text','')}")
            if art.get("cover_local_path"):
                parts.append(f"  封面图: `{art['cover_local_path']}`")
                n_images += 1
        parts.append("")
    return "\n".join(parts), n_images


def rewrite(idea_title: str, packages: list[dict], *,
            slug: str | None = None,
            kind: str = "L1_creative") -> str:
    """主洗稿入口 · 返回 markdown 字符串。

    走 cpa.gateway(L1_creative)· primary claude-max · fallback poe-api(claude-sonnet-4.6)。
    """
    if not packages:
        raise ValueError("packages 为空 · 没素材怎么洗")

    sources_block, n_images = _format_sources(packages)
    if not slug:
        slug = date.today().isoformat() + "-rewrite"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        idea_title=idea_title,
        sources_block=sources_block,
        n_images=n_images,
        slug=slug,
    )

    print(f"→ 调 cpa.gateway kind={kind} · 素材 {len(packages)} 个 · 图 {n_images} 张")
    md = llm_service.generate_text(
        prompt=user_prompt,
        system=SYSTEM_PROMPT,
        kind=kind,
    )
    md = (md or "").strip()
    # 去掉可能的 ``` 包裹
    md = re.sub(r"^```(?:markdown|md)?\s*\n", "", md, count=1)
    md = re.sub(r"\n```\s*$", "", md, count=1)
    # 兜底:LLM 偶尔会把 slug 写错(用 article slug 而不是 source slug)
    # 收集 packages 里所有 local_path 的真实文件名 · 校正 md 里的引用
    md = _fix_image_paths(md, packages)
    return md


def _fix_image_paths(md: str, packages: list[dict]) -> str:
    """LLM 偶尔把图路径写错(slug 错位)· 用 packages 真实 local_path 校正。

    策略:从 packages 抽所有 (basename, real_path) · md 里 ![](xxx/{basename}) 全替换。
    """
    # 收集所有真实 local_path
    real_by_basename: dict[str, str] = {}
    for p in packages:
        if not p.get("ok"):
            continue
        for img in p.get("images") or []:
            lp = img.get("local_path", "")
            if lp:
                base = Path(lp).name
                real_by_basename[base] = lp.removeprefix("output/")
        if p.get("quoted"):
            for img in p["quoted"].get("images") or []:
                lp = img.get("local_path", "")
                if lp:
                    real_by_basename[Path(lp).name] = lp.removeprefix("output/")
        if p.get("article") and p["article"].get("cover_local_path"):
            lp = p["article"]["cover_local_path"]
            real_by_basename[Path(lp).name] = lp.removeprefix("output/")

    if not real_by_basename:
        return md

    def _sub(m: re.Match) -> str:
        alt, path = m.group(1), m.group(2)
        base = Path(path).name
        if base in real_by_basename:
            return f"![{alt}]({real_by_basename[base]})"
        return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _sub, md)


def save_article(md: str, *, slug: str | None = None,
                 out_dir: Path | None = None) -> Path:
    """存 md 到 output/{date}-{slug}.md。"""
    out_dir = out_dir or (ROOT / "output")
    today = date.today().isoformat()
    fname = f"{today}-{slug or 'rewrite'}.md"
    dst = out_dir / fname
    dst.write_text(md, encoding="utf-8")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea-title", required=True, help="选题标题(idea_bank 里的)")
    ap.add_argument("--sources-json", required=True,
                    help="source_fetcher --json-out 输出的文件 · 含 packages 数组")
    ap.add_argument("--slug", default=None, help="output md 文件 slug · 默认日期")
    ap.add_argument("--kind", default="L1_creative",
                    help="cpa kind (L1_creative / L0_critical / L3_summarize 等)")
    ap.add_argument("--dry-run", action="store_true",
                    help="只 print prompt · 不调 LLM")
    args = ap.parse_args()

    pkgs = json.loads(Path(args.sources_json).read_text(encoding="utf-8"))
    if not isinstance(pkgs, list):
        print("⚠ sources-json 必须是 list 形态")
        return 1

    if args.dry_run:
        block, n = _format_sources(pkgs)
        print("=== source block ===")
        print(block)
        print(f"\nimages total: {n}")
        return 0

    md = rewrite(args.idea_title, pkgs, slug=args.slug, kind=args.kind)
    dst = save_article(md, slug=args.slug)
    print(f"\n✓ {dst.relative_to(ROOT)}({len(md)} 字)")
    print()
    print(md[:600] + "\n...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
