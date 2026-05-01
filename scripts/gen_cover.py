#!/usr/bin/env python3
"""gen_cover.py · 微信公众号封面图生成器(banner 1146×488 + square 900×900 双出图)。

设计:
  - 走 xhs-card html 引擎(jinja2 + playwright 截图 · 0 钱 · 漂亮模板)
  - banner 与 square 拆 2 个 HTML 文件 · 视觉语言完全不同 · 不靠 CSS 缩放
  - 共享变量在 themes/{theme}.css · 颜色/字体统一
  - 默认 --format both · 同时双图(横版叙事 / 方版中心堆叠)

用法:
  # 单张 · dark-bold 双图(默认)
  venv/bin/python3 scripts/gen_cover.py \\
      --title "手机跑大模型 提速 17 倍 实测" \\
      --subtitle "Microsoft 自家在用" \\
      --tag "AI 红利" \\
      --template wewrite-dark-bold

  # 只要横版
  venv/bin/python3 scripts/gen_cover.py --title "..." --format banner

  # 批量(JSON 输入)
  venv/bin/python3 scripts/gen_cover.py --input titles.json

  # JSON 格式:
  # [
  #   {"title": "...", "subtitle": "...", "tag": "...", "template": "wewrite-dark-bold",
  #    "anchor_glyph": "★", "kicker": "宸的 AI 掘金笔记",
  #    "hero_stats": [{"v": "17x", "l": "提速"}, {"v": "7B", "l": "模型"}]}
  # ]

输出:
  output/cover/{YYYYMMDD-HHMMSS}_{标题前10字}/
    banner.png   (1146×488)
    square.png   (900×900)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib.image_card_client import render_card  # noqa: E402


def _slug(title: str, max_len: int = 12) -> str:
    """中文 OK · 去掉文件名敏感字符 · 截前 N 字。"""
    s = re.sub(r"\s+", "-", (title or "").strip())
    s = re.sub(r"[^\w一-鿿A-Za-z0-9\-]", "", s)
    return s[:max_len] or "cover"


def _spec_for(template: str, theme: str, size_preset: str, fields: dict) -> dict:
    """构造 image_card_client.render_card 的 spec。"""
    return {
        "slug": fields.get("slug", "cover"),
        "engine": "html",
        "platform": "gzh",
        "theme": theme,
        "size_preset": size_preset,
        "author": fields.get("author", "@aipickgold"),
        "pages": [{"template": template, "fields": fields}],
    }


def _canonical_fields(item: dict) -> dict:
    """JSON 输入归一化 · 提供默认值。"""
    return {
        "tag": item.get("tag") or "AI 红利",
        "title_main": (item.get("title") or "").strip(),
        "title_sub": (item.get("subtitle") or "").strip(),
        "anchor_glyph": item.get("anchor_glyph") or "★",
        "kicker": item.get("kicker") or "宸的 AI 掘金笔记",
        "hero_stats": item.get("hero_stats") or [],
    }


def gen_one(item: dict, *, output_dir: Path, fmt: str = "both") -> dict:
    """单条 · 出 banner / square / both · 返回 {format: path}。"""
    fields = _canonical_fields(item)
    template = item.get("template") or "wewrite-dark-bold"
    title = fields["title_main"]
    if not title:
        raise ValueError("title_main 必填")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    sub = output_dir / f"{ts}_{_slug(title)}"
    sub.mkdir(parents=True, exist_ok=True)

    out_paths: dict[str, Path] = {}

    if fmt in ("banner", "both"):
        banner_dir = sub / "_render-banner"
        banner_dir.mkdir(exist_ok=True)
        spec = _spec_for("cover-banner", template, "wewrite-banner",
                         {**fields, "slug": f"banner-{_slug(title, 8)}"})
        outputs = render_card(spec, banner_dir, timeout=120)
        if outputs:
            target = sub / "banner.png"
            shutil.copy2(outputs[0], target)
            out_paths["banner"] = target
        # 清 tmp
        for f in banner_dir.glob("*"):
            try: f.unlink()
            except OSError: pass
        try: banner_dir.rmdir()
        except OSError: pass

    if fmt in ("square", "both"):
        sq_dir = sub / "_render-square"
        sq_dir.mkdir(exist_ok=True)
        spec = _spec_for("cover-square", template, "wewrite-square",
                         {**fields, "slug": f"square-{_slug(title, 8)}"})
        outputs = render_card(spec, sq_dir, timeout=120)
        if outputs:
            target = sub / "square.png"
            shutil.copy2(outputs[0], target)
            out_paths["square"] = target
        for f in sq_dir.glob("*"):
            try: f.unlink()
            except OSError: pass
        try: sq_dir.rmdir()
        except OSError: pass

    print(f"✓ {title[:30]} → {sub.relative_to(ROOT)}")
    for k, v in out_paths.items():
        print(f"   {k}: {v.relative_to(ROOT)}")
    return out_paths


def main() -> int:
    p = argparse.ArgumentParser(description="微信公众号封面图生成(banner+square 双图)")
    p.add_argument("--title", help="主标题")
    p.add_argument("--subtitle", default="", help="副标题")
    p.add_argument("--tag", default="AI 红利", help="顶部 chip 标签")
    p.add_argument("--template", default="wewrite-dark-bold",
                   help="theme 名(themes/<name>.css)· 默认 wewrite-dark-bold")
    p.add_argument("--format", choices=("banner", "square", "both"), default="both",
                   help="输出格式 · 默认 both 双图")
    p.add_argument("--input", help="批量 JSON 文件路径(优先级高于 --title)")
    p.add_argument("--output", default="output/cover",
                   help="输出根目录(默认 output/cover/)")
    args = p.parse_args()

    output_dir = ROOT / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input:
        items = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(items, list):
            print("❌ --input JSON 必须是数组", file=sys.stderr)
            return 1
        ok = fail = 0
        for it in items:
            try:
                gen_one(it, output_dir=output_dir, fmt=args.format)
                ok += 1
            except Exception as e:
                print(f"   ✗ {(it.get('title') or '?')[:30]}: {e}", file=sys.stderr)
                fail += 1
        print(f"\n=== 批量完成 · 成功 {ok} · 失败 {fail} ===")
        return 0 if fail == 0 else 1

    if not args.title:
        p.print_help()
        return 1

    item = {
        "title": args.title,
        "subtitle": args.subtitle,
        "tag": args.tag,
        "template": args.template,
    }
    gen_one(item, output_dir=output_dir, fmt=args.format)
    return 0


if __name__ == "__main__":
    sys.exit(main())
