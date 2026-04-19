"""
:::author-card container preprocessor · Python port of md2wx's preprocessor.ts

Supports 8 card-style presets, each with its own palette + gradients.
Themes (md2wx server themes + WeWrite native themes) are auto-mapped to
their matching style. Users can override via `style: <id>` inside the block.

Used by:
- WeWrite's native `converter.py` (--engine native)
- WeWrite's `converter_md2wx.py` (--engine md2wx · before HTTP POST)

TypeScript twin: md2wx/skill/src/preprocessor.ts (kept in sync).
"""

from __future__ import annotations

import html
import json
import re

# =================================================================
# 8 card-style presets · complete palette tokens
# =================================================================

STYLES = {
    # 1 · Editorial warmth (default) — Claude DESIGN.md
    "claude-warm": {
        "bg_start": "#faf9f5", "bg_end": "#f5f4ed",
        "strip_start": "#c96442", "strip_mid": "#d97757", "strip_end": "#c96442",
        "avatar_start": "#c96442", "avatar_end": "#d97757", "avatar_text": "#faf9f5",
        "text_primary": "#141413", "text_secondary": "#4d4c48", "text_tertiary": "#87867f",
        "border": "#f0eee6", "chip_bg": "#e8e6dc", "chip_text": "#c96442",
        "shadow_rgba": "201, 100, 66",
    },
    # 2 · Corporate depth — for navy/blue themes
    "ocean-deep": {
        "bg_start": "#f7fafc", "bg_end": "#e2e8f0",
        "strip_start": "#1e3a5f", "strip_mid": "#2c5282", "strip_end": "#1e3a5f",
        "avatar_start": "#1e3a5f", "avatar_end": "#2c5282", "avatar_text": "#f7fafc",
        "text_primary": "#1a202c", "text_secondary": "#2d3748", "text_tertiary": "#718096",
        "border": "#e2e8f0", "chip_bg": "#edf2f7", "chip_text": "#2c5282",
        "shadow_rgba": "30, 58, 95",
    },
    # 3 · Luxury minimalism
    "minimal-luxe": {
        "bg_start": "#fdfbf5", "bg_end": "#f5f1e8",
        "strip_start": "#b8860b", "strip_mid": "#d4a843", "strip_end": "#b8860b",
        "avatar_start": "#b8860b", "avatar_end": "#d4a843", "avatar_text": "#fdfbf5",
        "text_primary": "#2a2a2a", "text_secondary": "#5a5a5a", "text_tertiary": "#9e9a8f",
        "border": "#e8e0c8", "chip_bg": "#fdfbf5", "chip_text": "#b8860b",
        "shadow_rgba": "184, 134, 11",
    },
    # 4 · Bold energy
    "pop-vibrant": {
        "bg_start": "#ffffff", "bg_end": "#fff5f5",
        "strip_start": "#e63226", "strip_mid": "#f5b700", "strip_end": "#e63226",
        "avatar_start": "#e63226", "avatar_end": "#f5b700", "avatar_text": "#ffffff",
        "text_primary": "#1a1a1a", "text_secondary": "#4a4a4a", "text_tertiary": "#888888",
        "border": "#fed7d7", "chip_bg": "#fff5f5", "chip_text": "#e63226",
        "shadow_rgba": "230, 50, 38",
    },
    # 5 · Zen freshness
    "mint-fresh": {
        "bg_start": "#f0fdf4", "bg_end": "#d1fae5",
        "strip_start": "#10b981", "strip_mid": "#34d399", "strip_end": "#10b981",
        "avatar_start": "#10b981", "avatar_end": "#34d399", "avatar_text": "#f0fdf4",
        "text_primary": "#064e3b", "text_secondary": "#065f46", "text_tertiary": "#047857",
        "border": "#a7f3d0", "chip_bg": "#ecfdf5", "chip_text": "#065f46",
        "shadow_rgba": "16, 185, 129",
    },
    # 6 · Creative dream
    "lavender-soft": {
        "bg_start": "#faf5ff", "bg_end": "#f3e8ff",
        "strip_start": "#8b5cf6", "strip_mid": "#a78bfa", "strip_end": "#8b5cf6",
        "avatar_start": "#8b5cf6", "avatar_end": "#c4b5fd", "avatar_text": "#faf5ff",
        "text_primary": "#4c1d95", "text_secondary": "#5b21b6", "text_tertiary": "#7c3aed",
        "border": "#e9d5ff", "chip_bg": "#f3e8ff", "chip_text": "#7c3aed",
        "shadow_rgba": "139, 92, 246",
    },
    # 7 · Warm glow
    "sunset-glow": {
        "bg_start": "#fffbeb", "bg_end": "#fef3c7",
        "strip_start": "#f59e0b", "strip_mid": "#fbbf24", "strip_end": "#f59e0b",
        "avatar_start": "#f59e0b", "avatar_end": "#fbbf24", "avatar_text": "#fffbeb",
        "text_primary": "#78350f", "text_secondary": "#92400e", "text_tertiary": "#b45309",
        "border": "#fde68a", "chip_bg": "#fef9e7", "chip_text": "#b45309",
        "shadow_rgba": "245, 158, 11",
    },
    # 8 · Neon dark (cyber themes, bold-navy)
    "cyber-dark": {
        "bg_start": "#0f172a", "bg_end": "#1e293b",
        "strip_start": "#22c55e", "strip_mid": "#06b6d4", "strip_end": "#22c55e",
        "avatar_start": "#22c55e", "avatar_end": "#06b6d4", "avatar_text": "#0f172a",
        "text_primary": "#f1f5f9", "text_secondary": "#cbd5e1", "text_tertiary": "#94a3b8",
        "border": "#334155", "chip_bg": "#1e293b", "chip_text": "#22c55e",
        "shadow_rgba": "34, 197, 94",
    },
}

# =================================================================
# Theme → style mapping
# md2wx server themes (50) + WeWrite native themes (16)
# =================================================================

THEME_TO_STYLE = {
    # --- md2wx server themes (50) ---
    # General
    "default": "claude-warm", "bytedance": "ocean-deep", "apple": "minimal-luxe",
    "sports": "pop-vibrant", "chinese": "pop-vibrant", "cyber": "cyber-dark",
    "wechat-native": "claude-warm", "nyt-classic": "ocean-deep",
    "github-readme": "minimal-luxe", "sspai-red": "pop-vibrant",
    "mint-fresh": "mint-fresh", "sunset-amber": "sunset-glow",
    "ink-minimal": "minimal-luxe", "lavender-dream": "lavender-soft",
    "coffee-house": "claude-warm", "bauhaus-primary": "pop-vibrant",
    "xiaomo": "lavender-soft", "shikexin": "pop-vibrant",
    # Minimal series
    "minimal-gold": "minimal-luxe", "minimal-green": "mint-fresh",
    "minimal-blue": "ocean-deep", "minimal-orange": "sunset-glow",
    "minimal-red": "pop-vibrant", "minimal-navy": "ocean-deep",
    "minimal-gray": "minimal-luxe", "minimal-sky": "ocean-deep",
    # Focus series
    "focus-gold": "minimal-luxe", "focus-green": "mint-fresh",
    "focus-blue": "ocean-deep", "focus-orange": "sunset-glow",
    "focus-red": "pop-vibrant", "focus-navy": "ocean-deep",
    "focus-gray": "minimal-luxe", "focus-sky": "ocean-deep",
    # Elegant series
    "elegant-gold": "minimal-luxe", "elegant-green": "mint-fresh",
    "elegant-blue": "ocean-deep", "elegant-orange": "sunset-glow",
    "elegant-red": "pop-vibrant", "elegant-navy": "ocean-deep",
    "elegant-gray": "minimal-luxe", "elegant-sky": "ocean-deep",
    # Bold series
    "bold-gold": "pop-vibrant", "bold-green": "pop-vibrant",
    "bold-blue": "pop-vibrant", "bold-orange": "pop-vibrant",
    "bold-red": "pop-vibrant", "bold-navy": "cyber-dark",
    "bold-gray": "pop-vibrant", "bold-sky": "pop-vibrant",
    # --- WeWrite native themes (16) ---
    "professional-clean": "ocean-deep",
    "minimal": "minimal-luxe",
    "newspaper": "ocean-deep",
    "tech-modern": "ocean-deep",
    "bytedance": "ocean-deep",  # dup w/ server, same map
    "github": "minimal-luxe",
    "warm-editorial": "claude-warm",
    "sspai": "pop-vibrant",
    "ink": "minimal-luxe",
    "elegant-rose": "lavender-soft",
    "bold-navy": "cyber-dark",
    "minimal-gold": "minimal-luxe",  # dup
    "bold-green": "pop-vibrant",  # dup
    "bauhaus": "pop-vibrant",
    "focus-red": "pop-vibrant",  # dup
    "midnight": "cyber-dark",
}

DEFAULT_STYLE = "claude-warm"

# =================================================================
# Style resolution + token generation
# =================================================================

_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, \"Segoe UI\", "
    "\"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", sans-serif"
)


def _resolve_style(override=None, theme_id=None):
    if override and override in STYLES:
        return STYLES[override]
    if theme_id and theme_id in THEME_TO_STYLE:
        key = THEME_TO_STYLE[theme_id]
        if key in STYLES:
            return STYLES[key]
    return STYLES[DEFAULT_STYLE]


def _build_tokens(s):
    bg = f"linear-gradient(135deg, {s['bg_start']} 0%, {s['bg_end']} 100%)"
    strip = (
        f"linear-gradient(90deg, {s['strip_start']} 0%, "
        f"{s['strip_mid']} 50%, {s['strip_end']} 100%)"
    )
    avatar_grad = (
        f"linear-gradient(135deg, {s['avatar_start']} 0%, "
        f"{s['avatar_end']} 100%)"
    )
    shadow = f"0 2px 8px rgba({s['shadow_rgba']}, 0.15)"
    return {
        "card": "; ".join([
            "margin: 32px 0",
            f"background: {bg}",
            f"border: 1px solid {s['border']}",
            "border-radius: 16px",
            f"font-family: {_FONT_STACK}",
            f"color: {s['text_secondary']}",
            "line-height: 1.6",
            "overflow: hidden",
        ]),
        "brand_strip": f"height: 3px; background: {strip}",
        "content": "padding: 24px",
        "header": "display: flex; align-items: center; gap: 16px",
        "avatar": "; ".join([
            "width: 56px", "height: 56px", "border-radius: 50%",
            "object-fit: cover",
            f"border: 1px solid {s['border']}",
            "flex-shrink: 0",
        ]),
        "avatar_fallback": "; ".join([
            "width: 56px", "height: 56px", "border-radius: 50%",
            f"background: {avatar_grad}",
            f"color: {s['avatar_text']}",
            "display: inline-flex", "align-items: center", "justify-content: center",
            "font-size: 22px", "font-weight: 600", "flex-shrink: 0",
            f"box-shadow: {shadow}",
        ]),
        "name": "; ".join([
            "margin: 0 0 4px 0", "font-size: 18px", "font-weight: 700",
            f"color: {s['text_primary']}", "line-height: 1.3",
        ]),
        "tagline": "; ".join([
            "margin: 0", "font-size: 13px",
            f"color: {s['text_tertiary']}", "line-height: 1.5",
        ]),
        "bio": "; ".join([
            "margin: 20px 0 16px 0", "font-size: 15px",
            f"color: {s['text_secondary']}", "line-height: 1.75",
        ]),
        "tags_wrap": "margin: 12px 0 0 0; line-height: 2.2",
        "chip": "; ".join([
            "display: inline-block", "margin: 0 8px 8px 0", "padding: 4px 14px",
            f"background: {s['chip_bg']}",
            f"color: {s['chip_text']}",
            "border-radius: 999px",
            "font-size: 13px", "font-weight: 500", "letter-spacing: 0.2px",
        ]),
        "divider": "; ".join([
            "margin: 20px 0 16px 0", "height: 1px",
            f"background: {s['border']}",
            "border: 0",
        ]),
        "footer": "; ".join([
            "margin: 0", "font-size: 13px",
            f"color: {s['text_tertiary']}", "line-height: 1.6",
        ]),
    }


# =================================================================
# YAML-lite + render
# =================================================================

def _parse_block(raw):
    out = {}
    for line in raw.split("\n"):
        m = re.match(
            r"^\s*(name|avatar|tagline|bio|tags|footer|style)\s*:\s*(.*?)\s*$",
            line, re.IGNORECASE,
        )
        if not m:
            continue
        key = m.group(1).lower()
        raw_val = m.group(2)
        if key == "tags":
            tags = []
            if raw_val.startswith("["):
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, list):
                        tags = [str(t) for t in parsed]
                except json.JSONDecodeError:
                    pass
            if not tags:
                tags = [
                    t.strip().strip("'\"")
                    for t in raw_val.strip("[]").split(",")
                    if t.strip()
                ]
            out["tags"] = tags
        else:
            out[key] = raw_val.strip("'\"")
    return out


def _render(fields, theme_id=None):
    style = _resolve_style(fields.get("style"), theme_id)
    T = _build_tokens(style)

    name = html.escape(fields.get("name") or "匿名作者")
    tagline = html.escape(fields.get("tagline") or "")
    bio = html.escape(fields.get("bio") or "")
    avatar = (fields.get("avatar") or "").strip()
    footer = html.escape(fields.get("footer") or "")
    tags = [html.escape(t) for t in (fields.get("tags") or [])]

    if avatar:
        avatar_html = (
            f'<img src="{html.escape(avatar)}" alt="{name}" '
            f'style="{T["avatar"]}"/>'
        )
    else:
        avatar_html = (
            f'<span style="{T["avatar_fallback"]}">{name[:1]}</span>'
        )

    header = (
        f'<section style="{T["header"]}">'
        f'{avatar_html}'
        f'<section style="min-width:0">'
        f'<p style="{T["name"]}">{name}</p>'
        + (f'<p style="{T["tagline"]}">{tagline}</p>' if tagline else "")
        + f'</section></section>'
    )

    bio_html = f'<p style="{T["bio"]}">{bio}</p>' if bio else ""

    if tags:
        chips = "".join(f'<span style="{T["chip"]}">{t}</span>' for t in tags)
        tags_html = f'<section style="{T["tags_wrap"]}">{chips}</section>'
    else:
        tags_html = ""

    if footer:
        footer_html = (
            f'<hr style="{T["divider"]}"/>'
            f'<p style="{T["footer"]}">{footer}</p>'
        )
    else:
        footer_html = ""

    return (
        f'<section style="{T["card"]}">'
        f'<section style="{T["brand_strip"]}"></section>'
        f'<section style="{T["content"]}">'
        f'{header}{bio_html}{tags_html}{footer_html}'
        f'</section></section>'
    )


_RE_CONTAINER = re.compile(
    r"^:::author-card\s*\r?\n([\s\S]*?)\r?\n:::[ \t]*$",
    re.MULTILINE,
)


def preprocess_author_card(markdown, theme_id=None):
    """Replace :::author-card blocks with inline HTML.

    :param theme_id: optional server/native theme id; auto-maps to a card style.
    """
    def sub(match):
        fields = _parse_block(match.group(1))
        return _render(fields, theme_id)
    return _RE_CONTAINER.sub(sub, markdown)
