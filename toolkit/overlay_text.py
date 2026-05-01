#!/usr/bin/env python3
"""
overlay_text.py — 在 AI 生成的无字底图上精准叠加中文字

用途:图像模型对长中文、小字、中英混排的渲染错误率高。
WeWrite 的 T2 工作流:AI 出无字底图 + 本脚本用 Pillow 叠汉字。

用法:
    python3 toolkit/overlay_text.py BASE_PNG OVERLAY_JSON [-o OUT] [--verbose]

默认输出:
    - BASE_PNG 以 "-raw.png" 结尾 → 输出同目录 ".png"(去掉 -raw)
    - 否则 → 追加 "-final.png"
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------- 字体检测 ----------

_PINGFANG = Path("/System/Library/Fonts/PingFang.ttc")
_STHEITI_MEDIUM = Path("/System/Library/Fonts/STHeiti Medium.ttc")
_STHEITI_LIGHT = Path("/System/Library/Fonts/STHeiti Light.ttc")
_SONGTI = Path("/System/Library/Fonts/Supplemental/Songti.ttc")

# PingFang.ttc face index: Regular=0, Medium=1, Semibold=2, Bold=3, Heavy=4
_PINGFANG_INDEX = {
    "Regular": 0, "Medium": 1, "Semibold": 2, "Bold": 3, "Heavy": 4,
}


def _find_source_han_sans() -> Path | None:
    for root in [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts")]:
        if not root.exists():
            continue
        for f in root.glob("SourceHanSans*.*"):
            return f
        for f in root.glob("NotoSansCJK*.*"):
            return f
    return None


@lru_cache(maxsize=64)
def _load_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """按优先级加载中文字体。缓存 (weight, size) 组合。"""
    weight = weight or "Regular"

    # 1. PingFang(macOS 默认中文无衬线,最美)
    if _PINGFANG.exists():
        idx = _PINGFANG_INDEX.get(weight, 1)  # 默认 Medium
        try:
            return ImageFont.truetype(str(_PINGFANG), size=size, index=idx)
        except (OSError, ValueError):
            pass

    # 2. STHeiti(macOS 兜底黑体)
    if weight in ("Regular", "Light") and _STHEITI_LIGHT.exists():
        try:
            return ImageFont.truetype(str(_STHEITI_LIGHT), size=size)
        except OSError:
            pass
    if _STHEITI_MEDIUM.exists():
        try:
            return ImageFont.truetype(str(_STHEITI_MEDIUM), size=size)
        except OSError:
            pass
    if _STHEITI_LIGHT.exists():
        try:
            return ImageFont.truetype(str(_STHEITI_LIGHT), size=size)
        except OSError:
            pass

    # 3. 思源黑体 / Noto Sans CJK(如用户安装)
    han_sans = _find_source_han_sans()
    if han_sans:
        try:
            return ImageFont.truetype(str(han_sans), size=size)
        except OSError:
            pass

    # 4. 宋体兜底
    if _SONGTI.exists():
        try:
            return ImageFont.truetype(str(_SONGTI), size=size)
        except OSError:
            pass

    # 5. PIL 默认(英文字体,中文会乱)
    print("⚠️  未找到中文字体,中文将渲染为方块。请装 PingFang / 思源黑体", file=sys.stderr)
    return ImageFont.load_default()


# ---------- 颜色解析 ----------

def _parse_color(s: str | None) -> tuple[int, int, int, int] | None:
    """解析 #RRGGBB 或 #RRGGBBAA 为 (R,G,B,A)。"""
    if not s:
        return None
    s = s.strip().lstrip("#")
    if len(s) == 6:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return (r, g, b, 255)
    if len(s) == 8:
        r, g, b, a = (int(s[i:i+2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, a)
    raise ValueError(f"Invalid color: {s}")


# ---------- 文本换行(CJK 感知)----------

def _wrap_text(text: str, max_width_px: int, font: ImageFont.FreeTypeFont) -> list[str]:
    """按像素宽度换行,CJK 字符按 2 倍宽度估算。"""
    if "\n" in text:
        out = []
        for line in text.split("\n"):
            out.extend(_wrap_text(line, max_width_px, font))
        return out

    # 粗估每行能容纳多少字符
    avg_ascii_width = font.getlength("Aa国")
    if avg_ascii_width == 0:
        return [text]
    # 假设一半是中文(每字 ≈ font.size),简单保守估计
    est_chars = max(1, int(max_width_px * 2 / (font.size * 1.2)))

    lines = []
    current = ""
    for ch in text:
        candidate = current + ch
        if font.getlength(candidate) > max_width_px and current:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [text]


# ---------- 单层绘制 ----------

def _draw_layer(base: Image.Image, layer: dict, verbose: bool) -> None:
    text = layer.get("text", "")
    if not text:
        return

    x = int(layer.get("x", 0))
    y = int(layer.get("y", 0))
    anchor = layer.get("anchor") or "mm"
    weight = layer.get("weight") or "Regular"
    size = int(layer.get("size", 32))
    color = _parse_color(layer.get("color", "#000000")) or (0, 0, 0, 255)
    stroke_color = _parse_color(layer.get("stroke_color"))
    stroke_width = int(layer.get("stroke_width", 0) or 0)
    bg = _parse_color(layer.get("bg"))
    bg_padding = int(layer.get("bg_padding", 16))
    line_spacing = float(layer.get("line_spacing", 1.2))
    max_width = layer.get("max_width")
    rotation = float(layer.get("rotation", 0) or 0)
    opacity = float(layer.get("opacity", 1.0))

    font = _load_font(weight, size)

    # 处理多行
    if max_width:
        lines = _wrap_text(text, int(max_width), font)
    else:
        lines = text.split("\n")
    render_text = "\n".join(lines)
    line_h = int(size * line_spacing)

    # 计算文字 bbox
    tmp = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp)
    bbox = tmp_draw.multiline_textbbox(
        (0, 0), render_text, font=font, anchor="la",
        spacing=line_h - size, stroke_width=stroke_width,
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # 透明层(用于旋转/不透明度合成)
    layer_w = text_w + bg_padding * 2 + stroke_width * 2 + 8
    layer_h = text_h + bg_padding * 2 + stroke_width * 2 + 8
    scratch = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scratch)

    # 背景圆角矩形
    if bg:
        sd.rounded_rectangle(
            (0, 0, layer_w - 1, layer_h - 1),
            radius=8,
            fill=bg,
        )

    # 文字
    tx = bg_padding + stroke_width + 4 - bbox[0]
    ty = bg_padding + stroke_width + 4 - bbox[1]
    sd.multiline_text(
        (tx, ty),
        render_text,
        font=font,
        fill=color,
        anchor="la",
        spacing=line_h - size,
        stroke_width=stroke_width,
        stroke_fill=stroke_color or (0, 0, 0, 0),
    )

    # 旋转
    if rotation:
        scratch = scratch.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

    # 不透明度
    if opacity < 1.0:
        alpha = scratch.split()[3].point(lambda a: int(a * opacity))
        scratch.putalpha(alpha)

    # 按 anchor 计算粘贴位置
    anchor_h, anchor_v = anchor[0], anchor[1]
    w, h = scratch.size
    if anchor_h == "l":
        paste_x = x - 4
    elif anchor_h == "r":
        paste_x = x - w + 4
    else:  # m
        paste_x = x - w // 2
    if anchor_v == "t":
        paste_y = y - 4
    elif anchor_v == "b":
        paste_y = y - h + 4
    elif anchor_v in ("s", "d"):  # baseline/descender 近似居中
        paste_y = y - h // 2
    else:  # m, a
        paste_y = y - h // 2

    # 合成到 base
    if base.mode != "RGBA":
        base_rgba = base.convert("RGBA")
        base.paste(Image.alpha_composite(base_rgba, _pad_scratch(scratch, base.size, paste_x, paste_y)).convert(base.mode))
    else:
        padded = _pad_scratch(scratch, base.size, paste_x, paste_y)
        composed = Image.alpha_composite(base, padded)
        base.paste(composed)

    if verbose:
        preview = text if len(text) <= 20 else text[:20] + "…"
        print(f"  · layer: «{preview}» @ ({x},{y}) {weight} {size}px anchor={anchor}")


def _pad_scratch(scratch: Image.Image, size: tuple[int, int], px: int, py: int) -> Image.Image:
    """把 scratch 放到和 base 同尺寸的透明层上,位置 (px,py)。"""
    padded = Image.new("RGBA", size, (0, 0, 0, 0))
    padded.alpha_composite(scratch, dest=(px, py))
    return padded


# ---------- 主流程 ----------

def apply_overlay(base_path: Path, overlay_path: Path, out_path: Path, verbose: bool = False) -> None:
    if not base_path.exists():
        print(f"❌ 底图不存在: {base_path}", file=sys.stderr)
        sys.exit(1)
    if not overlay_path.exists():
        print(f"❌ overlay.json 不存在: {overlay_path}", file=sys.stderr)
        sys.exit(1)

    with overlay_path.open("r", encoding="utf-8") as f:
        spec = json.load(f)

    base = Image.open(base_path).convert("RGBA")

    # 尺寸强制
    target_size = spec.get("size")
    if target_size and tuple(target_size) != base.size:
        base = base.resize(tuple(target_size), Image.Resampling.BICUBIC)
        if verbose:
            print(f"  · resized base to {tuple(target_size)}")

    layers = spec.get("layers", [])
    if verbose:
        print(f"📝 应用 {len(layers)} 个文字层 → {out_path.name}")

    for layer in layers:
        _draw_layer(base, layer, verbose)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "PNG", optimize=True)
    if verbose:
        print(f"✅ 输出: {out_path}")


def _default_out(base_path: Path) -> Path:
    name = base_path.name
    if name.endswith("-raw.png"):
        return base_path.with_name(name[:-len("-raw.png")] + ".png")
    stem = base_path.stem
    return base_path.with_name(f"{stem}-final.png")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在 AI 生成的无字底图上精准叠加中文字(WeWrite T2 工作流)",
    )
    parser.add_argument("base", type=Path, help="底图 PNG(通常以 -raw.png 结尾)")
    parser.add_argument("overlay", type=Path, help="overlay.json 文字层配置")
    parser.add_argument("-o", "--output", type=Path, help="输出 PNG 路径(默认去掉 -raw 后缀)")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印每层详细信息")
    args = parser.parse_args()

    out = args.output or _default_out(args.base)
    apply_overlay(args.base, args.overlay, out, verbose=args.verbose)
    if not args.verbose:
        print(f"✓ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
