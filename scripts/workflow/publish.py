#!/usr/bin/env python3
"""Workflow 4 · 推草稿 publish
读 session · 调 cli.py publish · push 草稿链接 + 提醒手动加公众号卡片。

用法: python3 scripts/workflow/publish.py
"""
from __future__ import annotations
import os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
CLI = ROOT / "toolkit" / "cli.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def run_publish(md_path: str, cover: str, title: str, engine="md2wx", theme="focus-navy"):
    env = os.environ.copy()
    keys = ROOT / "secrets" / "keys.env"
    if keys.exists():
        for line in keys.read_text().splitlines():
            m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"]*)"?\s*$', line)
            if m:
                env[m.group(1)] = m.group(2)

    args = [
        str(PY), str(CLI), "publish", md_path,
        "--engine", engine, "--theme", theme,
        "--cover", cover, "--title", title,
    ]
    print(f"→ cli.py publish ...")
    r = subprocess.run(args, cwd=str(ROOT), env=env,
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"publish failed:\n{r.stdout[-500:]}\n{r.stderr[-500:]}")
    m = re.search(r"Draft created[!]?\s+media_id:\s*(\S+)", r.stdout)
    if not m:
        m = re.search(r"media_id:\s*(\S{30,})", r.stdout)
    return m.group(1) if m else "?", r.stdout


def push_done(media_id: str, title: str):
    text = (
        f"🚀 **草稿已推送到微信草稿箱**\n"
        f"📝 {title}\n"
        f"🆔 `{media_id}`\n\n"
        f"---\n"
        f"**⚠️ 最后一步**(2 分钟手机也能做):\n"
        f"1. `mp.weixin.qq.com` → 草稿箱 → 找最新这篇\n"
        f"2. 「编辑」\n"
        f"3. author-card 和二维码之间,工具栏「资源引用」→「公众号」→ 选 **宸的 AI 掘金笔记**\n"
        f"4. 通读 → 发表\n\n"
        f"下一篇可回 `brief` 触发选题 · 或等明早 08:30 自动 brief。"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", text],
        check=True, timeout=60,
    )


def main():
    s = _state.load()
    if s["state"] != _state.STATE_IMAGED:
        print(f"❌ state={s['state']} · 要先 write → images", file=sys.stderr); sys.exit(1)

    article_md = s.get("article_md")
    topic = s.get("selected_topic") or {}
    if not article_md:
        print("❌ 无 article_md", file=sys.stderr); sys.exit(1)

    cover = ROOT / "output" / "images" / "cover.png"
    if not cover.exists():
        print("❌ cover.png 不存在", file=sys.stderr); sys.exit(1)

    title = (topic.get("title") or "")[:60] or "(untitled)"

    media_id, _out = run_publish(
        md_path=article_md,
        cover=str(cover.relative_to(ROOT)),
        title=title,
    )
    _state.advance(_state.STATE_DONE, draft_media_id=media_id)
    push_done(media_id, title)
    print(f"✓ published · media_id={media_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
