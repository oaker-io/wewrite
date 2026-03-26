"""
Markdown to WeChat-compatible HTML converter.

Forked from wechat_article_skills/scripts/markdown_to_html.py,
adapted for YAML-driven themes and agent integration.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import markdown
from bs4 import BeautifulSoup

from theme import Theme, load_theme, get_inline_css_rules


@dataclass
class ConvertResult:
    """Result of a Markdown → WeChat HTML conversion."""

    html: str  # WeChat-compatible inline-style HTML (body content only)
    title: str  # Extracted H1 title
    digest: str  # Auto-generated summary (first 120 chars)
    images: list[str] = field(default_factory=list)  # Image references found


class WeChatConverter:
    """Convert Markdown to WeChat-compatible inline-style HTML."""

    def __init__(self, theme: Optional[Theme] = None, theme_name: str = "professional-clean"):
        if theme is not None:
            self._theme = theme
        else:
            self._theme = load_theme(theme_name)
        self._css_rules = get_inline_css_rules(self._theme)

    def convert(self, markdown_text: str) -> ConvertResult:
        """
        Convert Markdown text to WeChat-compatible HTML.

        Returns ConvertResult with:
          - html: inline-style HTML (body content only, no <html>/<head> wrapper)
          - title: extracted H1 title (or empty string)
          - digest: first 120 characters of plain text
          - images: list of image src references
        """
        title = self._extract_title(markdown_text)
        markdown_text = self._strip_h1(markdown_text)

        # Parse Markdown → HTML
        html = self._markdown_to_html(markdown_text)

        # Enhance code blocks (add data-lang attribute)
        html = self._enhance_code_blocks(html)

        # Process images (ensure responsive styling)
        html, images = self._process_images(html)

        # Apply inline CSS from theme
        html = self._apply_inline_styles(html)

        # Apply WeChat compatibility fixes
        html = self._apply_wechat_fixes(html)

        # Generate digest from plain text
        digest = self._generate_digest(html)

        return ConvertResult(html=html, title=title, digest=digest, images=images)

    def convert_file(self, input_path: str) -> ConvertResult:
        """Convert a Markdown file."""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        text = path.read_text(encoding="utf-8")
        return self.convert(text)

    # -- internal methods --

    def _extract_title(self, text: str) -> str:
        """Extract the first H1 title from Markdown text."""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped[2:].strip()
        return ""

    def _strip_h1(self, text: str) -> str:
        """Remove H1 lines — WeChat has a separate title field."""
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _markdown_to_html(self, text: str) -> str:
        """Parse Markdown to HTML using python-markdown with extensions."""
        extensions = [
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.nl2br",
            "markdown.extensions.sane_lists",
            "markdown.extensions.codehilite",
        ]
        extension_configs = {
            "codehilite": {
                "linenums": False,
                "guess_lang": True,
                "noclasses": True,  # Inline syntax highlight styles
            }
        }
        md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
        return md.convert(text)

    def _enhance_code_blocks(self, html: str) -> str:
        """Add data-lang attribute to <pre> elements for language labeling."""
        soup = BeautifulSoup(html, "html.parser")
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                for cls in code.get("class", []):
                    if cls.startswith("language-"):
                        pre["data-lang"] = cls.replace("language-", "")
                        break
        return str(soup)

    def _process_images(self, html: str) -> tuple[str, list[str]]:
        """Extract image references and ensure responsive styling."""
        soup = BeautifulSoup(html, "html.parser")
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src:
                images.append(src)
            # Ensure responsive image styles
            existing = img.get("style", "")
            if "max-width" not in existing:
                additions = "max-width: 100%; height: auto; display: block; margin: 24px auto"
                img["style"] = f"{existing}; {additions}" if existing else additions
        return str(soup), images

    def _apply_inline_styles(self, html: str) -> str:
        """Apply theme CSS rules as inline styles on matching elements."""
        soup = BeautifulSoup(html, "html.parser")

        for selector, styles in self._css_rules.items():
            # Skip body — we don't wrap in body tag
            if selector.strip() == "body":
                continue

            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for elem in elements:
                existing = elem.get("style", "")
                style_dict = {}

                # Parse existing inline styles
                if existing:
                    for item in existing.split(";"):
                        if ":" in item:
                            key, val = item.split(":", 1)
                            style_dict[key.strip()] = val.strip()

                # Add theme styles (existing styles take precedence)
                for prop, val in styles.items():
                    if prop not in style_dict:
                        style_dict[prop] = val

                elem["style"] = "; ".join(f"{k}: {v}" for k, v in style_dict.items())

        return str(soup)

    def _apply_wechat_fixes(self, html: str) -> str:
        """
        Apply WeChat-specific compatibility fixes:
        1. Force explicit color on every <p> tag
        2. Ensure code blocks preserve whitespace
        """
        soup = BeautifulSoup(html, "html.parser")
        text_color = self._theme.colors.get("text", "#333333")

        # Fix 1: Ensure all <p> tags have explicit color
        for p in soup.find_all("p"):
            style = p.get("style", "")
            if "color" not in style:
                p["style"] = f"{style}; color: {text_color}" if style else f"color: {text_color}"

        # Fix 2: Ensure <pre> has whitespace preservation
        for pre in soup.find_all("pre"):
            style = pre.get("style", "")
            if "white-space" not in style:
                pre["style"] = f"{style}; white-space: pre-wrap; word-wrap: break-word" if style else "white-space: pre-wrap; word-wrap: break-word"

        return str(soup)

    def _generate_digest(self, html: str, max_bytes: int = 120) -> str:
        """Generate a digest that fits within WeChat's byte limit (120 bytes UTF-8)."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        # Truncate to fit within max_bytes (UTF-8)
        ellipsis = "..."
        ellipsis_bytes = len(ellipsis.encode("utf-8"))
        target_bytes = max_bytes - ellipsis_bytes

        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text

        # Truncate at valid UTF-8 boundary
        truncated = encoded[:target_bytes].decode("utf-8", errors="ignore").rstrip()
        return truncated + ellipsis


def preview_html(body_html: str, theme: Theme) -> str:
    """
    Wrap body content in a full HTML document for browser preview.
    This is only for local preview — NOT for WeChat publishing.
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview</title>
    <style>
{theme.base_css}
    </style>
</head>
<body>
    {body_html}
</body>
</html>"""
