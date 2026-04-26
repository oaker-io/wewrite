"""source_finder.py · 给 idea title · 找 Top 3 Twitter 候选 url。

L1(MVP):用户给 url(走 source_fetcher 即可 · 不需此模块)
L2(本周):WebSearch 用 site:x.com / site:twitter.com 找候选 → LLM 排序
L3(后续):xAI Grok API · 真做 Twitter 实时搜索

WebSearch 限制:
  - WebSearch tool 只在 Claude Code session 里能调
  - 此脚本独立跑时没 WebSearch · 退化到 fallback:用 Bing/Google 通用 web 搜
  - 公开搜索拿到的 url 可能是 nitter mirror · 转回 x.com URL 给 source_fetcher
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _normalize_to_x_url(url: str) -> str:
    """把 nitter / fxtwitter / mobile.twitter.com 之类 url 全部转回 x.com 形式。"""
    if not url:
        return url
    url = re.sub(r"https?://(?:mobile\.)?(?:twitter\.com|x\.com)", "https://x.com", url)
    url = re.sub(r"https?://nitter\.[^/]+", "https://x.com", url)
    url = re.sub(r"https?://(?:api\.)?fxtwitter\.com", "https://x.com", url)
    return url


def search_via_duckduckgo(query: str, *, limit: int = 10) -> list[dict]:
    """DuckDuckGo HTML endpoint(no auth · 不靠 webfetch)· 返回 url+title list。

    fail-safe · 网络挂直接返 [] · 不抛。
    """
    q = urllib.parse.quote_plus(f"{query} site:x.com")
    ddg_url = f"https://duckduckgo.com/html/?q={q}"
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", "20",
             "-H", "User-Agent: Mozilla/5.0",
             ddg_url],
            capture_output=True, text=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        return []
    if r.returncode != 0:
        return []
    html = r.stdout
    # 解析 result link · DDG html 结果格式 <a class="result__a" href="...">
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    out: list[dict] = []
    for m in pattern.finditer(html):
        href, title = m.group(1), m.group(2).strip()
        # DDG 包了一层 redirect: //duckduckgo.com/l/?uddg=URL_ENCODED&...
        rd = re.search(r"uddg=([^&]+)", href)
        if rd:
            href = urllib.parse.unquote(rd.group(1))
        href = _normalize_to_x_url(href)
        if "/status/" not in href:
            continue
        out.append({"url": href, "title": title, "source": "ddg"})
        if len(out) >= limit:
            break
    return out


def search_via_bing(query: str, *, limit: int = 10) -> list[dict]:
    """Bing 公开 search(无需 key)· 兜底。"""
    q = urllib.parse.quote_plus(f"{query} site:x.com")
    url = f"https://www.bing.com/search?q={q}"
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", "20",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             url],
            capture_output=True, text=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        return []
    if r.returncode != 0:
        return []
    html = r.stdout
    # bing 结果 url 在 <h2><a href="REAL_URL">
    pattern = re.compile(r'<h2><a[^>]+href="([^"]+)"', re.IGNORECASE)
    out: list[dict] = []
    for m in pattern.finditer(html):
        href = _normalize_to_x_url(m.group(1))
        if "/status/" not in href:
            continue
        if any(o["url"] == href for o in out):
            continue
        out.append({"url": href, "title": "", "source": "bing"})
        if len(out) >= limit:
            break
    return out


def find_candidates(query: str, *, limit: int = 5) -> list[dict]:
    """主入口 · 给 idea title · 返回 Top N 候选 Twitter url。"""
    cands = search_via_duckduckgo(query, limit=limit * 2)
    if len(cands) < limit:
        cands += search_via_bing(query, limit=limit * 2)
    # dedup 保序
    seen = set()
    out: list[dict] = []
    for c in cands:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        out.append(c)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="选题 idea title · 用来做搜索关键词")
    ap.add_argument("--limit", type=int, default=5, help="返回最多 N 个候选")
    ap.add_argument("--json-out", default=None, help="结果存到 JSON 文件")
    args = ap.parse_args()

    print(f"=== 搜:{args.query} ===")
    cands = find_candidates(args.query, limit=args.limit)
    if not cands:
        print("⚠ 0 候选 · search 没结果 · 用户手动给 url 吧")
        return 1
    for c in cands:
        print(f"  · [{c['source']}] {c['url']}")
        if c.get("title"):
            print(f"    {c['title'][:80]}")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(cands, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n✓ {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
