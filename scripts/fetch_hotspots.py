#!/usr/bin/env python3
"""
Fetch trending topics from multiple Chinese platforms.

Sources (all attempted in parallel, results merged and deduplicated):
  1. Weibo hot search (weibo.com/ajax/side/hotSearch)
  2. Toutiao hot board (toutiao.com/hot-event/hot-board)
  3. Baidu hot search (top.baidu.com/api/board)

Usage:
    python3 fetch_hotspots.py --limit 20
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

import requests

TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def fetch_weibo() -> list[dict]:
    """Fetch Weibo hot search."""
    try:
        resp = requests.get(
            "https://weibo.com/ajax/side/hotSearch",
            headers={**HEADERS, "Referer": "https://weibo.com/"},
            timeout=TIMEOUT,
        )
        data = resp.json()
        items = []
        for entry in data.get("data", {}).get("realtime", []):
            note = entry.get("note", "")
            if not note:
                continue
            items.append({
                "title": note,
                "source": "微博",
                "hot": entry.get("num", 0),
                "url": f"https://s.weibo.com/weibo?q=%23{note}%23",
                "description": entry.get("label_name", ""),
            })
        return items
    except Exception as e:
        print(f"[warn] weibo failed: {e}", file=sys.stderr)
        return []


def fetch_toutiao() -> list[dict]:
    """Fetch Toutiao hot board."""
    try:
        resp = requests.get(
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        data = resp.json()
        items = []
        for entry in data.get("data", []):
            title = entry.get("Title", "")
            if not title:
                continue
            items.append({
                "title": title,
                "source": "今日头条",
                "hot": int(entry.get("HotValue", 0) or 0),
                "url": entry.get("Url", ""),
                "description": "",
            })
        return items
    except Exception as e:
        print(f"[warn] toutiao failed: {e}", file=sys.stderr)
        return []


def fetch_baidu() -> list[dict]:
    """Fetch Baidu hot search."""
    try:
        resp = requests.get(
            "https://top.baidu.com/api/board?platform=wise&tab=realtime",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        data = resp.json()
        items = []
        # Baidu nests items inside cards[0].content[0].content
        for card in data.get("data", {}).get("cards", []):
            top_content = card.get("content", [])
            if not top_content:
                continue
            entries = top_content[0].get("content", []) if isinstance(top_content[0], dict) else top_content
            for entry in entries:
                word = entry.get("word", "")
                if not word:
                    continue
                items.append({
                    "title": word,
                    "source": "百度",
                    "hot": int(entry.get("hotScore", 0) or 0),
                    "url": entry.get("url", ""),
                    "description": "",
                })
        return items
    except Exception as e:
        print(f"[warn] baidu failed: {e}", file=sys.stderr)
        return []


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicates by exact title match."""
    seen = set()
    result = []
    for item in items:
        title = item["title"].strip()
        if title and title not in seen:
            seen.add(title)
            result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch trending topics")
    parser.add_argument("--limit", type=int, default=20, help="Max items to return")
    args = parser.parse_args()

    all_items = []
    sources_ok = []
    sources_fail = []

    for name, fetcher in [("weibo", fetch_weibo), ("toutiao", fetch_toutiao), ("baidu", fetch_baidu)]:
        items = fetcher()
        if items:
            sources_ok.append(name)
            all_items.extend(items)
        else:
            sources_fail.append(name)

    all_items = deduplicate(all_items)

    # Normalize hot values across platforms (different scales: toutiao ~10M, weibo ~1M, baidu ~100K)
    # Strategy: within each source, rank-based score 0-100, so cross-platform sorting is fair
    by_source: dict[str, list[dict]] = {}
    for item in all_items:
        by_source.setdefault(item["source"], []).append(item)

    for source, items in by_source.items():
        items.sort(key=lambda x: int(x.get("hot", 0) or 0), reverse=True)
        n = len(items)
        for rank, item in enumerate(items):
            # Top item = 100, linear decay to ~1 for last item
            item["hot_normalized"] = round(100 * (n - rank) / n, 1) if n > 0 else 0

    all_items.sort(key=lambda x: x.get("hot_normalized", 0), reverse=True)
    all_items = all_items[:args.limit]

    tz = timezone(timedelta(hours=8))
    output = {
        "timestamp": datetime.now(tz).isoformat(),
        "sources": sources_ok,
        "sources_failed": sources_fail,
        "count": len(all_items),
        "items": all_items,
    }

    if not all_items:
        output["error"] = "All sources failed. SKILL.md should fall back to WebSearch."

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
