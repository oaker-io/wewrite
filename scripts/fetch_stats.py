#!/usr/bin/env python3
"""
Fetch WeChat article statistics and update history.yaml.

Uses WeChat Data Analytics API to pull article performance:
  - /datacube/getarticlesummary (daily summary)
  - /datacube/getarticletotal (cumulative)

Usage:
    python3 fetch_stats.py
    python3 fetch_stats.py --days 7

Requires: wechat appid/secret in config.yaml (skill root or toolkit dir)
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

SKILL_DIR = Path(__file__).parent.parent
TOOLKIT_CONFIG_PATHS = [
    SKILL_DIR / "config.yaml",                      # skill root
    SKILL_DIR / "toolkit" / "config.yaml",           # toolkit dir
    Path.home() / ".config" / "wewrite" / "config.yaml",
    Path.cwd() / "config.yaml",
]


def _load_toolkit_config() -> dict:
    for p in TOOLKIT_CONFIG_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


def _get_access_token(appid: str, secret: str) -> str:
    resp = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
    )
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"Token error: {data}")
    return data["access_token"]


def fetch_article_summary(token: str, date: str) -> list[dict]:
    """
    Fetch daily article summary.
    API: POST /datacube/getarticlesummary
    date format: "2026-03-23"
    """
    resp = requests.post(
        "https://api.weixin.qq.com/datacube/getarticlesummary",
        params={"access_token": token},
        json={"begin_date": date, "end_date": date},
    )
    data = resp.json()
    if "list" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "")
        if errcode == 61500:
            # No data for this date (article not yet published or no reads)
            return []
        print(f"[warn] getarticlesummary error: {errcode} {errmsg}", file=sys.stderr)
        return []
    return data["list"]


def fetch_article_total(token: str, date: str) -> list[dict]:
    """
    Fetch cumulative article stats.
    API: POST /datacube/getarticletotal
    """
    resp = requests.post(
        "https://api.weixin.qq.com/datacube/getarticletotal",
        params={"access_token": token},
        json={"begin_date": date, "end_date": date},
    )
    data = resp.json()
    if "list" not in data:
        return []
    return data["list"]


def update_history(stats_list: list[dict]):
    """Match stats to history.yaml entries and update."""
    history_path = SKILL_DIR / "history.yaml"
    if not history_path.exists():
        print("No history.yaml found.")
        return

    with open(history_path, "r", encoding="utf-8") as f:
        history = yaml.safe_load(f) or {}

    articles = history.get("articles", [])
    if not articles:
        print("No articles in history to update.")
        return

    # Build a lookup by title for matching
    title_to_idx = {}
    for i, article in enumerate(articles):
        title_to_idx[article.get("title", "")] = i

    updated = 0
    for stat in stats_list:
        title = stat.get("title", "")
        if title in title_to_idx:
            idx = title_to_idx[title]
            articles[idx]["stats"] = {
                "read_count": stat.get("int_page_read_count", 0),
                "share_count": stat.get("share_count", 0),
                "like_count": stat.get("old_like_count", 0) + stat.get("like_count", 0),
                "read_rate": round(
                    stat.get("int_page_read_count", 0)
                    / max(stat.get("target_user", 1), 1)
                    * 100,
                    1,
                ),
            }
            updated += 1

    if updated > 0:
        history["articles"] = articles
        with open(history_path, "w", encoding="utf-8") as f:
            yaml.dump(history, f, allow_unicode=True, default_flow_style=False)
        print(f"Updated stats for {updated} article(s).")
    else:
        print("No matching articles found in stats data.")


def main():
    parser = argparse.ArgumentParser(description="Fetch WeChat article stats")
    parser.add_argument("--days", type=int, default=3, help="Days to look back")
    args = parser.parse_args()

    cfg = _load_toolkit_config()
    wechat_cfg = cfg.get("wechat", {})
    appid = wechat_cfg.get("appid")
    secret = wechat_cfg.get("secret")

    if not appid or not secret:
        print("Error: wechat appid/secret not found in config.yaml", file=sys.stderr)
        sys.exit(1)

    token = _get_access_token(appid, secret)
    print(f"Fetching stats for last {args.days} days...")

    all_stats = []
    for i in range(args.days):
        date = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")
        stats = fetch_article_summary(token, date)
        if stats:
            print(f"  {date}: {len(stats)} article(s)")
            all_stats.extend(stats)

    if all_stats:
        update_history(all_stats)
    else:
        print("No stats data found for the specified period.")

    # Also print summary
    print(f"\nTotal data points: {len(all_stats)}")
    for s in all_stats:
        title = s.get("title", "unknown")
        reads = s.get("int_page_read_count", 0)
        shares = s.get("share_count", 0)
        print(f"  [{reads} reads, {shares} shares] {title}")


if __name__ == "__main__":
    main()
