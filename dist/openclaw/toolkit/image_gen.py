#!/usr/bin/env python3
"""
AI image generation module for WeWrite.

Supports multiple providers via a simple abstraction:
  - doubao-seedream (Volcengine Ark) — default, good for Chinese prompts
  - openai (DALL-E 3) — broad availability
  - gemini (Google Gemini Imagen) — multimodal image generation
  - Custom providers via ImageProvider base class

Usage as CLI:
    python3 image_gen.py --prompt "描述" --output cover.png
    python3 image_gen.py --prompt "描述" --output cover.png --size cover
    python3 image_gen.py --prompt "描述" --output cover.png --provider gemini

Usage as module:
    from image_gen import generate_image
    path = generate_image("prompt text", "output.png", size="cover")
"""

import abc
import argparse
import base64
import json
import sys
from pathlib import Path

import requests
import yaml

# --- Config ---

CONFIG_PATHS = [
    Path.cwd() / "config.yaml",
    Path(__file__).parent.parent / "config.yaml",  # skill root
    Path(__file__).parent / "config.yaml",          # toolkit dir
    Path.home() / ".config" / "wewrite" / "config.yaml",
]


def _load_config() -> dict:
    for p in CONFIG_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


# --- Size presets ---

# Cover: 2.35:1 微信封面比例
# Article: 16:9 横版内文配图
# Vertical: 9:16 竖版
SIZE_PRESETS = {
    "cover": {"doubao": "2952x1256", "openai": "1792x1024", "gemini": "1792x1024"},
    "article": {"doubao": "2560x1440", "openai": "1792x1024", "gemini": "1792x1024"},
    "vertical": {"doubao": "1088x2560", "openai": "1024x1792", "gemini": "1024x1792"},
    "square": {"doubao": "2048x2048", "openai": "1024x1024", "gemini": "1024x1024"},
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _compress_image(raw_bytes: bytes, max_size: int) -> bytes:
    """Compress image to fit under max_size by reducing JPEG quality."""
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(raw_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    for quality in (90, 80, 70, 60, 50):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_size:
            return buf.getvalue()

    return buf.getvalue()


# --- Provider abstraction ---

class ImageProvider(abc.ABC):
    """Base class for image generation providers."""

    @abc.abstractmethod
    def generate(self, prompt: str, size: str) -> bytes:
        """Generate an image and return raw bytes.

        Args:
            prompt: Image description (Chinese or English).
            size: Resolved size string (e.g. "1792x1024").

        Returns:
            Raw image bytes.
        """
        ...

    def resolve_size(self, preset: str) -> str:
        """Resolve a size preset to a concrete size string for this provider."""
        provider_key = self.provider_key
        if preset in SIZE_PRESETS:
            return SIZE_PRESETS[preset].get(provider_key, list(SIZE_PRESETS[preset].values())[0])
        return preset  # assume explicit WxH

    @property
    @abc.abstractmethod
    def provider_key(self) -> str:
        """Short identifier used for size preset lookup."""
        ...


class DoubaoProvider(ImageProvider):
    """doubao-seedream via Volcengine Ark API."""

    provider_key = "doubao"

    def __init__(self, api_key: str, model: str = "doubao-seedream-5-0-260128",
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        body = {
            "model": self._model,
            "prompt": prompt,
            "response_format": "url",
            "size": size,
            "stream": False,
            "watermark": False,
        }

        resp = requests.post(
            f"{self._base_url}/images/generations",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            json=body,
            timeout=120,
        )

        data = resp.json()
        if resp.status_code != 200:
            error = data.get("error", {})
            msg = error.get("message", json.dumps(data, ensure_ascii=False))
            raise ValueError(f"Doubao API error ({resp.status_code}): {msg}")

        image_data = data.get("data", [])
        if not image_data:
            raise ValueError(f"No image returned: {json.dumps(data, ensure_ascii=False)}")

        image_url = image_data[0].get("url")
        if not image_url:
            raise ValueError(f"No image URL in response: {json.dumps(data, ensure_ascii=False)}")

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content


class OpenAIProvider(ImageProvider):
    """OpenAI DALL-E 3 provider."""

    provider_key = "openai"

    def __init__(self, api_key: str, model: str = "dall-e-3",
                 base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        # DALL-E 3 expects size as "WxH" format
        dall_e_size = size.replace("x", "x")  # normalize

        body = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "size": dall_e_size,
            "response_format": "url",
        }

        resp = requests.post(
            f"{self._base_url}/images/generations",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            json=body,
            timeout=120,
        )

        data = resp.json()
        if resp.status_code != 200:
            error = data.get("error", {})
            msg = error.get("message", json.dumps(data, ensure_ascii=False))
            raise ValueError(f"OpenAI API error ({resp.status_code}): {msg}")

        image_data = data.get("data", [])
        if not image_data:
            raise ValueError(f"No image returned: {json.dumps(data, ensure_ascii=False)}")

        image_url = image_data[0].get("url")
        if not image_url:
            raise ValueError(f"No image URL in response: {json.dumps(data, ensure_ascii=False)}")

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content


class GeminiProvider(ImageProvider):
    """Google Gemini Imagen provider."""

    provider_key = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-image-preview",
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        # Append size instruction to prompt (Gemini doesn't have a native size param)
        if "x" in size:
            w, h = size.split("x", 1)
            prompt = f"{prompt}\n\nGenerate this image at {w}x{h} resolution."

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        resp = requests.post(
            f"{self._base_url}/models/{self._model}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            },
            json=body,
            timeout=120,
        )
        if resp.status_code != 200:
            try:
                error = resp.json().get("error", {})
                msg = error.get("message", resp.text[:200])
            except (ValueError, KeyError):
                msg = resp.text[:200]
            raise ValueError(f"Gemini API error ({resp.status_code}): {msg}")
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in Gemini response")
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            inline_data = part.get("inlineData")
            if inline_data and inline_data.get("mimeType", "").startswith("image/"):
                return base64.b64decode(inline_data["data"])
        raise ValueError(f"No image found in Gemini response parts")


# --- Provider registry ---

PROVIDERS = {
    "doubao": DoubaoProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}

def _build_provider(config: dict) -> ImageProvider:
    """Build an ImageProvider from config.yaml's image section.

    API key resolution order:
      1. image.{provider}_api_key  (e.g. image.gemini_api_key)
      2. image.api_key             (shared fallback)
    """
    img_cfg = config.get("image", {})
    provider_name = img_cfg.get("provider", "doubao")
    api_key = img_cfg.get(f"{provider_name}_api_key") or img_cfg.get("api_key")

    if not api_key:
        raise ValueError(
            f"image.api_key (or image.{provider_name}_api_key) not set in config.yaml. "
            f"Configure your {provider_name} API key to enable image generation."
        )

    provider_cls = PROVIDERS.get(provider_name)
    if not provider_cls:
        raise ValueError(
            f"Unknown image provider: '{provider_name}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )

    kwargs = {"api_key": api_key}
    if img_cfg.get("model"):
        kwargs["model"] = img_cfg["model"]
    if img_cfg.get("base_url"):
        kwargs["base_url"] = img_cfg["base_url"]

    return provider_cls(**kwargs)


# --- Public API ---

def generate_image(
    prompt: str,
    output_path: str,
    size: str = "cover",
    config: dict = None,
) -> str:
    """
    Generate an image using the configured provider.

    Args:
        prompt: Image generation prompt (Chinese or English).
        output_path: Where to save the image.
        size: Size preset ("cover", "article", "vertical", "square") or explicit "WxH".
        config: Optional config dict. If None, loads from config.yaml.

    Returns:
        The output file path.
    """
    if config is None:
        config = _load_config()

    provider = _build_provider(config)
    resolved_size = provider.resolve_size(size)

    raw_bytes = provider.generate(prompt, resolved_size)

    # Compress if over 5MB (WeChat upload limit)
    if len(raw_bytes) > MAX_FILE_SIZE:
        raw_bytes = _compress_image(raw_bytes, MAX_FILE_SIZE)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw_bytes)
    return str(output)


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using AI (doubao-seedream, OpenAI DALL-E, Gemini Imagen, etc.)"
    )
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument(
        "--size",
        default="cover",
        help="Size: cover, article, vertical, square, or WxH",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Override provider (doubao, openai, gemini). Default: from config.yaml",
    )
    args = parser.parse_args()

    try:
        config = _load_config()
        if args.provider:
            config.setdefault("image", {})["provider"] = args.provider
        path = generate_image(args.prompt, args.output, size=args.size, config=config)
        print(f"Image saved: {path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
