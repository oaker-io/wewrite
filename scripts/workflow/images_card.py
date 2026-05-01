#!/usr/bin/env python3
"""images_card.py · wewrite 接 image-card-engine 的最简入口。

跟 images.py(老路径 · LLM 自由写 prompt · claude -p)平行。
- 老路径 images.py 不动 · 7 plist 默认仍跑老路径
- 新路径 images_card.py 让用户显式跑 · 验证 0 钱 HTML 信息卡 / 模板填空

用法:
  python3 scripts/workflow/images_card.py --engine html         # 0 钱 · 公众号信息卡
  python3 scripts/workflow/images_card.py --engine image-model  # nano-banana-2 · 模板填空
  python3 scripts/workflow/images_card.py --vibe data            # auto_decision 选 engine
  python3 scripts/workflow/images_card.py --tier premium         # 主力贴文 · gpt-image-2 1/day

设计:
- 不改 wewrite write.py(LLM 写作不变)
- 不改 wewrite images.py(老路径保留)
- 仅作为 demo 入口 · 让 wewrite 用上新双 skill
- 后续 W4 反馈调优后 · 再决定是否替换主流程
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import _state  # noqa: E402

# image_card_client / cost_tracker · 通过 wewrite/lib/ 的 symlink import
from lib.image_card_client import render_card, auto_decision  # noqa: E402
from lib.cost_tracker import log_html, log_image, summary  # noqa: E402


def _extract_title(md_path: Path) -> str:
    """从 article_md 第一行 # H1 提标题。"""
    try:
        for line in md_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()[:20]
    except OSError:
        pass
    return "公众号头条"


def _build_spec_from_md(
    md_path: Path,
    *,
    engine: str,
    tier: str,
    style_pack: str,
    theme: str,
    n_pages: int = 1,
) -> dict:
    """从 article_md 抽 title 后构造最简 spec。

    V0 只出 cover + 可选 1-2 张内页(numbered_list)
    完整 spec 由 LLM 在 write.py 阶段输出 IMAGE_PLAN 块(W4 改造)。
    """
    title = _extract_title(md_path)
    slug = md_path.stem

    # cover 一定有
    pages: list[dict] = []
    if engine == "html":
        # xhs-card 模板:cover / steps / data_card / summary
        pages.append({
            "template": "cover",
            "fields": {
                "tag": "公众号头条",
                "title_main": title,
                "title_sub": "wewrite × image-card",
                "anchor_glyph": "★",
                "kicker": "wewrite",
            },
        })
    else:
        # image-card-engine cover_hero
        pages.append({
            "template_id": "cover_hero",
            "fields": {
                "title_main": title,
                "title_sub": f"wewrite × image-card · {tier}",
                "hero_visual": "公众号头条 · 中央 logo + 数据条 · 莫兰迪知识博主调性",
                "badge": "WEWRITE",
                "chinese_labels": [title, "wewrite × image-card", "WEWRITE"],
            },
            "use_cover_as_ref": False,
        })

    # spec 整体
    if engine == "html":
        return {
            "slug": slug,
            "engine": "html",
            "platform": "gzh",
            "theme": theme,
            "author": "@wewrite",
            "pages": pages,
        }
    return {
        "slug": slug,
        "engine": "image-model",
        "platform": "gzh",
        "tier": tier,
        "style_pack": style_pack,
        "author": "@wewrite",
        "pages": pages,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--engine", choices=("html", "image-model", "auto"), default="auto",
                   help="auto = 调 auto_decision 自动决策")
    p.add_argument("--tier", choices=("premium", "standard", "html"), default=None,
                   help="image-model 时用 · premium=主力 1/day · standard=不限")
    p.add_argument("--vibe", default="data",
                   help="主题 vibe · auto 时用(data/cute/vintage/major_announce)")
    p.add_argument("--style-pack", default="morandi-knowledge",
                   help="image-model 时的 style_pack")
    p.add_argument("--theme", default="xhs-insight-news",
                   help="html 时的 theme")
    p.add_argument("--md", default=None, help="覆盖 session 的 article_md")
    p.add_argument("--output", default=None, help="输出目录(default: output/images-card/)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    # 找 md
    if args.md:
        md_path = Path(args.md)
    else:
        s = _state.load()
        article_md = s.get("article_md")
        if not article_md:
            print("❌ session 无 article_md · 先跑 write.py 或 --md 显式指定", file=sys.stderr)
            return 1
        md_path = ROOT / article_md

    if not md_path.exists():
        print(f"❌ {md_path} 不存在", file=sys.stderr)
        return 1

    # auto 决策
    if args.engine == "auto":
        decision = auto_decision(args.vibe, "gzh", is_main_post=(args.tier == "premium"))
        engine = decision["engine"]
        tier = args.tier or decision.get("tier", "standard")
        style_pack = decision.get("style_pack", args.style_pack)
        theme = decision.get("theme", args.theme)
        print(f"[images_card] auto · vibe={args.vibe} → {decision}")
    else:
        engine = args.engine
        tier = args.tier or ("html" if engine == "html" else "standard")
        style_pack = args.style_pack
        theme = args.theme

    # 构 spec
    spec = _build_spec_from_md(md_path, engine=engine, tier=tier,
                                style_pack=style_pack, theme=theme)
    print(f"[images_card] spec.slug={spec['slug']} · engine={engine} · "
          f"{'theme=' + theme if engine == 'html' else 'tier=' + tier + ' style=' + style_pack}")

    output_dir = Path(args.output) if args.output else (ROOT / "output" / "images-card")
    try:
        pngs = render_card(spec, output_dir, platform="gzh", dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ render failed: {e}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"[images_card] dry-run · 0 张盘 · prompt 已 dump 到 {output_dir}")
    else:
        print(f"[images_card] ✓ {len(pngs)} 张 · {output_dir}")

    # cost summary
    if not args.dry_run:
        s = summary(days=1)
        print(f"[images_card] 💰 today: ${s['total']} · {s['by_kind']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
