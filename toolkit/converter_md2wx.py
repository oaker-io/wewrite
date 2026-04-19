"""
md2wx 排版引擎 adapter · 把 md2wx CLI 的输出包装成 WeWrite 的 ConvertResult。

md2wx(https://github.com/soarsky1991/md2wx)提供 40 主题,分 5 系列:经典/极简/聚焦/渐变/卡片。
相比 WeWrite 自带的 16 主题,md2wx 通过 aipickgold.com 服务器渲染,需要 API key。

用法:
    converter = Md2wxConverter(theme_name="经典-暖橙")
    result = converter.convert_file("article.md")

环境/配置:
    - md2wx repo 路径通过 MD2WX_DIR 环境变量或 ~/wechatgzh/md2wx 默认约定
    - API key 通过 md2wx CLI 配置(~/.md2wx.json)或 MD2WECHAT_API_KEY 环境变量
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConvertResult:
    html: str
    title: str
    digest: str
    images: list[str] = field(default_factory=list)


# md2wx CLI binary lookup order
_CANDIDATES = [
    os.environ.get("MD2WX_DIR"),  # explicit override
    str(Path.home() / "wechatgzh" / "md2wx" / "skill" / "dist" / "index.js"),
    str(Path.home() / "md2wx" / "skill" / "dist" / "index.js"),
    str(Path(__file__).resolve().parent.parent.parent / "md2wx" / "skill" / "dist" / "index.js"),
]


def _find_md2wx() -> Path:
    for c in _CANDIDATES:
        if c and Path(c).exists():
            return Path(c)
    raise FileNotFoundError(
        "md2wx CLI not found. Clone + build it:\n"
        "  git clone https://github.com/soarsky1991/md2wx.git ~/wechatgzh/md2wx\n"
        "  cd ~/wechatgzh/md2wx/skill && npm install && npm run build\n"
        "Or set MD2WX_DIR to the built dist/index.js path."
    )


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        m = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return "未命名文章"


def _extract_digest(markdown: str, max_bytes: int = 120) -> str:
    # Skip H1 + blank, take first 2-3 non-structural paragraphs
    lines = []
    in_body = False
    for line in markdown.splitlines():
        if re.match(r"^\s*#\s+", line):
            in_body = True
            continue
        if not in_body:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith("<!--"):
            continue
        # Strip markdown syntax inline
        clean = re.sub(r"[*_`\[\]()#>-]", "", stripped)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            lines.append(clean)
        if sum(len(l.encode("utf-8")) for l in lines) >= max_bytes:
            break
    text = " ".join(lines)
    # Truncate to max_bytes UTF-8
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes - 3].decode("utf-8", errors="ignore") + "..."


def _extract_images(markdown: str) -> list[str]:
    # Find all image refs: ![alt](path)
    return re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", markdown)


class Md2wxConverter:
    """Wrap md2wx CLI as a ConvertResult-producing converter."""

    def __init__(self, theme_name="经典-暖橙", font_size=None):
        self._bin = _find_md2wx()
        self._theme_name = theme_name
        self._font_size = font_size

    def convert(self, markdown_text: str) -> ConvertResult:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(markdown_text)
            src = Path(f.name)
        try:
            cmd = ["node", str(self._bin), "convert", str(src), "--theme", self._theme_name]
            if self._font_size:
                cmd += ["--font-size", self._font_size]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"md2wx convert failed (exit {result.returncode}): {stderr[:400]}\n"
                    f"Tip: run `md2wx config set api-key <YOUR_KEY>` or set MD2WECHAT_API_KEY "
                    f"(sign up at aipickgold.com)."
                )
            html = result.stdout
        finally:
            try:
                src.unlink()
            except OSError:
                pass

        return ConvertResult(
            html=html,
            title=_extract_title(markdown_text),
            digest=_extract_digest(markdown_text),
            images=_extract_images(markdown_text),
        )

    def convert_file(self, input_path: str) -> ConvertResult:
        markdown = Path(input_path).read_text(encoding="utf-8")
        return self.convert(markdown)
