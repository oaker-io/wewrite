"""learn_theme.py — extract a WeWrite-compatible theme from a WeChat article URL.

Usage:
    python3 scripts/learn_theme.py <url>          # fetch + analyse live article
    python3 scripts/learn_theme.py --file <path>  # analyse a saved HTML file
"""

import argparse
import colorsys
import re
import sys
from collections import Counter
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 1. Color utilities
# ---------------------------------------------------------------------------

def rgb_to_hex(rgb_str: str) -> str:
    """Convert ``rgb(r,g,b)`` or ``rgba(r,g,b,a)`` to ``#rrggbb``.

    Pass-through for values that already look like hex (lowercased).
    Return the original string unchanged if no pattern matches.
    """
    if not isinstance(rgb_str, str):
        return rgb_str
    s = rgb_str.strip()
    # Already hex
    if re.match(r"^#[0-9a-fA-F]{3,8}$", s):
        return s.lower()
    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)",
        s,
        re.IGNORECASE,
    )
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    return s


def lightness(hex_color: str) -> float:
    """Return HLS lightness (0.0–1.0) for a hex colour string.

    Returns 0.5 for any invalid / non-hex input.
    """
    s = hex_color.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return 0.5
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError:
        return 0.5
    _h, l, _s = colorsys.rgb_to_hls(r, g, b)
    return l


def is_gray(hex_color: str, threshold: int = 30) -> bool:
    """Return True if R, G, B values are all within *threshold* of each other."""
    s = hex_color.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return False
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
    except ValueError:
        return False
    return max(r, g, b) - min(r, g, b) <= threshold


def adjust_lightness(hex_color: str, target_l: float) -> str:
    """Return a new hex colour with lightness set to *target_l* (0.0–1.0)."""
    s = hex_color.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return hex_color
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError:
        return hex_color
    h, _l, sat = colorsys.rgb_to_hls(r, g, b)
    nr, ng, nb = colorsys.hls_to_rgb(h, max(0.0, min(1.0, target_l)), sat)
    return "#{:02x}{:02x}{:02x}".format(
        int(nr * 255), int(ng * 255), int(nb * 255)
    )


def derive_darkmode(colors: dict) -> dict:
    """Derive a dark-mode colour dict from a light-mode *colors* dict.

    Rules
    -----
    background  → #1e1e1e
    text        → lightness set to 0.80
    text_light  → lightness set to 0.60
    primary     → lightness + 0.15, capped at 0.85
    code_bg     → #2d2d2d
    code_color  → #d4d4d4
    quote_bg    → #252525
    quote_border → dark-mode primary
    """
    primary = colors.get("primary", "#2563eb")
    primary_l = lightness(primary)
    dm_primary = adjust_lightness(primary, min(primary_l + 0.15, 0.85))

    dm = {
        "background": "#1e1e1e",
        "text": adjust_lightness(colors.get("text", "#333333"), 0.80),
        "text_light": adjust_lightness(colors.get("text_light", "#666666"), 0.60),
        "primary": dm_primary,
        "code_bg": "#2d2d2d",
        "code_color": "#d4d4d4",
        "quote_bg": "#252525",
        "quote_border": dm_primary,
    }
    return dm


# ---------------------------------------------------------------------------
# 2. HTML fetch and style extraction
# ---------------------------------------------------------------------------

def parse_inline_style(style_str: str) -> dict:
    """Parse ``"color: red; font-size: 16px"`` into ``{"color": "red", "font-size": "16px"}``."""
    result = {}
    if not style_str:
        return result
    for declaration in style_str.split(";"):
        declaration = declaration.strip()
        if ":" not in declaration:
            continue
        prop, _, val = declaration.partition(":")
        result[prop.strip().lower()] = val.strip()
    return result


_TARGET_TAGS = {
    "p", "section", "span", "strong", "em",
    "h1", "h2", "h3", "h4",
    "blockquote", "code", "pre", "img", "a",
}

TEMPLATE_THEME = "professional-clean"
THEMES_DIR = Path(__file__).resolve().parent.parent / "toolkit" / "themes"


def _attach_title(soup, content) -> None:
    """Find the article title in *soup* and stash it on *content*."""
    title_tag = soup.find("h1", class_="rich_media_title") or soup.find(
        "h1", id="activity-name"
    )
    content._wewrite_title = title_tag.get_text(strip=True) if title_tag else ""


def fetch_article(url: str, timeout: int = 20) -> "BeautifulSoup tag":
    """Fetch a WeChat article, return the ``#js_content`` element.

    Delegates to fetch_article.fetch_html() for three-level fetching
    (requests → Playwright → manual fallback).

    The article title is attached as ``content._wewrite_title`` (empty string
    if not found).
    """
    from scripts.fetch_article import fetch_html

    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    content = soup.find(id="js_content")
    if content is None:
        print("Error: #js_content not found.", file=sys.stderr)
        sys.exit(1)

    _attach_title(soup, content)
    return content


def extract_styles(content) -> dict:
    """Iterate all elements in *content*, group inline styles by tag name.

    Returns ``{tag_name: [style_dict, ...], ...}`` for the target tags.
    Only elements that have a non-empty ``style`` attribute are included.
    """
    grouped: dict[str, list[dict]] = {tag: [] for tag in _TARGET_TAGS}
    for elem in content.find_all(True):
        tag = elem.name
        if tag not in _TARGET_TAGS:
            continue
        raw_style = elem.get("style", "")
        if not raw_style:
            continue
        parsed = parse_inline_style(raw_style)
        if parsed:
            grouped[tag].append(parsed)
    return grouped


# ---------------------------------------------------------------------------
# 3. Style analysis
# ---------------------------------------------------------------------------

DEFAULTS = {
    "primary": "#2563eb",
    "secondary": "#3b82f6",
    "text": "#333333",
    "text_light": "#666666",
    "background": "#ffffff",
    "code_bg": "#1e293b",
    "code_color": "#e2e8f0",
    "quote_border": "#2563eb",
    "quote_bg": "#eff6ff",
    "border_radius": "8px",
    "font_size": "16px",
    "line_height": "1.8",
    "letter_spacing": "0px",
    "font_family": (
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
        '"Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", '
        '"Microsoft YaHei", sans-serif'
    ),
    "p_margin": "0 0 16px 0",
}


def most_common_value(style_list: list, prop: str):
    """Return the most common value of CSS *prop* across *style_list*.

    Returns ``None`` if the property does not appear in any dict.
    """
    values = [d[prop] for d in style_list if prop in d and d[prop]]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _parse_px(value: str) -> float | None:
    """Parse a CSS pixel value like ``"16px"`` → 16.0, or return None."""
    if not value:
        return None
    m = re.match(r"([\d.]+)\s*px", value.strip(), re.IGNORECASE)
    return float(m.group(1)) if m else None


def analyze_styles(grouped: dict) -> dict:
    """Analyse the output of :func:`extract_styles` and return a flat theme dict.

    Inferred properties (falling back to DEFAULTS when not found):
    text, text_light, primary, secondary, background,
    font_size, line_height, letter_spacing, font_family, p_margin,
    quote_border, quote_bg, code_bg, code_color, border_radius.
    """
    result = dict(DEFAULTS)  # start with all defaults

    # --- text ------------------------------------------------------------------
    p_styles = grouped.get("p", [])
    raw_text = most_common_value(p_styles, "color")
    if raw_text:
        result["text"] = rgb_to_hex(raw_text)

    # --- text_light ------------------------------------------------------------
    # Collect foreground colours only (not backgrounds) for text_light candidates
    all_colors = []
    for tag_styles in grouped.values():
        for d in tag_styles:
            val = d.get("color")
            if val:
                all_colors.append(rgb_to_hex(val))

    text_light_candidates = [
        c for c in all_colors
        if is_gray(c) and 0.15 < lightness(c) < 0.85 and c != result["text"]
    ]
    if text_light_candidates:
        # Pick the one with the highest lightness
        result["text_light"] = max(text_light_candidates, key=lightness)

    # --- primary (accent color) ------------------------------------------------
    # Collect non-gray colors from strong/section/h1-h3/span; boost colors from
    # elements whose font-size is ≥ 20 px (weight × 5).
    # Exclude the dominant text color so near-black body text never wins.
    accent_tags = {"strong", "section", "h1", "h2", "h3", "span"}
    accent_counter: Counter = Counter()
    for tag in accent_tags:
        for d in grouped.get(tag, []):
            color_val = d.get("color")
            if not color_val:
                continue
            hex_c = rgb_to_hex(color_val)
            if is_gray(hex_c):
                continue
            if hex_c == result["text"]:
                continue
            # Check font-size for boost
            fs = d.get("font-size")
            fs_px = _parse_px(fs) if fs else None
            weight = 5 if (fs_px is not None and fs_px >= 20) else 1
            accent_counter[hex_c] += weight

    if accent_counter:
        sorted_accents = accent_counter.most_common()
        result["primary"] = sorted_accents[0][0]
        # --- secondary ---------------------------------------------------------
        if len(sorted_accents) >= 2:
            result["secondary"] = sorted_accents[1][0]
        else:
            # Derive: primary + 10% lightness, cap 0.90
            primary_l = lightness(result["primary"])
            result["secondary"] = adjust_lightness(
                result["primary"], min(primary_l + 0.10, 0.90)
            )
    else:
        # No accent found — derive secondary from default primary
        primary_l = lightness(result["primary"])
        result["secondary"] = adjust_lightness(
            result["primary"], min(primary_l + 0.10, 0.90)
        )

    # --- background ------------------------------------------------------------
    # Check background-color of the first few <section> elements for high lightness
    for d in (grouped.get("section", []))[:10]:
        bg = d.get("background-color") or d.get("background")
        if bg:
            hex_bg = rgb_to_hex(bg)
            if lightness(hex_bg) > 0.85:
                result["background"] = hex_bg
                break

    # --- typography (from <p>) -------------------------------------------------
    if p_styles:
        fs = most_common_value(p_styles, "font-size")
        if fs:
            result["font_size"] = fs
        lh = most_common_value(p_styles, "line-height")
        if lh:
            result["line_height"] = lh
        ls = most_common_value(p_styles, "letter-spacing")
        if ls:
            result["letter_spacing"] = ls
        margin = most_common_value(p_styles, "margin")
        if margin:
            result["p_margin"] = margin

    # font-family from <span>
    span_styles = grouped.get("span", [])
    ff = most_common_value(span_styles, "font-family")
    if ff:
        result["font_family"] = ff

    # --- quote_border / quote_bg -----------------------------------------------
    # Priority: actual <blockquote> elements first.
    # For section/p: only use a background when a border-left is also present on
    # that element (avoids picking up decorative divider colors).
    bq_border = None
    bq_bg = None

    # Pass 1: blockquote (highest confidence)
    for d in grouped.get("blockquote", []):
        bl = d.get("border-left") or d.get("border-left-color")
        if bl and not bq_border:
            color_match = re.search(r"(rgb[a]?\([^)]+\)|#[0-9a-fA-F]{3,8})", bl)
            if color_match:
                bq_border = rgb_to_hex(color_match.group(1))
        bg = d.get("background-color") or d.get("background")
        if bg and not bq_bg:
            hex_bg = rgb_to_hex(bg)
            if hex_bg not in ("#ffffff", "#000000") and not is_gray(hex_bg, threshold=10):
                bq_bg = hex_bg

    # Pass 2: section/p — only trust backgrounds that co-occur with border-left
    if not bq_border:
        for tag in ("section", "p"):
            for d in grouped.get(tag, []):
                bl = d.get("border-left") or d.get("border-left-color")
                if bl:
                    color_match = re.search(r"(rgb[a]?\([^)]+\)|#[0-9a-fA-F]{3,8})", bl)
                    if color_match and not bq_border:
                        bq_border = rgb_to_hex(color_match.group(1))
                    bg = d.get("background-color") or d.get("background")
                    if bg and not bq_bg:
                        hex_bg = rgb_to_hex(bg)
                        if hex_bg not in ("#ffffff", "#000000") and not is_gray(
                            hex_bg, threshold=10
                        ):
                            bq_bg = hex_bg

    if bq_border:
        result["quote_border"] = bq_border
    else:
        result["quote_border"] = result["primary"]

    if bq_bg:
        result["quote_bg"] = bq_bg
    else:
        # Derive a light tint of primary
        primary_l = lightness(result["primary"])
        result["quote_bg"] = adjust_lightness(result["primary"], min(primary_l + 0.35, 0.95))

    # --- code_bg / code_color --------------------------------------------------
    for tag in ("pre", "code"):
        tag_styles = grouped.get(tag, [])
        bg = most_common_value(tag_styles, "background-color") or most_common_value(
            tag_styles, "background"
        )
        if bg:
            result["code_bg"] = rgb_to_hex(bg)
        color = most_common_value(tag_styles, "color")
        if color:
            result["code_color"] = rgb_to_hex(color)

    # --- border_radius ---------------------------------------------------------
    all_radii = []
    for tag_styles in grouped.values():
        for d in tag_styles:
            br = d.get("border-radius")
            if br:
                all_radii.append(br)
    if all_radii:
        result["border_radius"] = Counter(all_radii).most_common(1)[0][0]

    return result


# ---------------------------------------------------------------------------
# 4. Theme YAML generation
# ---------------------------------------------------------------------------

def _load_template_css() -> str:
    """Load the base_css from the professional-clean template theme."""
    template_path = THEMES_DIR / f"{TEMPLATE_THEME}.yaml"
    with open(template_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["base_css"]


def generate_theme_yaml(name: str, title: str, analyzed: dict) -> str:
    """Generate a complete theme YAML string from analyzed style properties.

    Parameters
    ----------
    name:     Theme identifier (used as filename and --theme reference).
    title:    Article title (used in description).
    analyzed: Dict returned by :func:`analyze_styles`.
    """
    css = _load_template_css()

    # Build colors dict
    colors = {
        "primary":      analyzed.get("primary", "#2563eb"),
        "secondary":    analyzed.get("secondary", "#3b82f6"),
        "text":         analyzed.get("text", "#333333"),
        "text_light":   analyzed.get("text_light", "#666666"),
        "background":   analyzed.get("background", "#ffffff"),
        "code_bg":      analyzed.get("code_bg", "#1e293b"),
        "code_color":   analyzed.get("code_color", "#e2e8f0"),
        "quote_border": analyzed.get("quote_border", "#2563eb"),
        "quote_bg":     analyzed.get("quote_bg", "#eff6ff"),
        "border_radius": analyzed.get("border_radius", "8px"),
    }

    # Replace template colors in CSS
    css = css.replace("#2563eb", colors["primary"])
    css = css.replace("#3b82f6", colors["secondary"])
    css = css.replace("#333333", colors["text"])
    css = css.replace("#666666", colors["text_light"])
    css = css.replace("#1e293b", colors["code_bg"])
    css = css.replace("#e2e8f0", colors["code_color"])
    css = css.replace("#eff6ff", colors["quote_bg"])

    # Replace typography via regex
    font_size   = analyzed.get("font_size", "16px")
    line_height = analyzed.get("line_height", "1.8")
    font_family = analyzed.get("font_family",
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
        '"Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", '
        '"Microsoft YaHei", sans-serif')
    p_margin    = analyzed.get("p_margin", "12px 0")
    border_radius = colors["border_radius"]

    # body font-size
    css = re.sub(
        r"(body\s*\{[^}]*font-size:\s*)[\d.]+px",
        lambda m: m.group(1) + font_size,
        css,
        flags=re.DOTALL,
    )
    # body line-height
    css = re.sub(
        r"(body\s*\{[^}]*line-height:\s*)[\d.]+",
        lambda m: m.group(1) + line_height,
        css,
        flags=re.DOTALL,
    )
    # body font-family (replace the quoted chain)
    css = re.sub(
        r'(body\s*\{[^}]*font-family:\s*)[^;]+;',
        lambda m: m.group(1) + font_family + ";",
        css,
        flags=re.DOTALL,
    )
    # p line-height
    css = re.sub(
        r'(p\s*\{[^}]*line-height:\s*)[\d.]+',
        lambda m: m.group(1) + line_height,
        css,
        flags=re.DOTALL,
    )
    # p margin
    css = re.sub(
        r'(p\s*\{[^}]*margin:\s*)[^;]+;',
        lambda m: m.group(1) + p_margin + ";",
        css,
        flags=re.DOTALL,
    )
    # li line-height (match p line-height)
    css = re.sub(
        r'(li\s*\{[^}]*line-height:\s*)[\d.]+',
        lambda m: m.group(1) + line_height,
        css,
        flags=re.DOTALL,
    )
    # border-radius: 8px and border-radius: 4px
    css = css.replace("border-radius: 8px", f"border-radius: {border_radius}")
    css = css.replace("border-radius: 4px", f"border-radius: {border_radius}")

    # Derive dark mode
    darkmode = derive_darkmode(colors)

    # Description
    if title:
        description = f"从「{title}」学习的排版主题"
    else:
        description = f"Learned theme: {name}"

    # Build theme data
    colors_with_dark = dict(colors)
    colors_with_dark["darkmode"] = darkmode

    theme_data = {
        "name":        name,
        "description": description,
        "colors":      colors_with_dark,
        "base_css":    css,
    }

    return yaml.dump(theme_data, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI entry point / smoke test
# ---------------------------------------------------------------------------

def _load_from_file(path: str):
    """Load #js_content from a local HTML file (for smoke testing)."""
    with open(path, encoding="utf-8") as fh:
        soup = BeautifulSoup(fh.read(), "html.parser")
    content = soup.find(id="js_content")
    if content is None:
        print(f"Error: #js_content not found in {path}", file=sys.stderr)
        sys.exit(1)
    _attach_title(soup, content)
    return content


def main():
    parser = argparse.ArgumentParser(
        description="Learn a WeChat formatting theme from an article URL.",
    )
    parser.add_argument("url", help="WeChat article URL (https://mp.weixin.qq.com/s/...)")
    parser.add_argument("--name", required=True, help="Theme name (used as filename and reference)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: toolkit/themes/)")
    args = parser.parse_args()

    # Validate name: only letters, digits, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", args.name):
        print("Error: --name must contain only letters, digits, hyphens, and underscores.", file=sys.stderr)
        raise SystemExit(1)

    output_dir = Path(args.output_dir) if args.output_dir else THEMES_DIR
    output_path = output_dir / f"{args.name}.yaml"

    if output_path.exists():
        print(f"Warning: {output_path} already exists, will be overwritten.", file=sys.stderr)

    # Fetch
    print("Fetching article...")
    content = fetch_article(args.url)
    title = getattr(content, "_wewrite_title", "")
    if title:
        print(f"Title: {title}")

    # Extract
    grouped = extract_styles(content)
    styled_count = sum(len(v) for v in grouped.values())
    print(f"Extracted {styled_count} styled elements.")

    # Analyze
    analyzed = analyze_styles(grouped)

    # Generate & write
    theme_yaml = generate_theme_yaml(args.name, title, analyzed)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(theme_yaml, encoding="utf-8")

    # Report
    print()
    print(f"Learned theme from: {title or args.url}")
    print(f"  text:       {analyzed['text']}")
    print(f"  text_light: {analyzed['text_light']}")
    print(f"  primary:    {analyzed['primary']}")
    print(f"  secondary:  {analyzed['secondary']}")
    print(f"  background: {analyzed['background']}")
    print(f"  font:       {analyzed['font_family'][:50]}")
    print(f"  size:       {analyzed['font_size']} / line-height {analyzed['line_height']} / spacing {analyzed['letter_spacing']}")
    print()
    print(f"Theme saved → {output_path}")
    print(f"Use it:  python3 toolkit/cli.py preview article.md --theme {args.name}")
    print(f"Or set:  theme: {args.name}  in style.yaml")


if __name__ == "__main__":
    main()
