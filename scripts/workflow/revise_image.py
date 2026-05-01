#!/usr/bin/env python3
"""Workflow 3b · 单图返工 revise_image
state 必须 imaged · 只重生指定一张(cover / chart-1..4)· 其他不动。

用法:
  python3 scripts/workflow/revise_image.py --target cover
  python3 scripts/workflow/revise_image.py --target chart-3 --hint "色调冷一点 · 别堆那么多字"
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

VALID_TARGETS = {"cover", "chart-1", "chart-2", "chart-3", "chart-4"}


def normalize_target(raw: str) -> str | None:
    """容错:'Cover' / 'CHART-3' / 'chart 3' / 'chart3' → 标准 cover|chart-N"""
    if not raw:
        return None
    t = raw.strip().lower().replace("_", "-")
    # 去掉中英文空格
    t = re.sub(r"\s+", "", t)
    if t == "cover":
        return "cover"
    # chart3 / chart-3 / chart—3 (em-dash) 归一
    m = re.match(r"^chart[-‐‒–—]?([1-4])$", t)
    if m:
        return f"chart-{m.group(1)}"
    return None


def build_prompt(target: str, article_md: str, topic_title: str, hint: str | None) -> str:
    """构造 claude prompt · 单测会直接调用这个函数检查内容。"""
    feedback = hint if hint else "用户不满意当前这张 · 换个视觉方向"
    if target == "cover":
        spec = "cover · 2.35:1 · 含中文主标题(从 H1 压缩到 10-16 字)· 副标题「宸的 AI 掘金笔记」"
    else:
        spec = f"{target} · 16:9 · 高密度 infographic-dense · 深蓝色系协调"

    return (
        f"请重新生成 `output/images/{target}.png` 这一张图(其他 4 张保留不要动)。\n\n"
        f"原文章:{article_md}\n"
        f"原选题:{topic_title}\n"
        f"用户反馈:{feedback}\n\n"
        "硬约束:\n"
        f"1. 只重生 {target}.png · 其他 4 张不动\n"
        "2. 用 toolkit/image_gen.py 经 config.yaml 的 Poe provider\n"
        "3. 规格:\n"
        f"   - {spec}\n"
        f"4. 完成后返回 'DONE revised {target}'"
    )


def run_claude_revise_image(target: str, article_md: str, topic_title: str, hint: str | None):
    prompt = build_prompt(target, article_md, topic_title, hint)
    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    print(f"→ claude -p re-generating {target}.png... (2-8 分钟)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-500:]}")
    return r.stdout


def push_revised_image(target: str, img_path: Path):
    text = f"🎨 **{target}.png 已重做**"
    if img_path.exists():
        args = [str(PY), str(PUSH), "--text", text, "--image", str(img_path)]
    else:
        text += f"\n⚠️ 但文件 {img_path} 没找到 · 请本地看 claude 输出"
        args = [str(PY), str(PUSH), "--text", text]
    subprocess.run(args, check=True, timeout=120)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True,
                    help="cover | chart-1 | chart-2 | chart-3 | chart-4")
    ap.add_argument("--hint", default=None,
                    help="用户反馈(可选 · 没给就用默认 '换个方向')")
    ap.add_argument("--dry-run", action="store_true",
                    help="只 build prompt · 不调 claude")
    args = ap.parse_args(argv)

    target = normalize_target(args.target)
    if target not in VALID_TARGETS:
        print(f"❌ target '{args.target}' 非法 · 必须是 cover 或 chart-[1-4]",
              file=sys.stderr)
        sys.exit(1)

    s = _state.load()
    if s["state"] != _state.STATE_IMAGED:
        print(f"❌ state={s['state']} · 必须在 imaged 状态才能返工单图",
              file=sys.stderr)
        sys.exit(1)

    article_md = s.get("article_md") or ""
    topic = s.get("selected_topic") or {}
    topic_title = topic.get("title", "")

    if args.dry_run:
        prompt = build_prompt(target, article_md, topic_title, args.hint)
        print(f"[dry-run] target={target}")
        print(f"[dry-run] prompt:\n{prompt}")
        return 0

    try:
        run_claude_revise_image(target, article_md, topic_title, args.hint)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    img_path = ROOT / "output" / "images" / f"{target}.png"
    # state 仍 imaged · 只刷新 updated_at
    _state.advance(_state.STATE_IMAGED, images_dir=s.get("images_dir"))
    push_revised_image(target, img_path)
    print(f"✓ revised image · {img_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
