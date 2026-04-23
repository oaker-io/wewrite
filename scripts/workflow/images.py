#!/usr/bin/env python3
"""Workflow 3 · 图片 images
读 session 的 article_md · 跑 Step 6(cover + 4 charts)· push 到手机。

用法:
  python3 scripts/workflow/images.py                    # 默认 hotspot 风
  python3 scripts/workflow/images.py --style tutorial   # 干货 · infographic-dense
  python3 scripts/workflow/images.py --style case       # 案例 · case-realistic 套件 ★
  python3 scripts/workflow/images.py --auto             # 全自动 · 不等 ok · 自动进 publish
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

CASE_REALISTIC_REF = ROOT / "references" / "visuals" / "styles" / "case-realistic.md"
COVER_SQUARE_REF = ROOT / "references" / "visuals" / "styles" / "cover-square.md"
CUTE_INFOGRAPHIC_REF = ROOT / "references" / "visuals" / "styles" / "cute-infographic.md"


def _build_prompt_default(md_path: Path, topic_title: str) -> str:
    """通用配图 prompt(hotspot / tutorial 都用这个 · 主推位 · 6 张图含 1:1 thumb)。"""
    cover_sq_rel = COVER_SQUARE_REF.relative_to(ROOT)
    return (
        f"请为 `{md_path.relative_to(ROOT)}` 这篇文章生成配图(Step 6)。\n\n"
        f"选题:{topic_title}\n\n"
        "严格要求:\n"
        "1. 用 toolkit/image_gen.py 经 config.yaml 的 Poe provider 生成,不要用网页手动路径\n"
        "2. **6 张图**,输出到 `output/images/`:\n"
        "   - `cover.png`        2.35:1  · 内文首图大封面 · 中文主标题 10-16 字 + 副标「宸的 AI 掘金笔记」\n"
        f"   - `cover-square.png` 1:1 (1080×1080) · **看一看 thumb 缩略位** · 严格按 `{cover_sq_rel}` 配置\n"
        "                          · 主标 8-10 字(从 H1 极致压缩 · 数字保留)· 80×80 缩略仍可读\n"
        "   - `chart-1.png` ~ `chart-4.png`  16:9 各一张 · 高密度 infographic-dense\n"
        "3. 文章 md 里的 `![](images/xxx.png)` 占位符对应 cover/chart-* 5 个 · cover-square.png **不放 md 里**(只用作 thumb)\n"
        "4. 每张图生成后**不要**写 prompts 文件或重新改 md\n"
        "5. 风格:和 chart 深蓝色系协调 · 用 pop-laboratory 风 · 要求 AI 逐字渲染中文数据\n"
        "6. 完成后返回 'DONE images generated'\n\n"
        "失败降级:若 Poe 超时,尝试 Gemini(config.yaml 第二个 provider)。"
    )


def _build_prompt_narrative(md_path: Path, topic_title: str) -> str:
    """漫画 / 萌系信息图 prompt(参考极客杰尼范文 · cute-infographic 套件)。

    适合「Agent 系统讲解」「概念图解」「面向小白的科普」类。
    比 case-realistic 更易传播 · 转发率更高 · 但牺牲一点严肃可信感。
    """
    cute_ref_rel = CUTE_INFOGRAPHIC_REF.relative_to(ROOT)
    cover_sq_rel = COVER_SQUARE_REF.relative_to(ROOT)
    return (
        f"请为 `{md_path.relative_to(ROOT)}` 这篇文章生成配图(Step 6 · 萌系信息图风 · narrative 模式)。\n\n"
        f"选题:{topic_title}\n\n"
        f"**强制先读** `{cute_ref_rel}`(完整 prompt 模板 + 5 个 layout 模板 + negative prompt)。\n"
        f"**额外读** `{cover_sq_rel}`(1:1 thumb 配置)。\n\n"
        "严格要求:\n"
        f"1. 严格按 `{cute_ref_rel}` 的 5 个 layout 走(挑最适合本文的)· 6 张图:\n"
        "   - `cover.png` 2.35:1 · 萌系角色 + 标题(eg「<拟人比喻> 系统」)· 用 layout 1 / 2 / 5\n"
        "   - `chart-1.png` 16:9 · layout 1 (角色 + 痛点 4 宫格) · 铺开问题\n"
        "   - `chart-2.png` 16:9 · layout 2 (系统架构拟人图) · 讲清方案\n"
        "   - `chart-3.png` 16:9 · layout 3 (时间流程横排) · 步骤化\n"
        "   - `chart-4.png` 16:9 · layout 4 (之前 vs 之后 对比图) · 给变化\n"
        f"   - `cover-square.png` 1:1 · **不萌系** · 走 `{cover_sq_rel}` 数字大字风(thumb 要清晰可读)\n\n"
        "2. **★ 同一角色贯穿全篇**(连续性):cover 用什么角色 · chart-1..4 都用同一角色\n"
        "   eg 全篇都是龙虾 / 都是机器人 / 都是猫\n\n"
        "3. **★ 暖色板**:橙 / 黄 / 浅蓝 · 不要冷调蓝紫(不亲切)\n\n"
        "4. **★ 手绘感**:略歪 · 不要工业 SVG 那种死板 · 不要 photoshop 拟物风\n\n"
        "5. 用 toolkit/image_gen.py 经 Poe 生成 · 失败 fallback Gemini\n"
        "6. 完成后返回 'DONE narrative images generated'\n\n"
        "**自检**:这套图给小白看 · 应该让人一眼笑出来 + 能看懂 · 而不是「这是技术架构图」。"
    )


def _build_prompt_shortform(md_path: Path, topic_title: str) -> str:
    """短文(副推位)配图 prompt · 只生 1:1 thumb + 0-2 张内文图。"""
    cover_sq_rel = COVER_SQUARE_REF.relative_to(ROOT)
    return (
        f"请为 `{md_path.relative_to(ROOT)}` 这篇 **副推短文** 生成配图(Step 6 · 短文模式)。\n\n"
        f"选题:{topic_title}\n\n"
        "**短文模式特殊要求**:\n"
        "1. **只生 1-3 张图**(不是 6 张):\n"
        f"   - `cover-square.png` 1:1 (1080×1080) · 看一看 thumb · 严格按 `{cover_sq_rel}` 配置\n"
        "   - 短文 md 里若有 `![](images/chart-1.png)` 占位 · 生 1 张 16:9 chart-1\n"
        "   - 短文 md 里若有 `![](images/chart-2.png)` 占位 · 再生 1 张 16:9 chart-2\n"
        "   - **超过 chart-2 的占位忽略**(短文不允许多图)\n"
        "2. **不生 cover.png**(短文不显示大封面)\n"
        "3. cover-square 主标 8-10 字 · 大字 · 80×80 缩略仍可读\n"
        "4. 用 toolkit/image_gen.py 经 Poe 生成 · 失败 fallback Gemini\n"
        "5. 完成后返回 'DONE shortform images generated'\n\n"
        "**自检**:看一下 md 里有几个 ![](images/...) 占位 · 你只生这么多 + 1 张 cover-square。"
    )


def _build_prompt_case(md_path: Path, topic_title: str) -> str:
    """案例 · case-realistic 套件 prompt(2026-04-23 加 · 周三轮播)。

    强制读 references/visuals/styles/case-realistic.md · 6 张图(5 case + 1 cover-square)。
    数字必须从 markdown 抽真实出现的 · 不能让 AI 编。
    """
    case_ref_rel = CASE_REALISTIC_REF.relative_to(ROOT)
    cover_sq_rel = COVER_SQUARE_REF.relative_to(ROOT)
    return (
        f"请为 `{md_path.relative_to(ROOT)}` 这篇 **AI 真实成功案例** 文章生成配图(Step 6 · case-realistic 套件)。\n\n"
        f"选题:{topic_title}\n\n"
        f"**强制先读** `{case_ref_rel}`(完整 prompt 模板 + negative prompt + 5 张图各自配置)。\n"
        f"**额外读** `{cover_sq_rel}`(1:1 thumb 配置 · 走「2) 案例 / 复盘类」数字大字风)。\n\n"
        "严格要求:\n"
        f"1. 严格按 `{case_ref_rel}` 的 5 张图配置走:\n"
        "   - `cover.png` · 真实产品 UI 截图(macOS / iOS / 浏览器三选一)· photorealistic\n"
        "   - `chart-1.png` · 真实 dashboard 数据截图(Stripe / Mixpanel / Vercel 风)\n"
        "   - `chart-2.png` · 功效对比图(before/after split 或 30 天曲线)\n"
        "   - `chart-3.png` · 真实操作截图(terminal / VS Code / DevTools)\n"
        "   - `chart-4.png` · 真实结果证明(Stripe 通知 / GitHub stars / Tweet 截图)\n"
        f"   - `cover-square.png` · 1:1 (1080×1080) · 数字大字风(从案例文章抽 1 个最爆的数字 · 如 $12,847 / Day 30)\n\n"
        "2. **★ 数字必须从 markdown 中真实出现的数字抽** · 不要凭空编:\n"
        "   - 先读 markdown 找出所有具体数字(如 `$12,847` / `4,891 users` / `Day 30`)\n"
        "   - 把这些数字放进对应 chart 的 prompt · 让生成的截图包含这些数字\n"
        "   - 数字要 `not round`(避免 5000 / 10000 / $1000 这种凑数)\n\n"
        "3. **★ 必带 negative prompt**(case-realistic.md 末尾那段)· 拒绝插画/卡通/水彩/渐变光晕等\n\n"
        "4. 用 toolkit/image_gen.py 经 config.yaml 的 Poe provider(nano-banana-2)· 失败 fallback Gemini\n"
        "5. 输出到 `output/images/` · 文件名固定 cover.png / chart-1.png ... chart-4.png · 不要改名\n"
        "6. 每张图生成后**不要**写 prompts 文件或改 md\n"
        "7. 完成后返回 'DONE case-realistic images generated'\n\n"
        "**自检**:5 张图都不应该看起来像「AI 艺术作品」 · 应该看起来像「随手截的真实工作流」。"
    )


def run_claude_images(md_path: Path, topic_title: str, style: str = "default"):
    """调 claude -p 让 wewrite skill 跑 Step 6 · 产出图片到 output/images/

    style:
      - "default"   : 主推 6 张图(5 + 1:1 thumb) · 走 _build_prompt_default
      - "case"      : 案例拟真套件 6 张 · 走 _build_prompt_case + case-realistic.md
      - "narrative" : 萌系信息图 6 张 · 走 _build_prompt_narrative + cute-infographic.md
      - "shortform" : 短文 1-3 张(1:1 thumb + 0-2 chart) · 走 _build_prompt_shortform
      - "tutorial"  : 等价 default(预留 · 后续可单独定制)
    """
    if style == "shortform":
        prompt = _build_prompt_shortform(md_path, topic_title)
        label = "SHORTFORM (1:1 thumb + 0-2 charts)"
    elif style == "narrative":
        if not CUTE_INFOGRAPHIC_REF.exists():
            print(f"⚠ {CUTE_INFOGRAPHIC_REF} 不存在 · fallback 到 default 配图", file=sys.stderr)
            prompt = _build_prompt_default(md_path, topic_title)
            label = "DEFAULT (cute-infographic ref missing)"
        else:
            prompt = _build_prompt_narrative(md_path, topic_title)
            label = "NARRATIVE (萌系信息图)"
    elif style == "case":
        if not CASE_REALISTIC_REF.exists():
            print(f"⚠ {CASE_REALISTIC_REF} 不存在 · fallback 到 default 配图", file=sys.stderr)
            prompt = _build_prompt_default(md_path, topic_title)
            label = "DEFAULT (case ref missing)"
        else:
            prompt = _build_prompt_case(md_path, topic_title)
            label = "CASE-REALISTIC ★"
    else:
        prompt = _build_prompt_default(md_path, topic_title)
        label = "DEFAULT" if style == "default" else f"DEFAULT ({style})"

    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    print(f"→ claude -p generating 5 images [{label}]... (5-15 分钟)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude: {r.stderr[-500:]}")
    return r.stdout


def push_images(auto: bool = False, style: str = "default"):
    """Push 图到手机 Discord。

    style 决定 expected 文件清单:
      - default / case / tutorial:cover + cover-square + chart-1..4(共 6 张)
      - shortform:cover-square + chart-1..2(最多 3 张 · chart 视 md 占位决定)
    """
    imgs_dir = ROOT / "output" / "images"
    if style == "shortform":
        expected = ["cover-square.png", "chart-1.png", "chart-2.png"]
    else:
        expected = ["cover.png", "cover-square.png",
                    "chart-1.png", "chart-2.png", "chart-3.png", "chart-4.png"]
    found = [imgs_dir / name for name in expected if (imgs_dir / name).exists()]
    missing = [name for name in expected if not (imgs_dir / name).exists()]

    if auto:
        text = (
            f"🎨 **5 张图就绪 · auto** · {len(found)}/5\n"
            + (f"⚠️ 缺:{', '.join(missing)}\n" if missing else "")
            + "---\n"
            "auto 模式 · 接下来:11:00 auto_review → 12:00 auto_publish · 无需回复"
        )
    else:
        text = (
            f"🎨 **5 张图就绪** · {len(found)}/5\n"
            + (f"⚠️ 缺:{', '.join(missing)}\n" if missing else "")
            + "---\n"
            "回复 `ok` / `继续` 进入发布 · `重做 cover` / `重做 chart-3` 重生成具体某张"
        )
    args = [str(PY), str(PUSH), "--text", text]
    for p in found:
        args += ["--image", str(p)]
    subprocess.run(args, check=True, timeout=300)


def _parse_argv() -> tuple[str, bool]:
    """返回 (style, auto)。"""
    p = argparse.ArgumentParser(description="生成配图")
    p.add_argument("--style", choices=("default", "tutorial", "hotspot", "case", "shortform", "narrative"),
                   default="default",
                   help="配图风格 · case=拟真截图 · narrative=萌系信息图 · shortform=短文(1:1+0-2 chart)")
    p.add_argument("--auto", action="store_true", help="全自动 · 不等用户 ok")
    args = p.parse_args()
    return args.style, args.auto


def _resolve_style(cli_style: str) -> str:
    """优先用 cli_style(显式)· 否则用 session.auto_schedule.image_style。"""
    # cli 显式传 shortform · 优先级最高(短文流程)
    if cli_style == "shortform":
        return "shortform"
    s = _state.load()
    auto_sched = s.get("auto_schedule") or {}
    img_style = auto_sched.get("image_style")
    if img_style == "case-realistic":
        return "case"
    if img_style == "cute-infographic":
        return "narrative"
    if img_style == "shortform":
        return "shortform"
    if img_style in ("mockup", "infographic", "simple"):
        # 走 default · 这些 style 走通用 prompt(已经在写文阶段引导了 layout)
        return "default"
    return cli_style if cli_style != "default" else "default"


def main():
    cli_style, auto = _parse_argv()

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

    style = _resolve_style(cli_style)
    print(f"→ image style = {style} (cli={cli_style} · session.image_style={(s.get('auto_schedule') or {}).get('image_style')})")

    try:
        run_claude_images(md_path, topic.get("title", ""), style=style)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    imgs_dir = ROOT / "output" / "images"
    _state.advance(_state.STATE_IMAGED, images_dir=str(imgs_dir.relative_to(ROOT)))
    push_images(auto=auto, style=style)
    print(f"✓ images ready [{style}]{' · auto' if auto else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
