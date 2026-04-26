"""source_fetcher.py · 给 Twitter URL · 抓正文 + 原图 · 准备洗稿。

为啥不用 Twitter API:
  - Twitter API v2 需要 OAuth + Developer 账号 · 麻烦
  - cdn.syndication.twimg.com 是 Twitter 公开 embed endpoint · 0 auth
  - 已实测 4/26 拿到完整 tweet text + media_url_https + quoted_tweet

数据流:
  url → tweet_id → syndication API → JSON
       → 抽 author / text / mediaDetails / quoted_tweet
       → 下载 photos 到 output/images/{slug}/source_*.jpg
       → 返回结构化 dict 给 rewrite_article.py

支持(按优先级):
  - 单条 tweet · 含图(photo)
  - quoted_tweet · 嵌套抓
  - X 长文 article(预览段 + cover_media)· 全文需 OAuth · 暂不支持
  - thread(同作者 reply 链)· 后续加
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token=a"


def parse_tweet_id(url: str) -> str | None:
    """从 https://x.com/{user}/status/{id} 或 twitter.com 抽 id。"""
    m = re.search(r"/status/(\d+)", url)
    if m:
        return m.group(1)
    if url.isdigit():
        return url
    return None


def fetch_tweet(url_or_id: str, *, timeout: int = 15) -> dict | None:
    """调 Twitter syndication 拿 tweet metadata · 失败 None。"""
    tid = parse_tweet_id(url_or_id) or url_or_id
    if not tid.isdigit():
        return None
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout),
             SYNDICATION_URL.format(id=tid)],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("__typename") not in (None, "Tweet"):
        return None
    return data


def _extract_image_urls(tweet: dict) -> list[dict]:
    """从 tweet 抽所有 photo url(media_url_https · 跳过 video / GIF)。"""
    out = []
    for m in tweet.get("mediaDetails") or []:
        if m.get("type") != "photo":
            continue
        url = m.get("media_url_https")
        if not url:
            continue
        info = m.get("original_info") or {}
        out.append({
            "url": url,
            "width": info.get("width"),
            "height": info.get("height"),
        })
    return out


def _download_image(url: str, dst: Path, timeout: int = 30) -> bool:
    """curl 下载 · 返回是否成功。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout),
             "-o", str(dst), url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 1024


def fetch_source(url: str, *, slug: str | None = None,
                 include_quoted: bool = True,
                 out_root: Path | None = None) -> dict:
    """主入口 · 给 1 个 Twitter URL · 返回完整素材包。

    Returns:
        {
          "ok": True/False,
          "url": ...,
          "author": {"name", "screen_name", "verified"},
          "text": "...",
          "lang": "zh",
          "favorite_count": int,
          "created_at": iso,
          "images": [{"url", "local_path", "width", "height"}, ...],
          "quoted": {同结构 · 可选},
          "article": {"title", "preview", "cover_url"} or None,
        }
    """
    out_root = out_root or (ROOT / "output" / "images")
    slug = slug or datetime.now().strftime("source-%Y%m%d-%H%M%S")
    out_dir = out_root / slug

    tweet = fetch_tweet(url)
    if tweet is None:
        return {"ok": False, "url": url, "error": "syndication endpoint returned nothing"}

    user = tweet.get("user") or {}
    pkg: dict = {
        "ok": True,
        "url": url,
        "tweet_id": tweet.get("id_str"),
        "author": {
            "name": user.get("name", ""),
            "screen_name": user.get("screen_name", ""),
            "verified": user.get("is_blue_verified", False),
        },
        "text": tweet.get("text", ""),
        "lang": tweet.get("lang", ""),
        "favorite_count": tweet.get("favorite_count", 0),
        "created_at": tweet.get("created_at", ""),
        "images": [],
    }

    # 下主帖图
    for i, img in enumerate(_extract_image_urls(tweet), 1):
        local = out_dir / f"source_{i}.jpg"
        if _download_image(img["url"], local):
            pkg["images"].append({
                "url": img["url"],
                "local_path": str(local.relative_to(ROOT)),
                "width": img["width"],
                "height": img["height"],
            })

    # quoted tweet 嵌套(很多 X 长帖是引用别人 + 加评)
    if include_quoted and tweet.get("quoted_tweet"):
        qt = tweet["quoted_tweet"]
        qt_user = qt.get("user") or {}
        pkg["quoted"] = {
            "tweet_id": qt.get("id_str"),
            "author": {
                "name": qt_user.get("name", ""),
                "screen_name": qt_user.get("screen_name", ""),
            },
            "text": qt.get("text", ""),
            "favorite_count": qt.get("favorite_count", 0),
            "images": [],
        }
        for i, img in enumerate(_extract_image_urls(qt), 1):
            local = out_dir / f"source_quoted_{i}.jpg"
            if _download_image(img["url"], local):
                pkg["quoted"]["images"].append({
                    "url": img["url"],
                    "local_path": str(local.relative_to(ROOT)),
                    "width": img["width"],
                    "height": img["height"],
                })

    # X 长文 article(只有 preview · 全文需 OAuth · 现阶段只标记)
    if tweet.get("article"):
        art = tweet["article"]
        cover = (art.get("cover_media") or {}).get("media_info") or {}
        cover_url = cover.get("original_img_url")
        cover_local = None
        if cover_url:
            local = out_dir / "source_article_cover.jpg"
            if _download_image(cover_url, local):
                cover_local = str(local.relative_to(ROOT))
        pkg["article"] = {
            "rest_id": art.get("rest_id"),
            "title": art.get("title", ""),
            "preview_text": art.get("preview_text", ""),
            "cover_url": cover_url,
            "cover_local_path": cover_local,
            "note": "full body needs OAuth · 当前只有 preview",
        }

    return pkg


def fetch_multi(urls: list[str], *, slug: str | None = None) -> list[dict]:
    """一次抓多个 url · 用同一个 slug 目录归图。"""
    slug = slug or datetime.now().strftime("multi-%Y%m%d-%H%M%S")
    return [fetch_source(u, slug=slug) for u in urls]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+", help="Twitter / X status URL · 1 或多个")
    ap.add_argument("--slug", default=None, help="output/images/{slug}/ 目录名")
    ap.add_argument("--json-out", default=None, help="把结构化结果存到 JSON 文件")
    args = ap.parse_args()

    pkgs = fetch_multi(args.urls, slug=args.slug)
    for p in pkgs:
        print(f"\n=== {p['url']} ===")
        if not p.get("ok"):
            print(f"  ✗ {p.get('error', 'unknown')}")
            continue
        print(f"  author: {p['author']['name']} @{p['author']['screen_name']}")
        print(f"  text: {p['text'][:120]}")
        print(f"  images: {len(p.get('images', []))} 张")
        for img in p.get("images", []):
            print(f"    · {img['local_path']} · {img['width']}x{img['height']}")
        if p.get("quoted"):
            qt = p["quoted"]
            print(f"  quoted: @{qt['author']['screen_name']} · {qt['text'][:80]}")
            print(f"    images: {len(qt.get('images', []))} 张")
        if p.get("article"):
            art = p["article"]
            print(f"  article: {art['title']}")
            print(f"    preview: {art['preview_text'][:120]}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(pkgs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n✓ json 写入 {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
