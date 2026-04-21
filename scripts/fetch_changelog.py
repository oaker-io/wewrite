#!/usr/bin/env python3
"""fetch_changelog.py · 抓取官方/社区 changelog · 写入 idea_bank。

3 个数据源:
    1. anthropic-blog       https://www.anthropic.com/news
    2. anthropic-changelog  https://docs.anthropic.com/en/release-notes/api
    3. github-trending      https://github.com/trending?since=daily(过滤 AI)

用法:
    python3 fetch_changelog.py
    python3 fetch_changelog.py --source github-trending --limit 5
    python3 fetch_changelog.py --dry-run

设计公约:
    - 每个源独立 fetch · 失败不影响其他
    - 去重:title case-insensitive substring 比对 idea_bank 已有
    - dry-run 只打印 · 不落盘
    - HTTP timeout=15 · 浏览器 UA 防拦
    - 不调 LLM · 字符串模板转化标题
"""
from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path

import requests

# 让我们能 import _idea_bank
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "workflow"))
import _idea_bank  # noqa: E402

try:
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


SOURCES = ("all", "anthropic-blog", "anthropic-changelog", "github-trending")
TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# AI 关键词 · 用于过滤 GitHub trending
_AI_KEYWORDS = (
    "ai", "llm", "agent", "claude", "cursor", "gpt", "openai", "anthropic",
    "rag", "mcp", "gemini", "ollama", "langchain", "embedding", "transformer",
    "diffusion", "stable-diffusion", "vector", "vllm", "fine-tun", "prompt",
    "chatbot", "copilot", "deepseek", "qwen", "llama", "huggingface",
    "vision", "multimodal", "neural", "machine-learning",
)


# ============================================================
# HTTP helper
# ============================================================
def _http_get(url: str, *, extra_headers: dict | None = None) -> str | None:
    """GET → text · 失败返回 None。"""
    try:
        h = dict(HEADERS)
        if extra_headers:
            h.update(extra_headers)
        resp = requests.get(url, headers=h, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[warn] GET {url} failed: {e}", file=sys.stderr)
        return None


# ============================================================
# Source 1 · Anthropic news
# ============================================================
def fetch_anthropic_blog(limit: int = 10) -> list[dict]:
    """抓 https://www.anthropic.com/news · 返回 [{title, url, transformed_title}]。"""
    html = _http_get("https://www.anthropic.com/news")
    if not html:
        return []

    items: list[dict] = []
    seen = set()

    # 策略 A: BS4 解析 <a href="/news/..."> · 取链接文字
    if _HAS_BS4:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("/news/"):
                    continue
                # 跳过 /news 自身
                if href.rstrip("/") == "/news":
                    continue
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 8:
                    continue
                if title in seen:
                    continue
                seen.add(title)
                full_url = "https://www.anthropic.com" + href
                items.append({
                    "raw_title": title,
                    "url": full_url,
                })
                if len(items) >= limit:
                    break
        except Exception as e:
            print(f"[warn] anthropic blog BS4 parse failed: {e}", file=sys.stderr)

    # 策略 B (兜底 / 补充): regex 从 a tag 提取
    if not items:
        pattern = re.compile(
            r'<a[^>]+href="(/news/[^"#?]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern.finditer(html):
            href, inner = m.group(1), m.group(2)
            # 剥 inner 的所有 tag 取纯文本
            text = re.sub(r"<[^>]+>", " ", inner)
            text = unescape(re.sub(r"\s+", " ", text)).strip()
            if not text or len(text) < 8:
                continue
            if text in seen:
                continue
            seen.add(text)
            items.append({
                "raw_title": text,
                "url": "https://www.anthropic.com" + href,
            })
            if len(items) >= limit:
                break

    # 转化标题 · 标准模板
    for item in items:
        item["transformed_title"] = f"读懂 Anthropic 官方动态:{item['raw_title']}"

    return items


# ============================================================
# Source 2 · Anthropic API release notes
# ============================================================
def fetch_anthropic_changelog(limit: int = 10) -> list[dict]:
    """抓 docs.anthropic.com release notes · 失败 fallback 到通用页。"""
    candidates = [
        "https://docs.anthropic.com/en/release-notes/api",
        "https://docs.anthropic.com/en/release-notes",
    ]
    html = None
    for url in candidates:
        html = _http_get(url)
        if html:
            break
    if not html:
        return []

    items: list[dict] = []
    seen = set()

    # release notes 页面通常用 H2/H3 列条目 · 抓所有 heading 文本
    headings: list[str] = []
    if _HAS_BS4:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["h2", "h3"]):
                txt = tag.get_text(" ", strip=True)
                if txt:
                    headings.append(txt)
        except Exception as e:
            print(f"[warn] anthropic changelog BS4 parse failed: {e}", file=sys.stderr)

    if not headings:
        # regex 兜底
        pattern = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.DOTALL | re.IGNORECASE)
        for m in pattern.finditer(html):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = unescape(re.sub(r"\s+", " ", text)).strip()
            if text:
                headings.append(text)

    # 过滤太短或导航类条目
    skip_words = {"on this page", "search", "navigation", "table of contents"}
    for h in headings:
        if len(h) < 6:
            continue
        if h.lower() in skip_words:
            continue
        if h in seen:
            continue
        seen.add(h)
        items.append({
            "raw_title": h,
            "url": candidates[0],
        })
        if len(items) >= limit:
            break

    for item in items:
        item["transformed_title"] = f"Claude API 更新:{item['raw_title']}"

    return items


# ============================================================
# Source 3 · GitHub trending
# ============================================================
def _is_ai_relevant(text: str) -> bool:
    """简单关键词匹配:描述/topics 含 AI 相关词。"""
    if not text:
        return False
    low = text.lower()
    return any(kw in low for kw in _AI_KEYWORDS)


def fetch_github_trending(limit: int = 10) -> list[dict]:
    """抓 https://github.com/trending?since=daily · 过滤 AI 相关。"""
    html = _http_get("https://github.com/trending?since=daily")
    if not html:
        return []

    items: list[dict] = []
    seen = set()

    if _HAS_BS4:
        try:
            soup = BeautifulSoup(html, "html.parser")
            # GitHub trending 列表用 article.Box-row
            for art in soup.select("article.Box-row"):
                # repo 链接在 h2 > a
                h2 = art.find("h2")
                if not h2:
                    continue
                link = h2.find("a", href=True)
                if not link:
                    continue
                href = link["href"].strip()
                # repo: /owner/name
                repo_name = href.lstrip("/").strip()
                if not repo_name or "/" not in repo_name:
                    continue

                # 描述
                desc_tag = art.find("p")
                description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

                # 语言
                lang_tag = art.find("span", itemprop="programmingLanguage")
                language = lang_tag.get_text(strip=True) if lang_tag else ""

                # AI 过滤:repo 名 + 描述 + 语言三者任一含 AI 词
                combined = f"{repo_name} {description} {language}"
                if not _is_ai_relevant(combined):
                    continue

                if repo_name in seen:
                    continue
                seen.add(repo_name)

                items.append({
                    "repo": repo_name,
                    "description": description,
                    "language": language,
                    "url": "https://github.com" + ("/" + href.lstrip("/")),
                })
                if len(items) >= limit:
                    break
        except Exception as e:
            print(f"[warn] github trending BS4 parse failed: {e}", file=sys.stderr)

    # regex 兜底:抓 article.Box-row 内的 h2/a + p
    if not items:
        # 切片每个 article 块
        article_re = re.compile(
            r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
            re.DOTALL | re.IGNORECASE,
        )
        href_re = re.compile(r'<h2[^>]*>.*?<a[^>]+href="([^"]+)"', re.DOTALL)
        desc_re = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
        lang_re = re.compile(
            r'itemprop="programmingLanguage"[^>]*>(.*?)<', re.DOTALL
        )
        for m in article_re.finditer(html):
            block = m.group(1)
            href_m = href_re.search(block)
            if not href_m:
                continue
            href = href_m.group(1).strip()
            repo_name = href.lstrip("/").strip()
            if not repo_name or "/" not in repo_name:
                continue

            desc_m = desc_re.search(block)
            description = ""
            if desc_m:
                description = re.sub(r"<[^>]+>", " ", desc_m.group(1))
                description = unescape(re.sub(r"\s+", " ", description)).strip()

            lang_m = lang_re.search(block)
            language = ""
            if lang_m:
                language = re.sub(r"<[^>]+>", " ", lang_m.group(1)).strip()

            combined = f"{repo_name} {description} {language}"
            if not _is_ai_relevant(combined):
                continue
            if repo_name in seen:
                continue
            seen.add(repo_name)
            items.append({
                "repo": repo_name,
                "description": description,
                "language": language,
                "url": "https://github.com/" + repo_name,
            })
            if len(items) >= limit:
                break

    # 转化标题
    for item in items:
        repo = item["repo"]
        desc = item["description"]
        if desc:
            # 描述截 60 字
            short_desc = desc[:60].rstrip() + ("…" if len(desc) > 60 else "")
            item["transformed_title"] = (
                f"GitHub 今日热门 AI 项目:{repo} · {short_desc}"
            )
        else:
            item["transformed_title"] = f"GitHub 今日热门 AI 项目:{repo}"

    return items


# ============================================================
# Dedupe vs idea_bank
# ============================================================
def _is_duplicate(title: str, existing_titles_lower: list[str]) -> bool:
    """case-insensitive · title 完全等于 或 互为 substring 视为重复。"""
    if not title:
        return True
    t = title.strip().lower()
    if not t:
        return True
    for e in existing_titles_lower:
        if not e:
            continue
        if t == e or t in e or e in t:
            return True
    return False


# ============================================================
# Main pipeline
# ============================================================
def _truncate(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _add_with_log(
    transformed_title: str,
    *,
    category: str,
    source: str,
    tags: list[str],
    notes: str,
    source_label: str,
    dry_run: bool,
) -> dict | None:
    """加一条 idea + 打 log · dry-run 时只打不写。"""
    if dry_run:
        print(f"+ [dry] [{source_label}] {_truncate(transformed_title)}")
        return None
    try:
        rec = _idea_bank.add(
            transformed_title,
            category=category,
            source=source,
            priority=50,
            tags=tags,
            notes=notes,
        )
        print(f"+ #{rec['id']} [{source_label}] {_truncate(rec['title'])}")
        return rec
    except Exception as e:
        print(f"[warn] add idea failed: {e!r} · title={transformed_title!r}",
              file=sys.stderr)
        return None


def run(
    *,
    source: str = "all",
    limit: int = 10,
    dry_run: bool = False,
) -> dict:
    """主流程 · 返回 stats dict。"""
    if source not in SOURCES:
        raise ValueError(f"source 必须 ∈ {SOURCES}")

    # 已有 titles · case-insensitive
    existing_titles_lower: list[str] = []
    try:
        existing = _idea_bank.list_ideas(only_unused=False, limit=None)
        existing_titles_lower = [
            (i.get("title") or "").strip().lower() for i in existing
        ]
    except Exception as e:
        print(f"[warn] load existing idea_bank failed: {e}", file=sys.stderr)

    stats = {
        "fetched": 0,
        "added": 0,
        "duplicates": 0,
        "by_source": {},
        "failed_sources": [],
    }

    plan = []
    if source in ("all", "anthropic-blog"):
        plan.append(("anthropic-blog", fetch_anthropic_blog))
    if source in ("all", "anthropic-changelog"):
        plan.append(("anthropic-changelog", fetch_anthropic_changelog))
    if source in ("all", "github-trending"):
        plan.append(("github-trending", fetch_github_trending))

    for src_name, fetcher in plan:
        print(f"== {src_name} ==", file=sys.stderr)
        try:
            items = fetcher(limit=limit)
        except Exception as e:
            print(f"[warn] {src_name} fetch raised: {e!r}", file=sys.stderr)
            stats["failed_sources"].append(src_name)
            continue

        if not items:
            stats["failed_sources"].append(src_name)
            print(f"[warn] {src_name} returned 0 items", file=sys.stderr)
            continue

        stats["fetched"] += len(items)
        added_here = 0
        dup_here = 0

        for item in items:
            title = item.get("transformed_title", "").strip()
            if not title:
                continue
            if _is_duplicate(title, existing_titles_lower):
                dup_here += 1
                stats["duplicates"] += 1
                continue

            # 决定 category / source / tags
            if src_name == "anthropic-blog":
                cat, src_field = "tutorial", "changelog"
                tags = ["anthropic", "official"]
                notes = item.get("url", "")
            elif src_name == "anthropic-changelog":
                cat, src_field = "tutorial", "changelog"
                tags = ["anthropic", "claude", "api"]
                notes = item.get("url", "")
            else:  # github-trending
                cat, src_field = "tutorial", "github"
                tags = ["github", "trending"]
                lang = (item.get("language") or "").strip()
                if lang:
                    tags.append(lang.lower())
                notes = item.get("url", "")

            rec = _add_with_log(
                title,
                category=cat,
                source=src_field,
                tags=tags,
                notes=notes,
                source_label=src_name,
                dry_run=dry_run,
            )
            if rec is not None or dry_run:
                added_here += 1
                stats["added"] += 1
                # 加入 existing 防本批内部重复
                existing_titles_lower.append(title.lower())

        stats["by_source"][src_name] = {
            "fetched": len(items),
            "added": added_here,
            "duplicates": dup_here,
        }

    return stats


def _print_stats(stats: dict, dry_run: bool) -> None:
    suffix = " (dry-run)" if dry_run else ""
    print(f"\n=== stats{suffix} ===")
    print(f"fetched={stats['fetched']} · added={stats['added']} · "
          f"duplicates={stats['duplicates']}")
    for src, s in stats["by_source"].items():
        print(f"  {src}: fetched={s['fetched']} added={s['added']} "
              f"dup={s['duplicates']}")
    if stats["failed_sources"]:
        print(f"failed sources: {', '.join(stats['failed_sources'])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="抓 changelog/news/trending · 自动入 idea_bank"
    )
    parser.add_argument(
        "--source", choices=SOURCES, default="all",
        help="数据源(默认 all)",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="每个源最多抓多少条(默认 10)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印不写入 idea_bank",
    )
    args = parser.parse_args()

    stats = run(source=args.source, limit=args.limit, dry_run=args.dry_run)
    _print_stats(stats, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
