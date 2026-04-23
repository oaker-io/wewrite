#!/usr/bin/env python3
"""picpost · 贴图笔记生成 skill(微信公众号贴图 + 小红书互通)。

输入 1 个主题 + 框架 → 输出可双平台发布的素材包。
不调发布 API · 输出文件 · user 手动到公众号「贴图」+ 小红书 app 上传。
(API 等公众号 / 小红书开放后再加 to_wx_post.py / to_xhs.py)

输出结构:
    output/picpost/<YYYY-MM-DD>-<slug>/
      ├── post-1.png ... post-N.png      # 1:1 (1080×1080) · 3-9 张
      ├── caption-wechat.txt             # 公众号贴图文案(简洁 · 150-300 字)
      ├── caption-xhs.txt                # 小红书文案(带 #话题 · 200-500 字)
      └── meta.yaml                      # 主题 / 框架 / tags / 状态

用法:
    # 自动选框架(让 claude 决定)
    python3 scripts/workflow/picpost.py "30 天 Cursor 复盘 · 7 张图"

    # 显式指定框架
    python3 scripts/workflow/picpost.py "Claude 4.7 vs GPT-5 横评" --framework P2

    # 配主推文章(把贴图作为主推的视觉版)
    python3 scripts/workflow/picpost.py "Cursor 30 天复盘" \\
        --companion-of output/2026-04-23-cursor.md --framework P1

    # 只生 caption · 不调 claude 生图(给 user 自己画图)
    python3 scripts/workflow/picpost.py "本周金句合集" --framework P5 --no-images

设计公约:
    - 调 claude -p 让 wewrite skill 跑生图 + 写 caption(走 picpost-frameworks.md 模板)
    - 输出全部到 output/picpost/<slug>/ · 不污染 output/images/(那是主推用的)
    - meta.yaml status 字段记 4 态:drafted / wechat_posted / xhs_posted / both_posted
    - 不调发布 API · user 手动操作
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state  # noqa: F401 (预留 · picpost 后续可能也走 state machine)

ROOT = Path(__file__).resolve().parent.parent.parent
PICPOST_REF = ROOT / "references" / "picpost-frameworks.md"
COVER_SQ_REF = ROOT / "references" / "visuals" / "styles" / "cover-square.md"
CASE_REF = ROOT / "references" / "visuals" / "styles" / "case-realistic.md"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

FRAMEWORKS = ("auto", "P1", "P2", "P3", "P4", "P5")
FRAMEWORK_POSTS = {
    "P1": (5, 7),  # 时间线复盘
    "P2": (4, 6),  # 对比清单
    "P3": (5, 9),  # 步骤拆解
    "P4": (3, 5),  # 数据爆点
    "P5": (5, 9),  # 金句合集
}

_CST = timezone(timedelta(hours=8))


def _slugify(title: str, maxlen: int = 40) -> str:
    eng = re.findall(r"[A-Za-z0-9]+", title)
    if eng:
        s = "-".join(eng[:5]).lower()
    else:
        import hashlib
        s = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
    return s[:maxlen]


def _build_prompt(
    title: str,
    out_dir: Path,
    framework: str,
    *,
    companion_of: Path | None,
    no_images: bool,
) -> str:
    framework_hint = (
        f"**强制使用框架**:`references/picpost-frameworks.md` 里的 {framework}。"
        if framework != "auto"
        else "选用 `references/picpost-frameworks.md` 里 P1-P5 中**最适合本主题**的一套。"
    )
    if framework in FRAMEWORK_POSTS:
        lo, hi = FRAMEWORK_POSTS[framework]
        post_count_hint = f"张数 **{lo}-{hi}** 张(严格按 {framework} 的范围)"
    else:
        post_count_hint = "张数 **3-9** 张(单次贴图笔记上限)"

    companion_block = ""
    if companion_of:
        companion_block = (
            f"\n\n**这是主推文章 `{companion_of.relative_to(ROOT)}` 的视觉伴生版**。\n"
            "贴图核心点要跟主推一致 · 但**不是简单截屏**:\n"
            "- 抽主推里的 N 个最强数据点 / 最反直觉观点 · 每张 1 个\n"
            "- 跟主推共用 cover-square.png 的视觉风格(若已存在 · 可直接复用)\n"
            "- caption 末尾必带「完整论证看主推 · 公众号「宸的 AI 掘金笔记」」\n"
        )

    images_block = ""
    if not no_images:
        images_block = (
            "\n3. **生 N 张 1:1 (1080×1080) post-i.png** · 输出到上面 out_dir:\n"
            f"   - 严格按 `{COVER_SQ_REF.relative_to(ROOT)}` 的视觉规则(大字 / 留白 / 80×80 缩略可读)\n"
            "   - 数字驱动的图(eg P1 时间线 / P4 数据爆点)· 用 case-realistic 美学\n"
            f"     (参考 `{CASE_REF.relative_to(ROOT)}` 的拟真截图风)\n"
            "   - 金句卡 / 步骤卡 · 大字 + 单一信息 · 不要塞满\n"
            "   - 每张图独立成立(用户滑动查看 · 单张不能依赖上下文)\n"
            "   - 用 toolkit/image_gen.py 经 Poe 生成 · 失败 fallback Gemini\n"
        )
    else:
        images_block = "\n3. **--no-images 模式** · 不生图 · 只输出 caption + meta\n"

    return (
        "请使用 wewrite skill 生成一份**贴图笔记素材包**(微信公众号贴图 + 小红书图文双平台)。\n\n"
        f"**主题**:{title}\n\n"
        f"**输出目录**:`{out_dir.relative_to(ROOT)}`\n\n"
        f"**强制先读** `{PICPOST_REF.relative_to(ROOT)}`(完整框架库 + caption 模板)。\n\n"
        f"{framework_hint} · {post_count_hint}\n"
        f"{companion_block}\n"
        "**严格要求**:\n\n"
        "1. **创建输出目录** 如果不存在(mkdir -p)\n"
        "2. **写 3 个文件**(无论 --no-images 与否都要):\n"
        f"   - `{out_dir.relative_to(ROOT)}/caption-wechat.txt` · 公众号贴图文案(150-300 字)\n"
        f"   - `{out_dir.relative_to(ROOT)}/caption-xhs.txt` · 小红书文案(200-500 字 · 必带 #话题 + 表情)\n"
        f"   - `{out_dir.relative_to(ROOT)}/meta.yaml` · 主题/框架/tags/状态(参考 picpost-frameworks.md 末尾模板)\n"
        f"{images_block}"
        "\n4. **写完返回**:'DONE picpost <out_dir>'\n\n"
        "**caption 关键规则**(从 picpost-frameworks.md 摘录):\n"
        "- 公众号 caption 不带 #话题(看起来乱)· 简洁 · 末尾 1 句钩子\n"
        "- 小红书 caption 必带 3-5 个 #话题(无 # 流量减半)· 必带 emoji · 末尾 CTA + 私域\n"
        "- 两份 caption 主信息一致 · 但语气不同(公众号偏理性 · 小红书偏情绪)\n"
    )


def run_claude_picpost(
    title: str,
    out_dir: Path,
    framework: str,
    *,
    companion_of: Path | None = None,
    no_images: bool = False,
) -> str:
    prompt = _build_prompt(
        title, out_dir, framework,
        companion_of=companion_of, no_images=no_images,
    )
    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    label = f"PICPOST [{framework}]" + (" --no-images" if no_images else "")
    if companion_of:
        label += f" companion-of:{companion_of.name}"
    print(f"→ claude -p {label}... (3-15 分钟 · 取决于图数)")
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude: {r.stderr[-500:]}")
    return r.stdout


def push_done_notice(out_dir: Path, framework: str) -> None:
    posts = sorted(out_dir.glob("post-*.png"))
    cap_wx = out_dir / "caption-wechat.txt"
    cap_xhs = out_dir / "caption-xhs.txt"
    meta = out_dir / "meta.yaml"
    text_lines = [
        f"🖼️ **贴图笔记就绪** · {framework}",
        f"📂 `{out_dir.relative_to(ROOT)}`",
        f"📊 {len(posts)} 张图 · caption-wechat: {'✓' if cap_wx.exists() else '✗'} · caption-xhs: {'✓' if cap_xhs.exists() else '✗'} · meta: {'✓' if meta.exists() else '✗'}",
        "",
        "**手动发布**:",
        "1. 公众号:mp.weixin.qq.com → 贴图 → 上传 N 张 + paste caption-wechat.txt",
        "2. 小红书:小红书 app → 发布笔记 → 上传 N 张 + paste caption-xhs.txt",
        "",
        "发完更新 `meta.yaml` 的 `status` 字段:wechat_posted / xhs_posted / both_posted",
    ]
    args = [str(PY), str(PUSH), "--text", "\n".join(text_lines)]
    # 附带前 5 张图(Discord 单条消息上限 10 图)
    for p in posts[:5]:
        args += ["--image", str(p)]
    try:
        subprocess.run(args, check=True, timeout=300)
    except Exception as e:
        print(f"⚠ push 失败: {e}", file=sys.stderr)


def write_initial_meta(
    out_dir: Path,
    title: str,
    framework: str,
    companion_of: Path | None,
) -> None:
    """先写一个 stub meta.yaml · claude 跑完会覆盖完整版。"""
    meta = {
        "title": title,
        "framework": framework,
        "created_at": datetime.now(_CST).isoformat(timespec="seconds"),
        "post_count": 0,  # claude 跑完会更新
        "target_platforms": ["wechat-picpost", "xhs"],
        "tags": {"wechat": [], "xhs": []},
        "companion_main_article": (
            str(companion_of.relative_to(ROOT)) if companion_of else None
        ),
        "cta": {"qr": "qr-zhichen.png", "cta_text": "加我备注「" + title[:8] + "」"},
        "status": "drafted",
    }
    (out_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    p = argparse.ArgumentParser(description="picpost · 贴图笔记生成")
    p.add_argument("title", help="贴图主题 · eg \"30 天 Cursor 复盘\"")
    p.add_argument("--framework", choices=FRAMEWORKS, default="auto",
                   help="P1 时间线 / P2 对比 / P3 步骤 / P4 数据 / P5 金句 · auto 让 claude 选")
    p.add_argument("--companion-of", help="跟某主推文章伴生 · 路径如 output/x.md")
    p.add_argument("--no-images", action="store_true", help="只生 caption + meta · 不调图模型")
    p.add_argument("--no-push", action="store_true", help="不 push Discord 通知")
    args = p.parse_args()

    title = args.title.strip()
    if not title:
        print("❌ title 不能为空", file=sys.stderr)
        return 1

    companion_path: Path | None = None
    if args.companion_of:
        companion_path = (ROOT / args.companion_of).resolve()
        if not companion_path.exists():
            print(f"❌ --companion-of {companion_path} 不存在", file=sys.stderr)
            return 1

    if not PICPOST_REF.exists():
        print(f"❌ {PICPOST_REF} 不存在 · 缺框架库 · 跑不了", file=sys.stderr)
        return 1

    date_str = datetime.now(_CST).strftime("%Y-%m-%d")
    slug = _slugify(title)
    out_dir = ROOT / "output" / "picpost" / f"{date_str}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    write_initial_meta(out_dir, title, args.framework, companion_path)
    print(f"→ out_dir = {out_dir}")
    print(f"→ stub meta.yaml written · 等 claude 跑完会更新")

    try:
        run_claude_picpost(
            title, out_dir, args.framework,
            companion_of=companion_path, no_images=args.no_images,
        )
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    posts = sorted(out_dir.glob("post-*.png"))
    cap_wx = out_dir / "caption-wechat.txt"
    cap_xhs = out_dir / "caption-xhs.txt"
    print(f"✓ picpost 完成 · {len(posts)} 张图 · "
          f"wechat caption: {'✓' if cap_wx.exists() else '✗'} · "
          f"xhs caption: {'✓' if cap_xhs.exists() else '✗'}")

    if not args.no_push:
        push_done_notice(out_dir, args.framework)

    return 0


if __name__ == "__main__":
    sys.exit(main())
