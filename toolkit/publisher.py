import json
import os
import sys
import time
from pathlib import Path

import requests
from dataclasses import dataclass
from typing import Optional


def _autoload_wechat_proxy_env():
    """Auto-load WECHAT_HTTPS_PROXY from ~/.wechat-proxy.env when shell rc
    is bypassed (e.g. Claude Code's non-interactive bash, cron, launchd).
    No-op if env already set or file missing."""
    if os.environ.get("WECHAT_HTTPS_PROXY"):
        return
    env_file = Path.home() / ".wechat-proxy.env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("export WECHAT_HTTPS_PROXY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            os.environ["WECHAT_HTTPS_PROXY"] = val
            return


_autoload_wechat_proxy_env()

# Force WeChat API calls through a dedicated proxy (e.g. fixed-IP ECS) so
# they bypass shell-level https_proxy (Clash) — see WECHAT_HTTPS_PROXY.
_WECHAT_PROXY = os.environ.get("WECHAT_HTTPS_PROXY")
_WECHAT_PROXIES = (
    {"https": _WECHAT_PROXY, "http": _WECHAT_PROXY} if _WECHAT_PROXY else None
)


@dataclass
class DraftResult:
    media_id: str


@dataclass
class ImagePostResult:
    media_id: str
    image_count: int


# 幂等检查窗口：同 title 在多少秒内的草稿视为重复，复用 media_id
# 10 分钟覆盖 LLM 重试 + 网络抖动，但不会复用一个月前的同名旧文
DEDUP_WINDOW_SECONDS = 600


def _find_existing_draft(
    access_token: str,
    title: str,
    window_seconds: int = DEDUP_WINDOW_SECONDS,
    max_lookback: int = 20,
) -> Optional[str]:
    """
    Look up recent drafts by title within a time window.
    Returns media_id of the most recent matching draft, or None.

    Used by create_draft / create_image_post for idempotency:
    if the caller retries (LLM-driven, network jitter), we should
    reuse the existing draft rather than create duplicates.

    Match criteria:
    - Title must be exactly equal (case sensitive)
    - update_time must be within window_seconds of now
    - First N (max_lookback) drafts in WeChat's batchget order (newest first)

    Raises ValueError on WeChat API error (errcode != 0).
    """
    # no_content=0 ensures title field is present in news_item.
    # (Empirically no_content=1 also returns titles, but docs are ambiguous —
    # paying the extra bytes is cheap insurance.)
    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/draft/batchget",
        params={"access_token": access_token},
        json={"offset": 0, "count": max_lookback, "no_content": 0},
        proxies=_WECHAT_PROXIES,
    )
    # WeChat batchget response Content-Type doesn't declare charset,
    # requests falls back to latin-1 → mojibake Chinese titles → dedup miss.
    # Force utf-8 to match get_draft's pattern.
    resp.encoding = "utf-8"
    data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        # batchget failure should not block create_draft — log + degrade to create
        errmsg = data.get("errmsg", "unknown error")
        print(
            f"[publisher] WARN: dedup lookup failed (errcode={errcode}, errmsg={errmsg}), "
            f"falling back to create",
            file=sys.stderr,
        )
        return None

    now = int(time.time())
    items = data.get("item", [])

    # Don't rely on WeChat batchget being newest-first (docs don't guarantee
    # ordering). Scan all returned items, collect matches with their
    # update_time, return the newest match within window.
    best_match = None  # (update_time, media_id)
    for it in items:
        update_time = it.get("update_time", 0)
        if now - update_time > window_seconds:
            continue
        news_items = it.get("content", {}).get("news_item", [])
        for art in news_items:
            if art.get("title") == title:
                media_id = it.get("media_id")
                if best_match is None or update_time > best_match[0]:
                    best_match = (update_time, media_id)

    if best_match is not None:
        update_time, media_id = best_match
        age = now - update_time
        print(
            f"[publisher] DEDUP: reusing existing draft media_id={media_id} "
            f"(title='{title[:30]}...', age={age}s)",
            file=sys.stderr,
        )
        return media_id

    return None


def create_draft(
    access_token: str,
    title: str,
    html: str,
    digest: str,
    thumb_media_id: Optional[str] = None,
    author: Optional[str] = None,
    skip_dedup: bool = False,
) -> DraftResult:
    """
    Create a draft in WeChat.
    API: POST https://api.weixin.qq.com/cgi-bin/draft/add

    Idempotency: before creating, query batchget for recent drafts with
    same title. If found within DEDUP_WINDOW_SECONDS (default 600s),
    return the existing media_id instead of creating a duplicate.
    Pass skip_dedup=True to force a fresh create (rarely needed).

    Returns DraftResult.
    Raise ValueError on WeChat API error (errcode present and != 0).
    """
    if not skip_dedup:
        existing = _find_existing_draft(access_token, title)
        if existing is not None:
            return DraftResult(media_id=existing)

    article = {
        "title": title,
        "author": author or "",
        "digest": digest,
        "content": html,
        "show_cover_pic": 0,
    }

    # thumb_media_id is required by WeChat API — if not provided,
    # upload a default 1x1 white pixel, or skip if truly empty
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    body = {"articles": [article]}

    # MUST use ensure_ascii=False — otherwise Chinese becomes \uXXXX
    # and WeChat stores the escape sequences literally, causing title
    # length overflow and garbled content.
    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": access_token},
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        proxies=_WECHAT_PROXIES,
    )

    data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg", "unknown error")
        raise ValueError(f"WeChat create_draft error: errcode={errcode}, errmsg={errmsg}")

    if "media_id" not in data:
        raise ValueError(f"WeChat create_draft error: missing media_id in response: {data}")

    return DraftResult(media_id=data["media_id"])


def get_draft(access_token: str, media_id: str) -> str:
    """
    Get draft content from WeChat by media_id.
    API: POST https://api.weixin.qq.com/cgi-bin/draft/get
    Returns the HTML content of the first article.
    """
    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/draft/get",
        params={"access_token": access_token},
        json={"media_id": media_id},
        proxies=_WECHAT_PROXIES,
    )
    resp.encoding = "utf-8"
    data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg", "unknown error")
        raise ValueError(f"WeChat get_draft error: errcode={errcode}, errmsg={errmsg}")

    articles = data.get("news_item", [])
    if not articles:
        raise ValueError(f"WeChat get_draft: no articles in draft {media_id}")

    return articles[0].get("content", "")


def html_to_plaintext(html: str) -> str:
    """Extract plain text from WeChat HTML, stripping all tags and styles."""
    import re
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newlines
    text = re.sub(r"<(br|p|div|section|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def create_image_post(
    access_token: str,
    title: str,
    image_media_ids: list[str],
    content: str = "",
    open_comment: bool = False,
    fans_only_comment: bool = False,
    skip_dedup: bool = False,
) -> ImagePostResult:
    """
    Create a WeChat image post (小绿书/图片帖) draft.

    This uses article_type="newspic" which displays as a horizontal
    swipe carousel (3:4 ratio), similar to Xiaohongshu.

    Idempotency: same dedup behavior as create_draft (lookup by title
    within DEDUP_WINDOW_SECONDS). Pass skip_dedup=True to force create.

    Args:
        access_token: WeChat access token.
        title: Post title, max 32 characters.
        image_media_ids: List of permanent media_ids from upload_thumb().
                        Min 1, max 20. First image becomes the cover.
        content: Plain text description, max ~1000 chars. No HTML.
        open_comment: Allow comments.
        fans_only_comment: Only followers can comment.
        skip_dedup: Set True to bypass dedup and force create.

    Returns ImagePostResult with media_id of created draft.
    """
    if not image_media_ids:
        raise ValueError("At least 1 image is required for image post")
    if len(image_media_ids) > 20:
        raise ValueError(f"Max 20 images allowed, got {len(image_media_ids)}")
    if len(title) > 32:
        raise ValueError(f"Title max 32 chars for image post, got {len(title)}")

    if not skip_dedup:
        existing = _find_existing_draft(access_token, title)
        if existing is not None:
            return ImagePostResult(
                media_id=existing,
                image_count=len(image_media_ids),
            )

    article = {
        "article_type": "newspic",
        "title": title,
        "content": content,
        "image_info": {
            "image_list": [
                {"image_media_id": mid} for mid in image_media_ids
            ]
        },
        "need_open_comment": 1 if open_comment else 0,
        "only_fans_can_comment": 1 if fans_only_comment else 0,
    }

    body = {"articles": [article]}

    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": access_token},
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        proxies=_WECHAT_PROXIES,
    )

    data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg", "unknown error")
        raise ValueError(f"WeChat create_image_post error: errcode={errcode}, errmsg={errmsg}")

    if "media_id" not in data:
        raise ValueError(f"WeChat create_image_post: missing media_id in response: {data}")

    return ImagePostResult(
        media_id=data["media_id"],
        image_count=len(image_media_ids),
    )
