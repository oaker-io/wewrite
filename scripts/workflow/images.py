#!/usr/bin/env python3
"""Workflow 3 · 图片 images
读 session 的 article_md · 跑 Step 6(cover + 4 charts)· push 到手机。

用法: python3 scripts/workflow/images.py
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def run_claude_images(md_path: Path, topic_title: str):
    """调 claude -p 让 wewrite skill 跑 Step 6 · 产出 5 张图到 output/images/"""
    prompt = (
        f"请为 `{md_path.relative_to(ROOT)}` 这篇文章生成配图(Step 6)。\n\n"
        f"选题:{topic_title}\n\n"
        "严格要求:\n"
        "1. 用 toolkit/image_gen.py 经 config.yaml 的 Poe provider 生成,不要用网页手动路径\n"
        "2. **5 张图**,输出到 `output/images/`:\n"
        "   - `cover.png`  2.35:1  · 含中文主标题(从 H1 压缩到 10-16 字),副标题「宸的 AI 掘金笔记」\n"
        "   - `chart-1.png` ~ `chart-4.png`  16:9 各一张 · 高密度 infographic-dense\n"
        "3. 文章 md 里的 `![](images/xxx.png)` 占位符对应这 5 个文件,不要改文件名\n"
        "4. 每张图生成后**不要**写 prompts 文件或重新改 md\n"
        "5. 风格:和 chart 深蓝色系协调 · 用 pop-laboratory 风 · 要求 AI 逐字渲染中文数据\n"
        "6. 完成后返回 'DONE images generated'\n\n"
        "失败降级:若 Poe 超时,尝试 Gemini(config.yaml 第二个 provider)。"
    )
    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    print(f"→ claude -p generating 5 images... (5-15 分钟)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude: {r.stderr[-500:]}")
    return r.stdout


def push_images():
    """Push 5 张图到手机 Discord。"""
    imgs_dir = ROOT / "output" / "images"
    expected = ["cover.png", "chart-1.png", "chart-2.png", "chart-3.png", "chart-4.png"]
    found = [imgs_dir / name for name in expected if (imgs_dir / name).exists()]
    missing = [name for name in expected if not (imgs_dir / name).exists()]

    text = (
        f"🎨 **5 张图就绪** · {len(found)}/5\n"
        + (f"⚠️ 缺:{', '.join(missing)}\n" if missing else "")
        + "---\n"
        "回复 `ok` / `继续` 进入发布 · `重做 cover` / `重做 chart-3` 重生成具体某张"
    )
    # Max 10 images/msg · 5 图 1 条搞定
    args = [str(PY), str(PUSH), "--text", text]
    for p in found:
        args += ["--image", str(p)]
    subprocess.run(args, check=True, timeout=300)


def main():
    s = _state.load()
    if s["state"] != _state.STATE_WROTE:
        print(f"❌ state={s['state']} · 要先写完文章", file=sys.stderr); sys.exit(1)

    article_md = s.get("article_md")
    topic = s.get("selected_topic") or {}
    if not article_md:
        print("❌ 无 article_md", file=sys.stderr); sys.exit(1)

    md_path = ROOT / article_md
    if not md_path.exists():
        print(f"❌ {md_path} 不存在", file=sys.stderr); sys.exit(1)

    try:
        run_claude_images(md_path, topic.get("title", ""))
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    imgs_dir = ROOT / "output" / "images"
    _state.advance(_state.STATE_IMAGED, images_dir=str(imgs_dir.relative_to(ROOT)))
    push_images()
    print("✓ images ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
