"""
Theme system for WeWrite.

Loads YAML theme definitions and provides CSS parsing utilities
for the inline style converter.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cssutils
import yaml

# Suppress cssutils warnings (it's very noisy about non-standard properties)
cssutils.log.setLevel(logging.CRITICAL)


@dataclass
class Theme:
    """A theme definition with colors and base CSS."""

    name: str
    description: str
    base_css: str
    colors: dict = field(default_factory=dict)


def _default_themes_dir() -> str:
    """Return the themes/ directory relative to this file."""
    return str(Path(__file__).parent / "themes")


def load_theme(name: str, themes_dir: str = None) -> Theme:
    """
    Load a theme by name from a YAML file.

    Args:
        name: Theme name (without .yaml extension).
        themes_dir: Directory containing theme YAML files.
                    Defaults to themes/ relative to this file.

    Returns:
        A Theme object.

    Raises:
        FileNotFoundError: If the theme YAML file does not exist.
        ValueError: If the YAML is malformed or missing required fields.
    """
    if themes_dir is None:
        themes_dir = _default_themes_dir()

    theme_path = os.path.join(themes_dir, f"{name}.yaml")
    if not os.path.exists(theme_path):
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    with open(theme_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid theme file: {theme_path}")

    required = ("name", "description", "base_css", "colors")
    for key in required:
        if key not in data:
            raise ValueError(f"Theme file missing required field '{key}': {theme_path}")

    theme = Theme(
        name=data["name"],
        description=data["description"],
        base_css=data["base_css"],
        colors=data.get("colors", {}),
    )
    # Attach raw data for extra fields (aigc_footer, css_randomize, etc.)
    theme._raw_data = data
    return theme


def list_themes(themes_dir: str = None) -> list[str]:
    """
    List available theme names.

    Args:
        themes_dir: Directory containing theme YAML files.
                    Defaults to themes/ relative to this file.

    Returns:
        Sorted list of theme names (without .yaml extension).
    """
    if themes_dir is None:
        themes_dir = _default_themes_dir()

    if not os.path.isdir(themes_dir):
        return []

    names = []
    for filename in os.listdir(themes_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            names.append(filename.rsplit(".", 1)[0])

    return sorted(names)


def _resolve_css_variables(css_text: str, colors: dict) -> str:
    """
    Replace var(--xxx) references in CSS with actual color values.

    Supports var(--primary), var(--secondary), etc. based on the
    colors dict keys. The CSS variable name is mapped by stripping
    the leading --.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        # Strip leading -- prefix
        key = var_name.lstrip("-")
        # Also try with hyphens converted to underscores
        key_underscore = key.replace("-", "_")
        if key in colors:
            return str(colors[key])
        if key_underscore in colors:
            return str(colors[key_underscore])
        # Return original if not found
        return match.group(0)

    return re.sub(r"var\(\s*--([a-zA-Z0-9_-]+)\s*\)", replacer, css_text)


def _is_simple_selector(selector: str) -> bool:
    """
    Check if a selector is simple enough for inline styling.

    Rejects pseudo-classes, pseudo-elements, media queries,
    and complex combinators.
    """
    selector = selector.strip()

    # Reject if contains any of these characters
    reject_chars = (":", "@", ">", "+", "~", "[", "*")
    for ch in reject_chars:
        if ch in selector:
            return False

    return True


def get_inline_css_rules(theme: Theme) -> dict[str, dict[str, str]]:
    """
    Parse a theme's base_css into a selector -> {property: value} dict.

    This resolves CSS variable references using theme.colors, then
    parses the CSS with cssutils. Only simple selectors are included
    (no pseudo-classes, pseudo-elements, media queries, or complex
    combinators).

    Args:
        theme: A Theme object with base_css and colors.

    Returns:
        Dict mapping CSS selectors to dicts of {property: value}.
        Example: {"h1": {"color": "#333", "font-size": "28px"}, ...}
    """
    # Resolve CSS variables first
    resolved_css = _resolve_css_variables(theme.base_css, theme.colors)

    # Parse with cssutils
    sheet = cssutils.parseString(resolved_css, validate=False)

    rules: dict[str, dict[str, str]] = {}

    for rule in sheet:
        if rule.type != rule.STYLE_RULE:
            continue

        selector_text = rule.selectorText

        # A rule can have multiple comma-separated selectors
        selectors = [s.strip() for s in selector_text.split(",")]

        # Build property dict for this rule
        props: dict[str, str] = {}
        for prop in rule.style:
            props[prop.name] = prop.value

        if not props:
            continue

        for selector in selectors:
            if not _is_simple_selector(selector):
                continue

            if selector in rules:
                # Merge (later rules override)
                rules[selector].update(props)
            else:
                rules[selector] = dict(props)

    return rules
