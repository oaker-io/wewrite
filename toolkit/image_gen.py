#!/usr/bin/env python3
"""
AI image generation module for WeWrite.

Supports multiple providers via a simple abstraction:
  - doubao-seedream (Volcengine Ark) — default, good for Chinese prompts
  - openai (DALL-E 3) — broad availability
  - gemini (Google Gemini Imagen) — multimodal image generation
  - dashscope (Alibaba Tongyi Wanxiang) — good for Chinese prompts
  - minimax — Chinese provider
  - replicate — open-source models
  - azure_openai — Azure-hosted DALL-E
  - openrouter — multi-model proxy
  - jimeng (ByteDance) — good for Chinese prompts
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
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone
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
_DEFAULT = "1792x1024"
_DEFAULT_V = "1024x1792"
_DEFAULT_SQ = "1024x1024"

SIZE_PRESETS = {
    "cover": {
        "doubao": "2952x1256", "openai": _DEFAULT, "gemini": _DEFAULT,
        "dashscope": _DEFAULT, "minimax": _DEFAULT, "replicate": _DEFAULT,
        "azure_openai": _DEFAULT, "openrouter": _DEFAULT, "jimeng": _DEFAULT,
    },
    "article": {
        "doubao": "2560x1440", "openai": _DEFAULT, "gemini": _DEFAULT,
        "dashscope": _DEFAULT, "minimax": _DEFAULT, "replicate": _DEFAULT,
        "azure_openai": _DEFAULT, "openrouter": _DEFAULT, "jimeng": _DEFAULT,
    },
    "vertical": {
        "doubao": "1088x2560", "openai": _DEFAULT_V, "gemini": _DEFAULT_V,
        "dashscope": _DEFAULT_V, "minimax": _DEFAULT_V, "replicate": _DEFAULT_V,
        "azure_openai": _DEFAULT_V, "openrouter": _DEFAULT_V, "jimeng": _DEFAULT_V,
    },
    "square": {
        "doubao": "2048x2048", "openai": _DEFAULT_SQ, "gemini": _DEFAULT_SQ,
        "dashscope": _DEFAULT_SQ, "minimax": _DEFAULT_SQ, "replicate": _DEFAULT_SQ,
        "azure_openai": _DEFAULT_SQ, "openrouter": _DEFAULT_SQ, "jimeng": _DEFAULT_SQ,
    },
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


def _size_to_aspect(size: str) -> str:
    """Convert 'WxH' to nearest standard aspect ratio string."""
    if ":" in size:
        return size
    try:
        w, h = (int(x) for x in size.split("x", 1))
    except ValueError:
        return "16:9"
    ratio = w / h
    for ar, val in [("1:1", 1.0), ("16:9", 16/9), ("9:16", 9/16),
                    ("4:3", 4/3), ("3:4", 3/4), ("3:2", 3/2), ("2:3", 2/3)]:
        if abs(ratio - val) < 0.15:
            return ar
    return "16:9"


def _download_image(url: str) -> bytes:
    """Download image bytes from URL."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


# --- Provider abstraction ---

class ImageProvider(abc.ABC):
    """Base class for image generation providers."""

    @abc.abstractmethod
    def generate(self, prompt: str, size: str) -> bytes:
        """Generate an image and return raw bytes."""
        ...

    def resolve_size(self, preset: str) -> str:
        """Resolve a size preset to a concrete size string for this provider."""
        provider_key = self.provider_key
        if preset in SIZE_PRESETS:
            return SIZE_PRESETS[preset].get(provider_key, list(SIZE_PRESETS[preset].values())[0])
        return preset

    @property
    @abc.abstractmethod
    def provider_key(self) -> str:
        ...


# --- Providers ---

class DoubaoProvider(ImageProvider):
    """doubao-seedream via Volcengine Ark API."""

    provider_key = "doubao"

    def __init__(self, api_key: str, model: str = "doubao-seedream-5-0-260128",
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        resp = requests.post(
            f"{self._base_url}/images/generations",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "prompt": prompt,
                  "response_format": "url", "size": size,
                  "stream": False, "watermark": False},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"Doubao error ({resp.status_code}): "
                             f"{data.get('error', {}).get('message', str(data))}")
        url = data.get("data", [{}])[0].get("url")
        if not url:
            raise ValueError(f"No image URL: {data}")
        return _download_image(url)


class OpenAIProvider(ImageProvider):
    """OpenAI DALL-E 3 provider."""

    provider_key = "openai"

    def __init__(self, api_key: str, model: str = "dall-e-3",
                 base_url: str = "https://api.openai.com/v1", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        resp = requests.post(
            f"{self._base_url}/images/generations",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "prompt": prompt,
                  "n": 1, "size": size, "response_format": "url"},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"OpenAI error ({resp.status_code}): "
                             f"{data.get('error', {}).get('message', str(data))}")
        url = data.get("data", [{}])[0].get("url")
        if not url:
            raise ValueError(f"No image URL: {data}")
        return _download_image(url)


class GeminiProvider(ImageProvider):
    """Google Gemini Imagen provider."""

    provider_key = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-image-preview",
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        if "x" in size:
            w, h = size.split("x", 1)
            prompt = f"{prompt}\n\nGenerate this image at {w}x{h} resolution."
        resp = requests.post(
            f"{self._base_url}/models/{self._model}:generateContent",
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": self._api_key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
            timeout=120,
        )
        if resp.status_code != 200:
            msg = resp.text[:200]
            try:
                msg = resp.json().get("error", {}).get("message", msg)
            except Exception:
                pass
            raise ValueError(f"Gemini error ({resp.status_code}): {msg}")
        for part in resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("mimeType", "").startswith("image/"):
                return base64.b64decode(inline["data"])
        raise ValueError("No image in Gemini response")


class DashScopeProvider(ImageProvider):
    """Alibaba Tongyi Wanxiang (通义万相) via DashScope API."""

    provider_key = "dashscope"

    def __init__(self, api_key: str, model: str = "qwen-image-2.0-pro",
                 base_url: str = "https://dashscope.aliyuncs.com/api/v1", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        ds_size = size.replace("x", "*")  # DashScope uses "W*H"
        resp = requests.post(
            f"{self._base_url}/services/aigc/multimodal-generation/generation",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
                "parameters": {"prompt_extend": False, "size": ds_size, "watermark": False},
            },
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"DashScope error ({resp.status_code}): "
                             f"{data.get('message', str(data))}")
        # Try output.result_image first, then output.choices
        output = data.get("output", {})
        img = output.get("result_image")
        if not img:
            choices = output.get("choices", [])
            if choices:
                for c in choices[0].get("message", {}).get("content", []):
                    if "image" in c:
                        img = c["image"]
                        break
        if not img:
            raise ValueError(f"No image in DashScope response: {data}")
        if img.startswith("http"):
            return _download_image(img)
        return base64.b64decode(img)


class MiniMaxProvider(ImageProvider):
    """MiniMax image generation."""

    provider_key = "minimax"

    def __init__(self, api_key: str, model: str = "image-01",
                 base_url: str = "https://api.minimax.io/v1", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        w, h = 1024, 1024
        try:
            w, h = (int(x) for x in size.split("x", 1))
        except ValueError:
            pass
        resp = requests.post(
            f"{self._base_url}/image_generation",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "prompt": prompt,
                  "response_format": "base64",
                  "width": w, "height": h, "n": 1},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"MiniMax error ({resp.status_code}): {data}")
        b64_list = data.get("data", {}).get("image_base64", [])
        if not b64_list:
            raise ValueError(f"No image in MiniMax response: {data}")
        return base64.b64decode(b64_list[0])


class ReplicateProvider(ImageProvider):
    """Replicate API — supports many open-source image models."""

    provider_key = "replicate"
    _POLL_INTERVAL = 2
    _POLL_TIMEOUT = 300

    def __init__(self, api_key: str, model: str = "google/nano-banana-pro",
                 base_url: str = "https://api.replicate.com/v1", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        aspect = _size_to_aspect(size)
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self._api_key}",
                   "Prefer": "wait=60"}
        resp = requests.post(
            f"{self._base_url}/models/{self._model}/predictions",
            headers=headers,
            json={"input": {"prompt": prompt, "aspect_ratio": aspect,
                            "number_of_images": 1, "output_format": "png"}},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise ValueError(f"Replicate error ({resp.status_code}): {data}")

        # Poll if not completed yet
        poll_url = data.get("urls", {}).get("get")
        deadline = time.monotonic() + self._POLL_TIMEOUT
        while data.get("status") not in ("succeeded", "failed", "canceled"):
            if time.monotonic() > deadline:
                raise ValueError("Replicate polling timeout")
            time.sleep(self._POLL_INTERVAL)
            data = requests.get(poll_url, headers=headers, timeout=30).json()

        if data.get("status") != "succeeded":
            raise ValueError(f"Replicate failed: {data.get('error')}")

        output = data.get("output")
        if isinstance(output, list):
            output = output[0]
        if isinstance(output, dict):
            output = output.get("url", output.get("uri"))
        if not output or not isinstance(output, str):
            raise ValueError(f"No image URL in Replicate output: {data}")
        return _download_image(output)


class AzureOpenAIProvider(ImageProvider):
    """Azure-hosted OpenAI DALL-E."""

    provider_key = "azure_openai"

    def __init__(self, api_key: str, model: str = "dall-e-3",
                 base_url: str = "", deployment: str = "", **_kw):
        self._api_key = api_key
        self._deployment = deployment or model
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, size: str) -> bytes:
        if not self._base_url:
            raise ValueError("Azure OpenAI requires base_url "
                             "(e.g. https://YOUR-RESOURCE.openai.azure.com/openai)")
        resp = requests.post(
            f"{self._base_url}/deployments/{self._deployment}"
            f"/images/generations?api-version=2025-04-01-preview",
            headers={"Content-Type": "application/json",
                     "api-key": self._api_key},
            json={"prompt": prompt, "size": size, "n": 1, "quality": "medium"},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"Azure OpenAI error ({resp.status_code}): {data}")
        item = data.get("data", [{}])[0]
        if item.get("url"):
            return _download_image(item["url"])
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        raise ValueError(f"No image in Azure response: {data}")


class OpenRouterProvider(ImageProvider):
    """OpenRouter — multi-model proxy using chat completions format."""

    provider_key = "openrouter"

    def __init__(self, api_key: str, model: str = "google/gemini-3.1-flash-image-preview",
                 base_url: str = "https://openrouter.ai/api/v1", **_kw):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, size: str) -> bytes:
        aspect = _size_to_aspect(size)
        resp = requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image"],
                "stream": False,
                "image_config": {"aspect_ratio": aspect},
                "provider": {"require_parameters": True},
            },
            timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"OpenRouter error ({resp.status_code}): {data}")

        # Extract image from multiple possible locations
        choice = data.get("choices", [{}])[0].get("message", {})
        # Path 1: images array
        images = choice.get("images", [])
        if images:
            img = images[0]
            if img.startswith("http"):
                return _download_image(img)
            if img.startswith("data:"):
                _, b64 = img.split(",", 1)
                return base64.b64decode(b64)
        # Path 2: content array with image items
        content = choice.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image":
                    url = item.get("url") or item.get("image_url", {}).get("url")
                    if url:
                        if url.startswith("data:"):
                            _, b64 = url.split(",", 1)
                            return base64.b64decode(b64)
                        return _download_image(url)
        raise ValueError(f"No image in OpenRouter response: {data}")


class JimengProvider(ImageProvider):
    """ByteDance Jimeng (即梦) — async submit + poll with HMAC-SHA256 auth."""

    provider_key = "jimeng"
    _POLL_INTERVAL = 2
    _POLL_MAX_ATTEMPTS = 60

    def __init__(self, api_key: str, secret_key: str = "",
                 model: str = "jimeng_t2i_v40",
                 base_url: str = "https://visual.volcengineapi.com", **_kw):
        self._access_key = api_key
        self._secret_key = secret_key
        self._model = model
        self._base_url = base_url

    def _sign(self, method: str, path: str, query: str,
              headers: dict, payload: bytes) -> dict:
        """Generate Volcengine HMAC-SHA256 signed headers."""
        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")

        signed_headers_list = sorted(k.lower() for k in headers)
        signed_headers_str = ";".join(signed_headers_list)

        canonical = "\n".join([
            method, path, query,
            "".join(f"{k.lower()}:{headers[k]}\n" for k in sorted(headers)),
            signed_headers_str,
            hashlib.sha256(payload).hexdigest(),
        ])

        region = "cn-north-1"
        service = "cv"
        scope = f"{date_stamp}/{region}/{service}/request"
        string_to_sign = "\n".join([
            "HMAC-SHA256", amz_date, scope,
            hashlib.sha256(canonical.encode()).hexdigest(),
        ])

        def _hmac(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = _hmac(self._secret_key.encode(), date_stamp)
        k_region = _hmac(k_date, region)
        k_service = _hmac(k_region, service)
        k_signing = _hmac(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode(),
                             hashlib.sha256).hexdigest()

        auth = (f"HMAC-SHA256 Credential={self._access_key}/{scope}, "
                f"SignedHeaders={signed_headers_str}, Signature={signature}")
        return {**headers, "Authorization": auth, "X-Date": amz_date}

    def _request(self, action: str, body: dict) -> dict:
        payload = json.dumps(body).encode()
        path = "/"
        query = f"Action={action}&Version=2022-08-31"
        headers = {
            "Content-Type": "application/json",
            "Host": self._base_url.replace("https://", "").replace("http://", ""),
        }
        signed = self._sign("POST", path, query, headers, payload)
        resp = requests.post(
            f"{self._base_url}/?{query}",
            headers=signed, data=payload, timeout=120,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(f"Jimeng error ({resp.status_code}): {data}")
        return data

    def generate(self, prompt: str, size: str) -> bytes:
        if not self._secret_key:
            raise ValueError("Jimeng requires both api_key (access_key_id) "
                             "and secret_key (secret_access_key)")
        w, h = 1024, 1024
        try:
            w, h = (int(x) for x in size.split("x", 1))
        except ValueError:
            pass

        # Submit task
        submit = self._request("CVSync2AsyncSubmitTask", {
            "req_key": self._model, "prompt": prompt,
            "width": w, "height": h,
        })
        task_id = submit.get("data", {}).get("task_id")
        if not task_id:
            raise ValueError(f"No task_id from Jimeng: {submit}")

        # Poll for result
        for _ in range(self._POLL_MAX_ATTEMPTS):
            time.sleep(self._POLL_INTERVAL)
            result = self._request("CVSync2AsyncGetResult", {
                "req_key": self._model, "task_id": task_id,
            })
            code = result.get("code")
            if code == 10000:
                data = result.get("data", {})
                b64_list = data.get("binary_data_base64", [])
                if b64_list:
                    return base64.b64decode(b64_list[0])
                urls = data.get("image_urls", [])
                if urls:
                    return _download_image(urls[0])
                raise ValueError(f"No image data in Jimeng result: {result}")
            if code and code != 10000:
                status = result.get("data", {}).get("status")
                if status in ("failed", "canceled"):
                    raise ValueError(f"Jimeng task failed: {result}")

        raise ValueError("Jimeng polling timeout")


# --- Provider registry ---

PROVIDERS = {
    "doubao": DoubaoProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "dashscope": DashScopeProvider,
    "minimax": MiniMaxProvider,
    "replicate": ReplicateProvider,
    "azure_openai": AzureOpenAIProvider,
    "openrouter": OpenRouterProvider,
    "jimeng": JimengProvider,
}


def _build_provider_from_entry(entry: dict) -> ImageProvider:
    """Build a single ImageProvider from a provider config entry."""
    provider_name = entry.get("provider", "doubao")
    api_key = entry.get("api_key")

    if not api_key:
        raise ValueError(f"No api_key for provider '{provider_name}'")

    provider_cls = PROVIDERS.get(provider_name)
    if not provider_cls:
        raise ValueError(
            f"Unknown provider: '{provider_name}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )

    kwargs = {"api_key": api_key}
    if entry.get("model"):
        kwargs["model"] = entry["model"]
    if entry.get("base_url"):
        kwargs["base_url"] = entry["base_url"]
    if entry.get("secret_key"):
        kwargs["secret_key"] = entry["secret_key"]
    if entry.get("deployment"):
        kwargs["deployment"] = entry["deployment"]

    return provider_cls(**kwargs)


def _build_provider_chain(config: dict) -> list[ImageProvider]:
    """Build an ordered list of providers to try.

    Supports two config formats:
      - Legacy:  image.provider + image.api_key (single provider)
      - New:     image.providers (list, tried in order with auto-fallback)
    """
    img_cfg = config.get("image", {})
    providers_list = img_cfg.get("providers")

    if providers_list and isinstance(providers_list, list):
        chain = []
        for entry in providers_list:
            try:
                chain.append(_build_provider_from_entry(entry))
            except ValueError:
                continue  # skip misconfigured entries
        if not chain:
            raise ValueError(
                "No valid providers in image.providers list. "
                "Each entry needs 'provider' and 'api_key'."
            )
        return chain

    # Legacy single-provider format
    api_key = img_cfg.get("api_key")
    if not api_key:
        raise ValueError(
            "image.api_key not set in config.yaml. "
            "Configure your API key to enable image generation."
        )
    return [_build_provider_from_entry(img_cfg)]


def _build_provider(config: dict) -> ImageProvider:
    """Build an ImageProvider from config.yaml (backward-compatible entry point)."""
    return _build_provider_chain(config)[0]


# --- Public API ---

def generate_image(
    prompt: str,
    output_path: str,
    size: str = "cover",
    config: dict = None,
) -> str:
    """
    Generate an image using configured providers with auto-fallback.

    Tries each provider in order. If one fails, falls back to the next.
    Supports both single-provider (legacy) and multi-provider config.

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

    chain = _build_provider_chain(config)
    last_error = None

    for provider in chain:
        resolved_size = provider.resolve_size(size)
        try:
            raw_bytes = provider.generate(prompt, resolved_size)
        except Exception as e:
            last_error = e
            print(
                f"Provider '{provider.provider_key}' failed: {e}. "
                f"Trying next...",
                file=sys.stderr,
            )
            continue

        # Compress if over 5MB (WeChat upload limit)
        if len(raw_bytes) > MAX_FILE_SIZE:
            raw_bytes = _compress_image(raw_bytes, MAX_FILE_SIZE)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw_bytes)
        return str(output)

    raise ValueError(
        f"All providers failed. Last error: {last_error}"
    )


def main():
    ap = argparse.ArgumentParser(description="Generate images using AI")
    ap.add_argument("--prompt", required=True, help="Image generation prompt")
    ap.add_argument("--output", required=True, help="Output file path")
    ap.add_argument("--size", default="cover",
                    help="Size: cover, article, vertical, square, or WxH")
    ap.add_argument("--provider", default=None,
                    help=f"Override provider ({', '.join(PROVIDERS)})")
    args = ap.parse_args()

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
