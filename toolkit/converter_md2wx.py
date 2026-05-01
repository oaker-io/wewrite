"""
md2wx 排版引擎 adapter · 直接打 aipickgold.com 的 API · 50 主题

服务端 2026-04 升级后主题命名改为英文(见下方 THEMES 列表)。
本 adapter 不依赖任何本地 md2wx CLI 版本,只用 HTTP。

主题清单(50 个):
  **通用**(16):default / bytedance / apple / sports / chinese / cyber /
    wechat-native / nyt-classic / github-readme / sspai-red / mint-fresh /
    sunset-amber / ink-minimal / lavender-dream / coffee-house / bauhaus-primary
  **极简系列**(8):minimal-{gold,green,blue,orange,red,navy,gray,sky}
  **聚焦系列**(8):focus-{gold,green,blue,orange,red,navy,gray,sky}
  **优雅系列**(8):elegant-{gold,green,blue,orange,red,navy,gray,sky}
  **粗犷系列**(8):bold-{gold,green,blue,orange,red,navy,gray,sky}
  **特殊**(2):xiaomo / shikexin

用法:
    from converter_md2wx import Md2wxConverter
    c = Md2wxConverter(theme_name="focus-navy")
    result = c.convert_file("article.md")

配置 API key(优先级):
  1. 构造参数 api_key
  2. 环境变量 MD2WECHAT_API_KEY
  3. secrets/keys.env(同名变量,本脚本不自动 source,由调用方负责)
  4. ~/.md2wx.json 的 api_key(旧版 md2wx CLI 的配置位)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests


API_ENDPOINT = "https://aipickgold.com/api/convert"


@dataclass
class ConvertResult:
    html: str
    title: str
    digest: str
    images: list[str] = field(default_factory=list)


def _resolve_api_key(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("MD2WECHAT_API_KEY")
    if env:
        return env
    # Fallback:旧 md2wx CLI 的配置
    cfg = Path.home() / ".md2wx.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text())
            if data.get("api_key"):
                return data["api_key"]
        except (json.JSONDecodeError, OSError):
            pass
    raise RuntimeError(
        "md2wx API key 未配置。以下任一方式:\n"
        "  1. export MD2WECHAT_API_KEY=...\n"
        "  2. 编辑 secrets/keys.env 里的 MD2WECHAT_API_KEY,然后 source\n"
        "  3. ~/.md2wx.json 里 { \"api_key\": \"...\" }\n"
        "  去 https://aipickgold.com 账号中心申请 key。"
    )


def _extract_title(markdown):
    for line in markdown.splitlines():
        m = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return "未命名文章"


def _extract_digest(markdown, max_bytes=120):
    """提取摘要 · 兼容有/无 H1 两种文章。

    旧版要求 H1 作为正文起点;新管线 sanitize 会去 H1,所以这里改为
    无 H1 时从首行非元数据正文起算。
    """
    raw_lines = markdown.splitlines()
    has_h1 = any(re.match(r"^\s*#\s+", l) for l in raw_lines[:10])
    in_body = not has_h1
    lines = []
    for line in raw_lines:
        if re.match(r"^\s*#\s+", line):
            in_body = True
            continue
        if not in_body:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith("<!--"):
            continue
        clean = re.sub(r"[*_`\[\]()#>-]", "", stripped)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            lines.append(clean)
        if sum(len(l.encode("utf-8")) for l in lines) >= max_bytes:
            break
    text = " ".join(lines)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes - 3].decode("utf-8", errors="ignore") + "..."


def _extract_images(markdown):
    return re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", markdown)


class Md2wxConverter:
    """Direct HTTP client for aipickgold.com /api/convert · 50 themes."""

    def __init__(self, theme_name="focus-navy", font_size=None, api_key=None, timeout=60):
        self._theme = theme_name
        self._font_size = font_size
        self._api_key = _resolve_api_key(api_key)
        self._timeout = timeout

    def convert(self, markdown_text):
        # Pre-process author-card container with theme-aware style mapping
        from author_card import preprocess_author_card
        markdown_text = preprocess_author_card(markdown_text, theme_id=self._theme)
        body = {"markdown": markdown_text, "theme": self._theme}
        if self._font_size:
            body["fontSize"] = self._font_size

        resp = requests.post(
            API_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                # Redundant auth headers — post-2026-04 server accepts all four:
                "X-API-Key": self._api_key,
                "Authorization": f"Bearer {self._api_key}",
            },
            json=body,
            timeout=self._timeout,
        )

        if resp.status_code != 200:
            try:
                err = resp.json().get("msg") or resp.json().get("message") or resp.text[:200]
            except ValueError:
                err = resp.text[:200]
            raise RuntimeError(f"md2wx API {resp.status_code}: {err}")

        data = resp.json()
        # Server may return `{html, wordCount}` or `{code, data: {html, wordCount}}`
        html = data.get("html") or (data.get("data") or {}).get("html") or ""
        if not html:
            raise RuntimeError(f"md2wx API empty html: {json.dumps(data)[:300]}")

        return ConvertResult(
            html=html,
            title=_extract_title(markdown_text),
            digest=_extract_digest(markdown_text),
            images=_extract_images(markdown_text),
        )

    def convert_file(self, input_path):
        markdown = Path(input_path).read_text(encoding="utf-8")
        return self.convert(markdown)
