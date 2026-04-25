#!/usr/bin/env python3
"""fetch_kol.py · 每日凌晨 03:00 抓 KOL 公众号 RSS · 入 idea_bank。

为什么:
    用户精选 8-15 个头部 AI / 副业搞钱 KOL · 抓他们最近文章正文 → 抽 idea →
    进 idea_bank · 让 auto_pick 第二天选题时多一手头部对标素材。

依赖:
    - infra/wewe-rss/(本机 Docker)· 把 WeChat 公众号转 RSS
    - feedparser · 解析 RSS
    - config/kol_list.yaml · KOL 清单 + RSS url

数据流:
    1. 读 kol_list.yaml · status=active 的 KOL
    2. 每个 KOL fetch RSS · 取最近 daily_limit_per_kol 篇
    3. 去重(看 output/kol_corpus.yaml 30 天滑动窗口 · url + title hash)
    4. 新文章入 corpus · 同时调 _idea_bank.add(source="kol")
    5. push Discord 报告

幂等:重跑同一天不会重复入(去重指纹拦)。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import _idea_bank  # noqa: E402

KOL_LIST = ROOT / "config" / "kol_list.yaml"
KOL_CORPUS = ROOT / "output" / "kol_corpus.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def _now_dt() -> datetime:
    return datetime.now(_CST)


def _fingerprint(url: str, title: str) -> str:
    """url + title 双重 hash · url 不稳定时(短链跳转)title 兜底。"""
    raw = f"{(url or '').strip()}||{(title or '').strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# =================================================================
# kol_list.yaml IO
# =================================================================
def load_kol_list() -> dict:
    if not KOL_LIST.exists():
        print(f"❌ {KOL_LIST} 不存在 · 先建 KOL 清单", file=sys.stderr)
        sys.exit(1)
    return yaml.safe_load(KOL_LIST.read_text(encoding="utf-8")) or {}


def active_kols(data: dict) -> list[dict]:
    """返回 status=active 且 rss_url 非空的 KOL。"""
    return [
        k for k in (data.get("list") or [])
        if k.get("status") == "active" and (k.get("rss_url") or "").strip()
    ]


# =================================================================
# corpus.yaml IO + 去重
# =================================================================
def load_corpus() -> dict:
    if not KOL_CORPUS.exists():
        return {"last_fetched": None, "articles": []}
    return yaml.safe_load(KOL_CORPUS.read_text(encoding="utf-8")) or {
        "last_fetched": None, "articles": [],
    }


def save_corpus(corpus: dict) -> None:
    corpus["last_fetched"] = _now_iso()
    KOL_CORPUS.parent.mkdir(parents=True, exist_ok=True)
    KOL_CORPUS.write_text(
        yaml.safe_dump(corpus, allow_unicode=True, sort_keys=False, indent=2),
        encoding="utf-8",
    )


def prune_corpus(corpus: dict, *, window_days: int) -> dict:
    """删 window_days 天前的文章 · 防 corpus.yaml 无限增长。"""
    cutoff = _now_dt() - timedelta(days=window_days)
    keep: list[dict] = []
    for a in corpus.get("articles") or []:
        fetched_at = a.get("fetched_at") or ""
        try:
            dt = datetime.fromisoformat(fetched_at)
        except ValueError:
            keep.append(a)  # 没时间戳就保留 · 安全
            continue
        if dt >= cutoff:
            keep.append(a)
    corpus["articles"] = keep
    return corpus


def existing_fingerprints(corpus: dict, *, window_days: int) -> set[str]:
    """返回 window_days 天内 corpus 里所有指纹 · 用于去重。"""
    cutoff = _now_dt() - timedelta(days=window_days)
    out: set[str] = set()
    for a in corpus.get("articles") or []:
        fetched_at = a.get("fetched_at") or ""
        try:
            dt = datetime.fromisoformat(fetched_at)
        except ValueError:
            out.add(a.get("fingerprint", ""))
            continue
        if dt >= cutoff:
            out.add(a.get("fingerprint", ""))
    return out


# =================================================================
# RSS fetch
# =================================================================
def _html_to_md(html: str) -> str:
    """HTML → markdown · 用 html2text · 不折行(body_width=0)· 去图片 src 长串。"""
    if not html:
        return ""
    try:
        import html2text
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_images = False
        h.ignore_links = False
        h.skip_internal_links = True
        md = h.handle(html)
    except Exception:
        return html  # 兜底:返回 HTML 原文 · 让分析器跑 regex
    # mp.weixin.qq.com 图片 src 是超长 base64-like · 替成短占位
    md = re.sub(r'!\[([^\]]*)\]\([^)]{200,}\)', r'![\1](IMG)', md)
    return md.strip()


def fetch_rss(rss_url: str, *, limit: int = 5) -> list[dict]:
    """拉 RSS · 返回最多 limit 篇文章 · 每篇含 title/link/published/summary/content_md。

    失败返回空 list · 不抛(上层按 KOL 计 fail rate)。
    优先从 entry.content[0].value 取全文 · 没有 fallback summary。
    """
    import feedparser
    try:
        d = feedparser.parse(rss_url)
    except Exception as e:
        print(f"  ✗ RSS parse fail: {e}", file=sys.stderr)
        return []
    if d.bozo and not d.entries:
        print(f"  ✗ RSS bozo · {d.bozo_exception}", file=sys.stderr)
        return []
    out = []
    for entry in (d.entries or [])[:limit]:
        # 全文优先 entry.content[0].value(wewe-rss 这里给完整 HTML)
        content_html = ""
        contents = entry.get("content")
        if contents and isinstance(contents, list) and contents:
            content_html = (contents[0].get("value") or "").strip()
        # fallback summary
        summary = (entry.get("summary") or "").strip()
        if not content_html and summary:
            content_html = summary

        out.append({
            "title": (entry.get("title") or "").strip(),
            "link": (entry.get("link") or "").strip(),
            "published": entry.get("published") or entry.get("updated") or "",
            "summary": summary[:500],
            "content_md": _html_to_md(content_html),
        })
    return out


# =================================================================
# idea_bank 接入
# =================================================================
# KOL.tags[0] → idea_bank category 映射
_CATEGORY_MAP = {
    "商业": "flexible",
    "AI 工具": "tutorial",
    "副业": "flexible",
    "自媒体": "flexible",
    "设计": "tutorial",
    "AI": "tutorial",
    "广告": "flexible",
    "数字游民": "flexible",
    "案例": "flexible",
    "私域": "flexible",
    "IP": "flexible",
    "实战": "tutorial",
    "操盘": "flexible",
    "极客": "tutorial",
    "AIGC": "tutorial",
    "信息差": "flexible",
    "创业": "flexible",
    "段子": "flexible",
    "财经": "flexible",
    "搞钱": "flexible",
    "评测": "tutorial",
    "写作": "tutorial",
    "涨粉": "flexible",
    "复盘": "flexible",
    "远程": "flexible",
    "老炮": "flexible",
    "观察": "flexible",
    "框架": "tutorial",
    "工具": "tutorial",
}


def _kol_category(kol: dict) -> str:
    """KOL.tags 第一个有效标签 → idea_bank category。"""
    for t in kol.get("tags") or []:
        if t in _CATEGORY_MAP:
            return _CATEGORY_MAP[t]
    return "flexible"


def add_to_idea_bank(article: dict, kol: dict) -> int | None:
    """给一篇文章加进 idea_bank · 返回 idea_id · 失败返回 None。

    title 直接用 KOL 文章 title(不改 · 选题时让 LLM 决定怎么解构)。
    """
    title = article["title"]
    if not title:
        return None
    category = _kol_category(kol)
    notes = (
        f"from KOL: {kol.get('name', '?')} · {article.get('published', '?')[:10]}"
        f"\nurl: {article.get('link', '')}"
        f"\nsummary: {article.get('summary', '')[:200]}"
    )
    try:
        rec = _idea_bank.add(
            title=title,
            category=category,
            source="kol",
            priority=int(kol.get("weight", 50)),
            tags=list(kol.get("tags") or []),
            notes=notes,
        )
        return rec["id"]
    except Exception as e:
        print(f"  ✗ idea_bank add fail: {e}", file=sys.stderr)
        return None


# =================================================================
# Discord push
# =================================================================
def push_discord(text: str) -> None:
    """推 Discord · 失败静默(不阻断 fetch 主流程)。"""
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            timeout=30,
            check=False,
        )
    except Exception:
        pass


# =================================================================
# 主流程
# =================================================================
_SEED_ARTICLES = [
    {
        "title": "Cursor 估值 100 亿背后:3 个非共识真相",
        "kol": "刘润", "weight": 90, "tags": ["商业", "案例"],
        "content_md": (
            "## 估值不是关键\n\n"
            "昨晚刷到一条新闻 · Cursor 估值 100 亿。\n\n"
            "评论区一堆 「AI 泡沫」 「不过是套壳」。\n\n"
            "我看了 3 天财报 + 用户访谈数据 · 有 3 个真相被忽略了。\n\n"
            "## 真相 1:用户黏性 90%\n\n"
            "Cursor 月留存 87% · 比 Notion 还高 12 个百分点。\n\n"
            "这意味着开发者把它当成 IDE · 不是工具。\n\n"
            "**工具会被替换 · IDE 不会。**\n\n"
            "## 真相 2:ARR 8 亿\n\n"
            "去年这时候 ARR 才 1 亿 · 一年 8x 增长。\n\n"
            "这种增速 · 就算 SaaS 历史上也罕见。"
        ),
    },
    {
        "title": "我用 Claude 跑了 7 天副业 · 月入 3 万的真实拆解",
        "kol": "木马人AI", "weight": 85, "tags": ["AI 工具", "副业", "实战"],
        "content_md": (
            "## Day 0:为什么是 Claude\n\n"
            "上周朋友问我 · 现在做 AI 副业还来得及吗?\n\n"
            "**来得及 · 但窗口只剩 6 个月。**\n\n"
            "我跑了 7 天 · 用 Claude 接了 12 个单 · 月入折算 3 万。\n\n"
            "今天把全部流程拆给你。\n\n"
            "## Day 1-3:找到第一个客户\n\n"
            "不是去 Upwork · 是去小红书评论区。\n\n"
            "搜 「想做 AI 但不会用」 · 评论 3 句话 · 加微信。\n\n"
            "成单率 12% · 比 Upwork 高 8 倍。"
        ),
    },
    {
        "title": "5 个钩子让你的公众号文章打开率 +40%",
        "kol": "粥左罗", "weight": 90, "tags": ["自媒体", "写作", "涨粉"],
        "content_md": (
            "## 钩子是开篇 30 秒\n\n"
            "我看了 1000 篇打开率 10%+ 的文章。\n\n"
            "97% 都用了下面这 5 种钩子之一。\n\n"
            "## 钩子 1:数字反共识\n\n"
            "「为什么 90% 的人在 Cursor 上花了冤枉钱」\n\n"
            "数字 + 反常识 · 直接抓眼。"
        ),
    },
    {
        "title": "AI 创业的 3 个大坑 · 我踩了 2 个",
        "kol": "caoz 的梦呓", "weight": 80, "tags": ["商业", "观察"],
        "content_md": (
            "## 坑 1:别迷信「技术壁垒」\n\n"
            "去年我投了一个项目 · CEO 说有「核心算法壁垒」。\n\n"
            "今年开源模型一出 · 壁垒没了。\n\n"
            "**真正的壁垒是数据 + 用户习惯 · 不是技术。**"
        ),
    },
    {
        "title": "卡兹克教你 5 分钟做一张 AI 海报 · 还能商用",
        "kol": "数字生命卡兹克", "weight": 80, "tags": ["AI 工具", "实战"],
        "content_md": (
            "## 工具 = Midjourney V7 + GPT-4o\n\n"
            "上周我做的 AI 海报 · 客户一张给 800。\n\n"
            "5 分钟一张 · 一晚上做 6 张 · 折合时薪 ~600。\n\n"
            "## Step 1:用 GPT-4o 写 prompt\n\n"
            "把客户需求扔给 4o · 让它生成 V7 风格 prompt。\n\n"
            "「商业海报 · 留白 · 极简 · 字体 SourceHanSans」"
        ),
    },
]


def _seed_corpus() -> None:
    """塞 5 篇假文章进 corpus + idea_bank · 用户没起 wewe-rss 也能验证 P2/P3 链路。"""
    print("→ seeding 5 fake KOL articles...")
    corpus = load_corpus()
    seen_fps = existing_fingerprints(corpus, window_days=30)
    new_articles: list[dict] = []
    for i, seed in enumerate(_SEED_ARTICLES):
        url = f"https://mp.weixin.qq.com/s/seed-{i+1}"
        fp = _fingerprint(url, seed["title"])
        if fp in seen_fps:
            print(f"  · skip(dup): {seed['title'][:40]}")
            continue
        kol_record = {
            "name": seed["kol"], "handle": seed["kol"].lower().replace(" ", "_"),
            "weight": seed["weight"], "tags": seed["tags"],
        }
        article = {
            "kol": seed["kol"],
            "kol_handle": kol_record["handle"],
            "title": seed["title"],
            "url": url,
            "pub_date": datetime.now(_CST).strftime("%Y-%m-%d"),
            "summary": seed["content_md"][:200],
            "content_md": seed["content_md"],
            "fetched_at": _now_iso(),
            "fingerprint": fp,
            "idea_id": None,
            "weight": seed["weight"],
            "tags": seed["tags"],
        }
        idea_id = add_to_idea_bank(
            {"title": seed["title"], "summary": seed["content_md"][:200],
             "link": url, "published": article["pub_date"]},
            kol_record,
        )
        article["idea_id"] = idea_id
        new_articles.append(article)
        print(f"  + seed: [{idea_id}] {seed['title'][:50]}")

    corpus["articles"] = (corpus.get("articles") or []) + new_articles
    save_corpus(corpus)
    print(f"✓ seeded {len(new_articles)} 篇 → output/kol_corpus.yaml")
    print(f"  下一步:venv/bin/python3 scripts/analyze_kol.py --no-push")


def main() -> int:
    p = argparse.ArgumentParser(description="抓 KOL 公众号 RSS · 入 idea_bank")
    p.add_argument("--dry-run", action="store_true",
                   help="不写文件 · 不入 idea_bank · 只打印")
    p.add_argument("--no-push", action="store_true",
                   help="不 push Discord(测试用)")
    p.add_argument("--kol", default=None,
                   help="只跑某一个 KOL(填 name 或 handle · debug 用)")
    p.add_argument("--seed", action="store_true",
                   help="塞 5 篇假文章进 corpus + idea_bank · 测试 P2/P3 链路用")
    args = p.parse_args()

    if args.seed:
        _seed_corpus()
        return 0

    data = load_kol_list()
    fetch_cfg = data.get("fetch") or {}
    daily_limit = int(fetch_cfg.get("daily_limit_per_kol", 5))
    window_days = int(fetch_cfg.get("dedupe_window_days", 30))

    kols = active_kols(data)
    if args.kol:
        kols = [k for k in kols if args.kol in (k.get("name") or "")
                or args.kol == k.get("handle")]
    if not kols:
        msg = "⚠ 0 个 active KOL · kol_list.yaml 里 status=active 且 rss_url 非空才会跑"
        print(msg, file=sys.stderr)
        if not args.no_push:
            push_discord(f"📚 KOL fetch · {msg}")
        return 0

    print(f"→ 跑 {len(kols)} 个 KOL · daily_limit={daily_limit} · window={window_days}d")

    corpus = load_corpus()
    corpus = prune_corpus(corpus, window_days=window_days)
    seen_fps = existing_fingerprints(corpus, window_days=window_days)

    new_articles: list[dict] = []
    new_idea_ids: list[int] = []
    per_kol_stats: list[tuple[str, int, int]] = []  # (name, fetched, added)
    rss_failures: list[str] = []

    for kol in kols:
        name = kol.get("name", "?")
        rss_url = kol.get("rss_url", "")
        print(f"\n[{name}] {rss_url}")

        entries = fetch_rss(rss_url, limit=daily_limit)
        if not entries:
            rss_failures.append(name)
            print(f"  ⚠ 0 篇 · 跳过")
            per_kol_stats.append((name, 0, 0))
            continue

        added_this_kol = 0
        for entry in entries:
            fp = _fingerprint(entry["link"], entry["title"])
            if fp in seen_fps:
                print(f"  · skip(dup): {entry['title'][:40]}")
                continue
            seen_fps.add(fp)

            # 入 idea_bank
            idea_id = None
            if not args.dry_run:
                idea_id = add_to_idea_bank(entry, kol)
                if idea_id is not None:
                    new_idea_ids.append(idea_id)

            # 入 corpus
            article = {
                "kol": name,
                "kol_handle": kol.get("handle", ""),
                "title": entry["title"],
                "url": entry["link"],
                "pub_date": entry["published"][:25],
                "summary": entry["summary"],
                "content_md": entry.get("content_md", ""),
                "fetched_at": _now_iso(),
                "fingerprint": fp,
                "idea_id": idea_id,
                "weight": kol.get("weight", 50),
                "tags": list(kol.get("tags") or []),
            }
            new_articles.append(article)
            added_this_kol += 1
            print(f"  + new: [{idea_id}] {entry['title'][:50]}")

        per_kol_stats.append((name, len(entries), added_this_kol))

    if not args.dry_run:
        corpus["articles"] = (corpus.get("articles") or []) + new_articles
        save_corpus(corpus)

    # 报告
    total_fetched = sum(f for _, f, _ in per_kol_stats)
    total_added = sum(a for _, _, a in per_kol_stats)
    print(f"\n=== KOL fetch 完成 ===")
    print(f"  KOL 数:{len(kols)} · 抓:{total_fetched} 篇 · 新入库:{total_added} 篇")
    print(f"  idea_bank +{len(new_idea_ids)} 条")
    if rss_failures:
        print(f"  ⚠ RSS 抓失败:{', '.join(rss_failures)}")

    if not args.no_push:
        # Discord 报告(限 2000 字)
        lines = [
            f"📚 **KOL fetch · {datetime.now(_CST).strftime('%m-%d %H:%M')}**",
            f"KOL:{len(kols)} · 抓:{total_fetched} · 新入库:{total_added} · idea_bank +{len(new_idea_ids)}",
        ]
        if rss_failures:
            lines.append(f"⚠ RSS 失败:{', '.join(rss_failures[:5])}")
            lines.append("(可能 wewe-rss cookie 失效 · 浏览器开 http://localhost:4000 重扫码)")
        if total_added > 0:
            lines.append("\n**新入库 Top 5**:")
            for a in new_articles[:5]:
                lines.append(f"  - [{a['kol']}] {a['title'][:50]}")
        push_discord("\n".join(lines))

    return 0 if total_added > 0 or not kols else 1


if __name__ == "__main__":
    sys.exit(main())
