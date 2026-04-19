#!/usr/bin/env python3
"""Workflow 2b · 改稿 revise
读 session 的 article_md · 调 claude -p 按用户修改意图重写现有文章。
state 保持 wrote(只更新 updated_at)· push 新预览到手机。

用法:
  python3 scripts/workflow/revise.py --instruction "开头太硬,换个故事开场"
  python3 scripts/workflow/revise.py --instruction "加段 Devin 对比"
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def run_claude_revise(md_path: Path, instruction: str):
    """调 claude -p · 让它按 instruction 直接覆写 md_path。"""
    rel = md_path.relative_to(ROOT)
    prompt = (
        f"请按以下修改意图,重写 `{rel}` 这篇微信公众号文章:\n\n"
        "=== 用户修改意图 ===\n"
        f"{instruction}\n\n"
        "=== 硬约束 ===\n"
        f"1. 直接覆写 {rel} · 不另存新文件\n"
        "2. 保持 H1 标题不变,除非用户明确要求换标题\n"
        "3. 保持 `![封面](images/cover.png)` 和 chart 占位符原位(占位符不能删)\n"
        "4. 保持文末 :::author-card + 2 个二维码 + aipickgold 推广段不变\n"
        "5. 字数 1800-2500 保持范围\n"
        "6. 完成后输出:DONE revised"
    )

    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    print(f"→ claude -p revising... (2-6 分钟)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-500:]}")
    return r.stdout


def _excerpt(md: str) -> tuple[str, str]:
    """提取首段 + 末段(跳过 H1/图/容器/引用等非正文)。"""
    lines = md.splitlines()
    first, last = "", ""
    for l in lines:
        if l and not l.startswith(("#", "!", "<", ":", "-", ">", "|")):
            first = l
            break
    for l in reversed(lines):
        if l and not l.startswith(("#", "!", "<", ":", "-", ">", "|")):
            last = l
            break
    return first, last


def push_revised(md_path: Path, instruction: str, word_diff: int):
    """Push 改稿后的预览到 Discord。"""
    md = md_path.read_text(encoding="utf-8")
    new_count = len(md)
    first, last = _excerpt(md)

    sign = "+" if word_diff > 0 else ""
    diff_str = f"{sign}{word_diff}" if word_diff != 0 else "±0"

    header = (
        f"✏️ **已按『{instruction[:50]}』改过**\n"
        f"📂 `{md_path.relative_to(ROOT)}` · {new_count} 字({diff_str})\n"
        "---\n"
        "回复 `ok` / `继续` 进入生图 · 再改一次直接说意图 · `重写` 全部换角度"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", header],
        check=True, timeout=60,
    )

    excerpt = (
        f"**✏️ 新开头:**\n{first[:400]}{'...' if len(first) > 400 else ''}\n\n"
        f"**🎬 新结尾:**\n{last[:300]}{'...' if len(last) > 300 else ''}"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", excerpt],
        check=True, timeout=60,
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruction", required=True,
                    help="用户原话修改意图(完整一句话)")
    ap.add_argument("--dry-run", action="store_true",
                    help="只 build prompt,不实际调 claude")
    args = ap.parse_args(argv)

    instruction = args.instruction.strip()
    if not instruction:
        print("❌ instruction 不能为空", file=sys.stderr); sys.exit(1)

    s = _state.load()
    if s["state"] != _state.STATE_WROTE:
        print(f"❌ state={s['state']} · 必须在 wrote 状态才能改稿",
              file=sys.stderr)
        sys.exit(1)

    article_md = s.get("article_md")
    if not article_md:
        print("❌ session 无 article_md", file=sys.stderr); sys.exit(1)

    md_path = ROOT / article_md
    if not md_path.exists():
        print(f"❌ {md_path} 不存在", file=sys.stderr); sys.exit(1)

    old_count = len(md_path.read_text(encoding="utf-8"))

    if args.dry_run:
        # 仅打印 prompt 预览 · for smoke test
        rel = md_path.relative_to(ROOT)
        print(f"[dry-run] would revise {rel} with instruction: {instruction}")
        return 0

    try:
        run_claude_revise(md_path, instruction)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    if not md_path.exists():
        print(f"❌ {md_path} 被 claude 意外删除", file=sys.stderr); sys.exit(3)

    new_count = len(md_path.read_text(encoding="utf-8"))
    word_diff = new_count - old_count

    # 保持 state=wrote · 只更新 updated_at(advance 会自动刷新)
    _state.advance(_state.STATE_WROTE, article_md=article_md)

    push_revised(md_path, instruction, word_diff)
    print(f"✓ revised · {md_path} · diff={word_diff:+d} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
