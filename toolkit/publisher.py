import json

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class DraftResult:
    media_id: str


@dataclass
class ImagePostResult:
    media_id: str
    image_count: int


def create_draft(
    access_token: str,
    title: str,
    html: str,
    digest: str,
    thumb_media_id: Optional[str] = None,
    author: Optional[str] = None,
) -> DraftResult:
    """
    Create a draft in WeChat.
    API: POST https://api.weixin.qq.com/cgi-bin/draft/add
    Returns DraftResult.
    Raise ValueError on error (errcode present and != 0).
    """
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
    )

    data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg", "unknown error")
        raise ValueError(f"WeChat create_draft error: errcode={errcode}, errmsg={errmsg}")

    if "media_id" not in data:
        raise ValueError(f"WeChat create_draft error: missing media_id in response: {data}")

    return DraftResult(media_id=data["media_id"])


def create_image_post(
    access_token: str,
    title: str,
    image_media_ids: list[str],
    content: str = "",
    open_comment: bool = False,
    fans_only_comment: bool = False,
) -> ImagePostResult:
    """
    Create a WeChat image post (小绿书/图片帖) draft.

    This uses article_type="newspic" which displays as a horizontal
    swipe carousel (3:4 ratio), similar to Xiaohongshu.

    Args:
        access_token: WeChat access token.
        title: Post title, max 32 characters.
        image_media_ids: List of permanent media_ids from upload_thumb().
                        Min 1, max 20. First image becomes the cover.
        content: Plain text description, max ~1000 chars. No HTML.
        open_comment: Allow comments.
        fans_only_comment: Only followers can comment.

    Returns ImagePostResult with media_id of created draft.
    """
    if not image_media_ids:
        raise ValueError("At least 1 image is required for image post")
    if len(image_media_ids) > 20:
        raise ValueError(f"Max 20 images allowed, got {len(image_media_ids)}")
    if len(title) > 32:
        raise ValueError(f"Title max 32 chars for image post, got {len(title)}")

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
