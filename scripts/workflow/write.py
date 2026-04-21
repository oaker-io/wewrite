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


def run_claude_write(topic, date_str, out_path: Path):
    """调 claude -p 让 WeWrite skill 跑 Step 3-5 · 只写文章不生图不发布。"""
    prompt = (
        "请使用 wewrite skill 写一篇微信公众号文章,主题是:\n\n"
        f"**{topic['title']}**\n(来源:{topic['source']} · 热度 {topic['hot']:.0f})\n\n"
        "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. **不要写 H1**(WeChat 草稿箱标题由 publish 单独传入,H1 会重复)\n"
        "4. 第一行直接写 `![](images/cover.png)`(alt **必须留空**,否则会渲染出"封面"二字)\n"
        "5. 正文 1800-2500 字 · 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "6. 按需插入内文 chart 占位符 `![](images/chart-1.png)` ... `chart-4.png`\n"
        "7. 文末**压轴必须**放一张完整的「智辰老师」介绍卡(含嵌入公众号关注卡视觉),格式:\n"
        "   ```\n"
        "   :::author-card\n"
        "   name: 智辰老师\n"
        "   tagline: 独立开发者 · AI 非共识观察者 · openclaw 武汉创业群群主\n"
        "   bio: <根据本文主题自然带出 1-2 句 · 含「AI 非共识,掘金看智辰」口号>\n"
        "   mp_brand: 宸的 AI 掘金笔记\n"
        "   mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。\n"
        "   mp_meta: 关注获取每日 AI 非共识 · 掘金看智辰\n"
        "   tags: [AI 非共识, <2-3 个本文相关标签>]\n"
        "   footer: 扫码加我微信备注「<本文相关关键词>」· 我会拉你进读者群\n"
        "   :::\n"
        "   ```\n"
        "   `mp_brand/mp_desc/mp_meta` 三个字段会渲染成嵌入式公众号关注卡视觉(模仿 WeChat 官方 widget)。\n"
        "8. author-card **下方**仍要带:两个二维码 `![](images/qr-zhichen.png)` 和 `![](images/qr-openclaw.png)` + aipickgold.com 安利段\n"
        "9. 写完返回一行:'DONE {absolute_path}'\n\n"
        "作者身份:style.yaml 的 author/brand 字段 · 口号「AI 非共识,掘金看智辰」\n"
        "注:即便忘了 #3/#4/#7,publish 阶段会兜底 sanitize · 但写对省一道清理。"
    )

    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    print(f"→ claude -p writing... (可能 3-8 分钟)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-500:]}")
    return r.stdout


def push_article(md_path: Path, topic):
    """Push markdown preview to Discord · 分块(Discord 1900 char 上限)."""
    md = md_path.read_text(encoding="utf-8")
    word_count = len(md)

    # Header message
    header = (
        f"📝 **文章初稿就绪 · {word_count} 字**\n"
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


def main():
    # 两种模式:
    #   python3 write.py 0                    · 按 session Top N 里的 idx
    #   python3 write.py --idea "<自定义标题>" · 绕过 brief · 直接用这个 idea 写
    argv_idx = None
    custom_idea = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--idea":
            if len(sys.argv) < 3:
                print("❌ --idea 需要跟一个 idea 字符串", file=sys.stderr); sys.exit(1)
            custom_idea = " ".join(sys.argv[2:]).strip()
            if not custom_idea:
                print("❌ idea 不能为空", file=sys.stderr); sys.exit(1)
        else:
            try:
                argv_idx = int(sys.argv[1])
            except ValueError:
                print(f"❌ 首参数要么 idx (0-based) 要么 --idea '...'", file=sys.stderr); sys.exit(1)

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

        _state.advance(
            "writing",
            selected_idx=idx, selected_topic=topic,
            article_md=str(out_path.relative_to(ROOT)),
        )

    try:
        run_claude_write(topic, date_str, out_path)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    if not out_path.exists():
        print(f"❌ claude 跑完但 {out_path} 不存在 · 看 claude stdout 排查", file=sys.stderr)
        sys.exit(3)

    _state.advance(_state.STATE_WROTE, article_md=str(out_path.relative_to(ROOT)))
    push_article(out_path, topic)
    print(f"✓ wrote · {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
