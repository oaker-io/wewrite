"""
:::author-card container preprocessor · Python port of md2wx's preprocessor.ts

Color palette sourced from VoltAgent/awesome-design-md · design-md/claude
(warm terracotta accent + parchment editorial · Claude/Anthropic brand).

Used by:
- WeWrite's native `converter.py` (for --engine native)
- WeWrite's `converter_md2wx.py` (before HTTP POST to aipickgold)

Kept as standalone module so both converters import the same logic;
the TypeScript twin lives at md2wx/skill/src/preprocessor.ts.
"""

from __future__ import annotations

import html
import json
import re

# --- Claude brand palette(single source of truth)---

_CLAUDE = {
    "parchment":    "#f5f4ed",
    "ivory":        "#faf9f5",
    "white":        "#ffffff",
    "warm_sand":    "#e8e6dc",
    "near_black":   "#141413",
    "charcoal_warm":"#4d4c48",
    "olive_gray":   "#5e5d59",
    "stone_gray":   "#87867f",
    "border_cream": "#f0eee6",
    "border_warm":  "#e8e6dc",
    "terracotta":   "#c96442",
    "coral":        "#d97757",
}

_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, \"Segoe UI\", "
    "\"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", sans-serif"
)

# Element-level inline style tokens
_S = {
    "card": "; ".join([
        "margin: 32px 0",
        "padding: 24px",
        f"background: {_CLAUDE['ivory']}",
        f"border: 1px solid {_CLAUDE['border_cream']}",
        "border-radius: 16px",
        f"font-family: {_FONT_STACK}",
        f"color: {_CLAUDE['charcoal_warm']}",
        "line-height: 1.6",
    ]),
    "header": "display: flex; align-items: center; gap: 16px",
    "avatar": "; ".join([
        "width: 56px",
        "height: 56px",
        "border-radius: 50%",
        "object-fit: cover",
        f"border: 1px solid {_CLAUDE['border_warm']}",
        "flex-shrink: 0",
    ]),
    "avatar_fallback": "; ".join([
        "width: 56px",
        "height: 56px",
        "border-radius: 50%",
        f"background: {_CLAUDE['terracotta']}",
        f"color: {_CLAUDE['ivory']}",
        "display: inline-flex",
        "align-items: center",
        "justify-content: center",
        "font-size: 22px",
        "font-weight: 600",
        "flex-shrink: 0",
    ]),
    "name": "; ".join([
        "margin: 0 0 4px 0",
        "font-size: 18px",
        "font-weight: 700",
        f"color: {_CLAUDE['near_black']}",
        "line-height: 1.3",
    ]),
    "tagline": "; ".join([
        "margin: 0",
        "font-size: 13px",
        f"color: {_CLAUDE['stone_gray']}",
        "line-height: 1.5",
    ]),
    "bio": "; ".join([
        "margin: 20px 0 16px 0",
        "font-size: 15px",
        f"color: {_CLAUDE['charcoal_warm']}",
        "line-height: 1.75",
    ]),
    "tags_wrap": "margin: 12px 0 0 0; line-height: 2.2",
    "chip": "; ".join([
        "display: inline-block",
        "margin: 0 8px 8px 0",
        "padding: 4px 14px",
        f"background: {_CLAUDE['warm_sand']}",
        f"color: {_CLAUDE['terracotta']}",
        "border-radius: 999px",
        "font-size: 13px",
        "font-weight: 500",
        "letter-spacing: 0.2px",
    ]),
    "divider": "; ".join([
        "margin: 20px 0 16px 0",
        "height: 1px",
        f"background: {_CLAUDE['border_warm']}",
        "border: 0",
    ]),
    "footer": "; ".join([
        "margin: 0",
        "font-size: 13px",
        f"color: {_CLAUDE['stone_gray']}",
        "line-height: 1.6",
    ]),
}


def _parse_block(raw: str) -> dict:
    """YAML-lite:key: value 每行一对;tags 支持 [a, b] 或 a, b。"""
    out = {}
    for line in raw.split("\n"):
        m = re.match(
            r"^\s*(name|avatar|tagline|bio|tags|footer)\s*:\s*(.*?)\s*$",
            line,
            re.IGNORECASE,
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


def _render(fields: dict) -> str:
    name = html.escape(fields.get("name") or "匿名作者")
    tagline = html.escape(fields.get("tagline") or "")
    bio = html.escape(fields.get("bio") or "")
    avatar = (fields.get("avatar") or "").strip()
    footer = html.escape(fields.get("footer") or "")
    tags = [html.escape(t) for t in (fields.get("tags") or [])]

    if avatar:
        avatar_html = (
            f'<img src="{html.escape(avatar)}" alt="{name}" '
            f'style="{_S["avatar"]}"/>'
        )
    else:
        avatar_html = (
            f'<span style="{_S["avatar_fallback"]}">{name[:1]}</span>'
        )

    header = (
        f'<section style="{_S["header"]}">'
        f'{avatar_html}'
        f'<section style="min-width:0">'
        f'<p style="{_S["name"]}">{name}</p>'
        + (f'<p style="{_S["tagline"]}">{tagline}</p>' if tagline else "")
        + f'</section></section>'
    )

    bio_html = f'<p style="{_S["bio"]}">{bio}</p>' if bio else ""

    if tags:
        chips = "".join(
            f'<span style="{_S["chip"]}">{t}</span>' for t in tags
        )
        tags_html = f'<section style="{_S["tags_wrap"]}">{chips}</section>'
    else:
        tags_html = ""

    if footer:
        footer_html = (
            f'<hr style="{_S["divider"]}"/>'
            f'<p style="{_S["footer"]}">{footer}</p>'
        )
    else:
        footer_html = ""

    return (
        f'<section style="{_S["card"]}">'
        f'{header}{bio_html}{tags_html}{footer_html}'
        f'</section>'
    )


# Multiline `:::author-card\n...\n:::` → inline-style HTML
_RE_CONTAINER = re.compile(
    r"^:::author-card\s*\r?\n([\s\S]*?)\r?\n:::[ \t]*$",
    re.MULTILINE,
)


def preprocess_author_card(markdown: str) -> str:
    """Replace all :::author-card blocks in markdown with inline HTML."""
    def sub(match):
        fields = _parse_block(match.group(1))
        return _render(fields)
    return _RE_CONTAINER.sub(sub, markdown)
