#!/usr/bin/env python3
"""Workflow 4 · 推草稿 publish
读 session · 调 cli.py publish · push 草稿链接 + 提醒手动加公众号卡片。

用法:
  python3 scripts/workflow/publish.py            # 默认 · 推完留 done state · 等用户回复
  python3 scripts/workflow/publish.py --auto     # 全自动 · 推完直接通知 · 无需用户操作
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "toolkit"))
from sanitize import prepare_for_publish
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


def push_done(media_id: str, title: str, auto: bool = False):
    auto_tag = " · auto" if auto else ""
    text = (
        f"🚀 **草稿已推送到微信草稿箱{auto_tag}**\n"
        f"📝 {title}\n"
        f"🆔 `{media_id}`\n\n"
        f"📦 **已自动**:H1 去重 · 封面 alt 清空 · 末尾「智辰老师」介绍卡片(含 mp 嵌入卡视觉)\n\n"
        f"---\n"
        f"**⚠️ 唯一手动步骤**(WeChat 平台限制 · 关注卡是 UI-only widget):\n"
        f"1. `mp.weixin.qq.com` → 草稿箱 → 编辑\n"
        f"2. 在文末「智辰老师」卡片里那个白底 mp 占位上方,\n"
        f"   工具栏「资源引用」→「公众号」→ 选 **宸的 AI 掘金笔记**\n"
        f"3. 通读 → 发表\n\n"
        f"💡 那张静态 mp 占位卡是视觉等价物 · 不会真跳关注 · 必须草稿箱手插一次。"
    )
    if auto:
        text += "\n\n📅 自动节奏:今晚 19:30 会再推一次群发提醒 · 在那之前 1 tap 即可。"
    else:
        text += "\n\n下一篇可回 `brief` 触发选题 · 或等明早 08:30 自动 brief。"
    subprocess.run(
        [str(PY), str(PUSH), "--text", text],
        check=True, timeout=60,
    )


def main():
    p = argparse.ArgumentParser(description="推草稿到微信草稿箱")
    p.add_argument("--auto", action="store_true",
                   help="全自动模式 · 推完直接通知 · 不等用户操作")
    args = p.parse_args()

    s = _state.load()
    if s["state"] not in (_state.STATE_IMAGED, _state.STATE_DONE):
        print(f"❌ state={s['state']} · 要先 write → images", file=sys.stderr); sys.exit(1)

    article_md = s.get("article_md")
    topic = s.get("selected_topic") or {}
    if not article_md:
        print("❌ 无 article_md", file=sys.stderr); sys.exit(1)

    cover = ROOT / "output" / "images" / "cover.png"
    if not cover.exists():
        print("❌ cover.png 不存在", file=sys.stderr); sys.exit(1)

    title = (topic.get("title") or "")[:60] or "(untitled)"

    # 发布前 sanitize:去 H1 / 清 cover alt / 兜底 author-card
    md_abs = (ROOT / article_md).resolve()
    publish_md = prepare_for_publish(md_abs)
    if publish_md != md_abs:
        print(f"→ sanitized: {publish_md.name}")
    publish_md_rel = str(publish_md.relative_to(ROOT))

    try:
        media_id, _out = run_publish(
            md_path=publish_md_rel,
            cover=str(cover.relative_to(ROOT)),
            title=title,
        )
    finally:
        # 清掉 sanitize 临时副本(避免 output/ 堆积冗余文件)
        if publish_md != md_abs and publish_md.exists():
            try: publish_md.unlink()
            except OSError: pass

    _state.advance(_state.STATE_DONE, draft_media_id=media_id)
    push_done(media_id, title, auto=args.auto)
    print(f"✓ published · media_id={media_id}{' · auto' if args.auto else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
