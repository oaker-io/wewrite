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


def _build_article_dict(
    title: str,
    html: str,
    digest: str,
    *,
    thumb_media_id: Optional[str] = None,
    author: Optional[str] = None,
    open_comment: bool = True,
    fans_only_comment: bool = False,
    show_cover_pic: int = 0,
) -> dict:
    """组装一篇 article 的 API 字典 · 公用 helper。

    评论默认开(open_comment=True · 涨粉漏斗关键)。
    fans_only_comment 默认 False(允许非粉丝评论 · 增加路过用户互动 → 转化关注)。
    """
    article = {
        "title": title,
        "author": author or "",
        "digest": digest,
        "content": html,
        "show_cover_pic": show_cover_pic,
        "need_open_comment": 1 if open_comment else 0,
        "only_fans_can_comment": 1 if fans_only_comment else 0,
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id
    return article


def create_draft(
    access_token: str,
    title: str,
    html: str,
    digest: str,
    thumb_media_id: Optional[str] = None,
    author: Optional[str] = None,
    *,
    open_comment: bool = True,
    fans_only_comment: bool = False,
) -> DraftResult:
    """
    Create a draft in WeChat.
    API: POST https://api.weixin.qq.com/cgi-bin/draft/add
    Returns DraftResult.
    Raise ValueError on error (errcode present and != 0).

    Args:
        open_comment: 默认 True · 推草稿时打开评论(涨粉漏斗 + 评论运营基础)
        fans_only_comment: 默认 False · 允许非粉丝评论(路过用户互动 → 转化关注)
    """
    article = _build_article_dict(
        title, html, digest,
        thumb_media_id=thumb_media_id, author=author,
        open_comment=open_comment, fans_only_comment=fans_only_comment,
    )
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


def create_draft_bundle(
    access_token: str,
    articles: list[dict],
) -> DraftResult:
    """一次推 1-8 篇文章 (主推 + 副推) · 占同一次群发配额。

    订阅号每日 1 次群发 = 1 主图文 + 0-7 副图文。这是解锁副推位的关键 API。

    Args:
        articles: list of dicts · 每个 dict 至少含 {title, html, digest},
                  可选含 thumb_media_id / author / open_comment / fans_only_comment / show_cover_pic
                  第 1 个 article 是主推 · 其余是副推 (companion).

    Returns DraftResult with the bundle's media_id (一个 media_id 代表整个 bundle).

    Raises:
        ValueError on API error or 越界(< 1 or > 8 articles)。
    """
    if not articles:
        raise ValueError("create_draft_bundle 需要至少 1 篇 article")
    if len(articles) > 8:
        raise ValueError(f"WeChat draft 单次最多 8 篇 · 收到 {len(articles)} 篇")

    api_articles = []
    for i, a in enumerate(articles):
        if "title" not in a or "html" not in a or "digest" not in a:
            raise ValueError(f"article[{i}] 缺 title/html/digest 必填字段")
        api_articles.append(_build_article_dict(
            a["title"], a["html"], a["digest"],
            thumb_media_id=a.get("thumb_media_id"),
            author=a.get("author"),
            open_comment=a.get("open_comment", True),
            fans_only_comment=a.get("fans_only_comment", False),
            show_cover_pic=a.get("show_cover_pic", 0),
        ))

    body = {"articles": api_articles}

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
        raise ValueError(
            f"WeChat create_draft_bundle error (n_articles={len(api_articles)}): "
            f"errcode={errcode}, errmsg={errmsg}"
        )

    if "media_id" not in data:
        raise ValueError(f"WeChat create_draft_bundle: missing media_id in response: {data}")

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
