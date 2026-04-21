#!/usr/bin/env python3
"""Workflow 2 · 写作 write
读 session 的 selected_idx · 调 claude -p 跑 Step 3-5(框架+素材+写作)。
输出到 output/YYYY-MM-DD-slug.md · push 全文到手机等用户审。

用法:
  python3 scripts/workflow/write.py 0           # 选 session Top N 里的第 1 条
  python3 scripts/workflow/write.py --idea "Cursor 2.0 冲击 Claude Code"  # 自定义 idea · 绕开 brief
"""
from __future__ import annotations
import os, re, subprocess, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state
import _idea_bank

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def slugify(title, maxlen=40):
    """从中文标题提取关键词 slug(简单版 · 保留字母数字 + 连字符)"""
    # Extract English/numbers from title
    eng = re.findall(r"[A-Za-z0-9]+", title)
    if eng:
        s = "-".join(eng[:5]).lower()
    else:
        # Fallback: hash prefix + timestamp
        import hashlib
        s = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
    return s[:maxlen]


_COMMON_TAIL_RULES = (
    "**通用必守**:\n"
    "- **不要写 H1**(WeChat 草稿箱标题由 publish 单独传入,H1 会重复)\n"
    "- 第一行直接写 `![](images/cover.png)`(alt **必须留空**,否则会渲染出「封面」二字)\n"
    "- 文末**压轴必须**放一张完整的「智辰老师」介绍卡(含嵌入公众号关注卡视觉),格式:\n"
    "  ```\n"
    "  :::author-card\n"
    "  name: 智辰老师\n"
    "  tagline: 独立开发者 · AI 非共识观察者 · openclaw 武汉创业群群主\n"
    "  bio: <根据本文主题自然带出 1-2 句 · 含「AI 非共识,掘金看智辰」口号>\n"
    "  mp_brand: 宸的 AI 掘金笔记\n"
    "  mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。\n"
    "  mp_meta: 关注获取每日 AI 非共识 · 掘金看智辰\n"
    "  tags: [AI 非共识, <2-3 个本文相关标签>]\n"
    "  footer: 扫码加我微信备注「<本文相关关键词>」· 我会拉你进读者群\n"
    "  :::\n"
    "  ```\n"
    "  `mp_brand/mp_desc/mp_meta` 三字段会渲染成嵌入式公众号关注卡视觉。\n"
    "- author-card **下方**仍要带:两个二维码 `![](images/qr-zhichen.png)` 和 `![](images/qr-openclaw.png)` + aipickgold.com 安利段\n"
    "- 写完返回一行:'DONE {absolute_path}'\n"
    "- 即便忘了上述 · publish 阶段会兜底 sanitize · 但写对省一道清理。\n\n"
    "作者身份:style.yaml 的 author/brand 字段 · 口号「AI 非共识,掘金看智辰」"
)


def _build_prompt_hotspot(topic, out_path: Path) -> str:
    """热点观察 / 非共识解读 prompt(原 prompt)。"""
    return (
        "请使用 wewrite skill 写一篇微信公众号文章(**热点系列 · 非共识解读**),主题:\n\n"
        f"**{topic['title']}**\n(来源:{topic['source']} · 热度 {topic['hot']:.0f})\n\n"
        "**系列定位**:这篇属于「热点观察 / AI 非共识」系列。\n"
        "选用 `references/frameworks.md` 里的框架(痛点型/故事型/观点型/盘点型/对比型)。\n"
        "persona 推荐:`midnight-friend` / `industry-observer` / `sharp-journalist`。\n\n"
        "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **1800-2500 字** · 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "4. 按需插入内文 chart 占位符 `![](images/chart-1.png)` ... `chart-4.png`\n"
        "   配图 layout 推荐(信息密度型):dense-modules / dashboard / story-mountain / bento-grid / comparison-matrix\n\n"
        + _COMMON_TAIL_RULES
    )


def _build_prompt_tutorial(topic, out_path: Path) -> str:
    """干货 / 教程 / 方法论 prompt(2026-04-21 加 · 新系列入口)。"""
    return (
        "请使用 wewrite skill 写一篇微信公众号文章(**干货系列 · 教程方法论**),主题:\n\n"
        f"**{topic['title']}**\n\n"
        "**系列定位**:这篇属于「干货 / 教程 / 方法论」系列 · **不是热点观察**。\n"
        "选用 `references/tutorial-frameworks.md` 里的框架(T1 步骤教程 / T2 工具评测 / T3 方法论沉淀 / T4 知识科普 / T5 避坑清单),\n"
        "**默认用 T1 步骤教程型**(80% 干货文用这个),除非主题明显更适合其他。\n\n"
        "**写作 persona 用 `tutorial-instructor`**(教程讲师 · 步骤明确 · 操作性强 · 见 `personas/tutorial-instructor.yaml`)。\n\n"
        "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **2500-4500 字**(教程通常需要更长结构 · 步骤要展开)\n"
        "4. **结构必须步骤化**:每个核心步骤独立 H2 · 推荐格式「Step N: 一句话目标」\n"
        "5. 每步带四要素:【目标】→【操作】→【验证】→【常见坑】(可适度合并)\n"
        "6. 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "7. 按需插入内文 chart 占位符 `![](images/chart-1.png)` ... `chart-4.png`\n"
        "   配图 layout 推荐(操作流程型):\n"
        "   - **linear-progression**(★★★★★ 步骤流程 / SOP)\n"
        "   - **comparison-matrix**(★★★★★ 工具横评 / before-after)\n"
        "   - **hierarchical-layers**(★★★★★ 知识体系 / 三层递进)\n"
        "   - funnel(筛选决策)/ tree-branching(选择决策树)/ circular-flow(运行机制)\n"
        "   - 封面优先用 `bento-grid`(N 个要点速览)+ `ikea-manual` style(说明书风格)\n"
        "8. **避免热点系列的非共识口吻**:不要用「真相是」「其实没人告诉你」这种钩子;\n"
        "   要用「读完你能做到 X」「跟着我走一遍」这种承诺式钩子。\n"
        "9. 标题倾向(选一种):\n"
        "   - 「手把手:N 分钟用 X 做到 Y」\n"
        "   - 「X 的 N 个官方文档没说的细节」\n"
        "   - 「我用 X 半年总结的 N 个坑」\n"
        "   - 「从 0 到 1 配置 X 的完整 SOP」\n\n"
        + _COMMON_TAIL_RULES
    )


def run_claude_write(topic, date_str, out_path: Path, style: str = "hotspot"):
    """调 claude -p 让 WeWrite skill 跑 Step 3-5 · 只写文章不生图不发布。

    style:
      - "hotspot"  : 热点观察 / 非共识解读(默认 · 走 frameworks.md)
      - "tutorial" : 干货 / 教程 / 方法论(走 tutorial-frameworks.md + tutorial-instructor)
    """
    if style == "tutorial":
        prompt = _build_prompt_tutorial(topic, out_path)
        print(f"→ claude -p writing [TUTORIAL]... (可能 5-12 分钟 · 教程文较长)")
    else:
        prompt = _build_prompt_hotspot(topic, out_path)
        print(f"→ claude -p writing [HOTSPOT]... (可能 3-8 分钟)")

    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-500:]}")
    return r.stdout


def push_article(md_path: Path, topic, style: str = "hotspot"):
    """Push markdown preview to Discord · 分块(Discord 1900 char 上限)。"""
    md = md_path.read_text(encoding="utf-8")
    word_count = len(md)
    style_tag = "🛠️ 干货系列" if style == "tutorial" else "🔥 热点系列"

    # Header message
    header = (
        f"📝 **文章初稿就绪 · {word_count} 字** · {style_tag}\n"
        f"📌 选题:{topic['title']}\n"
        f"📂 路径:`{md_path.relative_to(ROOT)}`\n"
        f"---\n"
        f"下面推送**预览首段 + 末段 + 目录**。完整正文 Mac 本地查看 `open {md_path}`。\n"
        f"回复 `ok` / `继续` 进入生图 · `改 XX` 编辑 · `重写` 换角度 · `pass` 放弃本篇。"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", header],
        check=True, timeout=60,
    )

    # Preview excerpt
    lines = md.splitlines()
    h2_outline = [l for l in lines if l.startswith("## ")][:8]
    first_para = next((l for l in lines if l and not l.startswith(("#", "!", "<"))), "")
    last_para = ""
    for l in reversed(lines):
        if l and not l.startswith(("#", "!", "<", ":", "-", ">", "|")):
            last_para = l
            break

    excerpt = (
        f"**📑 目录(H2)**\n" + "\n".join(h2_outline) + "\n\n"
        f"**✏️ 开头:**\n{first_para[:400]}{'...' if len(first_para) > 400 else ''}\n\n"
        f"**🎬 结尾:**\n{last_para[:300]}{'...' if len(last_para) > 300 else ''}"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", excerpt],
        check=True, timeout=60,
    )


def _parse_argv():
    """解析命令行 · 返回 (argv_idx, custom_idea, style)。

    支持:
      python3 write.py 0                                     · idx
      python3 write.py --idea "<标题>"                        · 自定义 idea
      python3 write.py 0 --style tutorial                    · idx + style
      python3 write.py --idea "<标题>" --style tutorial       · idea + style
      python3 write.py --style tutorial --idea "<标题>"       · 顺序无关
    """
    args = sys.argv[1:]
    style = "hotspot"
    argv_idx = None
    custom_idea = None

    # 先抽 --style(无序)
    if "--style" in args:
        i = args.index("--style")
        if i + 1 >= len(args):
            print("❌ --style 需跟值: hotspot | tutorial", file=sys.stderr); sys.exit(1)
        style = args[i + 1]
        if style not in ("hotspot", "tutorial"):
            print(f"❌ --style 只能是 hotspot 或 tutorial · 收到 {style!r}", file=sys.stderr); sys.exit(1)
        args = args[:i] + args[i + 2:]

    # 再判 --idea / idx
    if args:
        if args[0] == "--idea":
            if len(args) < 2:
                print("❌ --idea 需要跟一个 idea 字符串", file=sys.stderr); sys.exit(1)
            custom_idea = " ".join(args[1:]).strip()
            if not custom_idea:
                print("❌ idea 不能为空", file=sys.stderr); sys.exit(1)
        else:
            try:
                argv_idx = int(args[0])
            except ValueError:
                print(f"❌ 首参数要么 idx (0-based) 要么 --idea '...'", file=sys.stderr); sys.exit(1)

    return argv_idx, custom_idea, style


def _auto_style_from_topic(topic: dict, cli_style: str) -> str:
    """阶段 D · idx 模式下根据 topic 来源 / category 推断 style。

    规则:
      - from == "hotspot"   → 用 cli_style(默认 hotspot)
      - from == "idea":
          category == "tutorial"  → 强制 tutorial
          category == "hotspot"   → 强制 hotspot
          category == "flexible"  → 用 cli_style
      - 缺字段(老 session 兼容)→ 用 cli_style
    """
    src = topic.get("from")
    if src == "idea":
        cat = topic.get("category", "flexible")
        if cat == "tutorial":
            return "tutorial"
        if cat == "hotspot":
            return "hotspot"
        return cli_style
    return cli_style


def main():
    argv_idx, custom_idea, cli_style = _parse_argv()
    style = cli_style  # 默认 = 命令行 · 走 idx 路径时可能被 idea category 覆盖
    idea_id_to_mark = None  # 写完成功后调 mark_used 的 id

    if custom_idea:
        # 构造一个虚拟 topic · 绕过 brief 状态检查
        topic = {
            "title": custom_idea,
            "source": "用户 idea",
            "hot": 0,
            "score": 100,
            "ai_kw": "custom",
            "url": "",
        }
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = slugify(custom_idea)
        out_path = ROOT / "output" / f"{date_str}-{slug}.md"
        _state.advance(
            "writing",
            selected_idx=-1, selected_topic=topic,
            article_md=str(out_path.relative_to(ROOT)),
        )
    else:
        s = _state.load()
        if s["state"] != _state.STATE_BRIEFED and argv_idx is None:
            print(f"❌ state={s['state']} · 先跑 brief 选 Top 3", file=sys.stderr); sys.exit(1)

        topics = s.get("topics") or []
        if not topics:
            print("❌ session 无 topics,先 brief", file=sys.stderr); sys.exit(1)

        idx = argv_idx if argv_idx is not None else (s.get("selected_idx") or 0)
        if idx < 0 or idx >= len(topics):
            print(f"❌ idx {idx} out of range(0-{len(topics)-1})", file=sys.stderr); sys.exit(1)

        topic = topics[idx]
        date_str = s.get("article_date") or datetime.now().strftime("%Y-%m-%d")
        slug = slugify(topic["title"])
        out_path = ROOT / "output" / f"{date_str}-{slug}.md"

        # 阶段 D · 按 from/category 自动推断 style · 记 idea_id 等写完后标 used
        style = _auto_style_from_topic(topic, cli_style)
        if topic.get("from") == "idea" and topic.get("idea_id") is not None:
            idea_id_to_mark = topic.get("idea_id")

        _state.advance(
            "writing",
            selected_idx=idx, selected_topic=topic,
            article_md=str(out_path.relative_to(ROOT)),
        )

    try:
        run_claude_write(topic, date_str, out_path, style=style)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    if not out_path.exists():
        print(f"❌ claude 跑完但 {out_path} 不存在 · 看 claude stdout 排查", file=sys.stderr)
        sys.exit(3)

    _state.advance(_state.STATE_WROTE, article_md=str(out_path.relative_to(ROOT)),
                   style=style)

    # 阶段 D · idea 库选题写完 · 自动标 used
    src_tag = ""
    if idea_id_to_mark is not None:
        try:
            _idea_bank.mark_used(
                idea_id_to_mark,
                article_md=str(out_path.relative_to(ROOT)),
            )
            src_tag = f" · from idea #{idea_id_to_mark}"
        except Exception as e:
            print(f"⚠ mark_used idea #{idea_id_to_mark} 失败: {e}", file=sys.stderr)

    push_article(out_path, topic, style=style)
    print(f"✓ wrote [{style}{src_tag}] · {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
