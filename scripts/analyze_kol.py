#!/usr/bin/env python3
"""analyze_kol.py · P2 · 从 KOL corpus 抽 metadata 4 层 → output/kol_patterns.yaml。

为什么:
    P1 的 fetch_kol.py 把 KOL 文章原始内容入 corpus · P2 这里抽 4 层模式给 P3 的
    write.py prompt 用 · 让自动写文时能"对标今日头部"。

4 层 metadata:
    选题层  · title / hook(首段)/ kw(关键词)
    结构层  · h2_count / paragraph_count / avg_para_chars / single_sent_para_ratio / image_count
    风格层  · emoji / exclaim density / number density / bold count / ellipsis
    传播层  · 暂跳过 · P4 接付费 API 时再做

输出 output/kol_patterns.yaml · write.py 在 prompt 里 inject「今日头部 5 条钩子 + 结构基线」。

跑法:
    venv/bin/python3 scripts/analyze_kol.py            # 默认 7 天滑动窗
    venv/bin/python3 scripts/analyze_kol.py --days 3   # 短窗口
    venv/bin/python3 scripts/analyze_kol.py --no-push  # 不 push Discord
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KOL_CORPUS = ROOT / "output" / "kol_corpus.yaml"
KOL_PATTERNS = ROOT / "output" / "kol_patterns.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


# =================================================================
# 选题层 · title / hook / kw
# =================================================================
_BOILERPLATE_PATTERNS = (
    "这是", "第 ", "关注公众号", "订阅", "星标", "置顶", "作者 l", "作者|", "作者 |",
    "编辑 l", "编辑|", "编辑 |", "分享 l", "分享|", "分享 |", "ID：", "ID:",
    "百万互联网", "向上生长", "**▲", "▲**", "未经授权",
    "点进去后", "预约所有直播", "免费听课", "每日推送", "每天分享",
)


def _is_boilerplate(line: str) -> bool:
    """KOL 文章常见首段 boilerplate · 这种段不算钩子。"""
    s = line.strip()
    if not s:
        return True
    # 短行(< 8 字)+ 含模板词 · 极可能是签名行
    for pat in _BOILERPLATE_PATTERNS:
        if pat in s:
            return True
    return False


def extract_hook(content_md: str) -> str:
    """首段非空 / 非标题 / 非引导(KOL boilerplate)的真钩子段 · 截 80 字。"""
    if not content_md:
        return ""
    for line in content_md.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("![") or line.startswith(">"):
            continue
        if line.startswith("- ") or line.startswith("* "):
            continue
        if _is_boilerplate(line):
            continue
        return line[:80]
    return ""


# 简单中英 keyword 提取(无 jieba 依赖 · 取 4-8 字段连续中文 + 大写英文)
_KW_CN = re.compile(r"[一-鿿]{2,8}")
_KW_EN = re.compile(r"[A-Z][A-Za-z0-9]{2,15}")
_STOPWORDS = {
    "我们", "你们", "他们", "什么", "怎么", "为什么", "因为", "所以", "但是",
    "如果", "可以", "已经", "应该", "或者", "这个", "那个", "这样", "那样",
    "现在", "今天", "昨天", "明天", "一个", "一些", "其实", "也许", "可能",
    "今日", "今晚", "上周", "今年", "这次", "那次", "其中", "之间", "之后",
    "之前", "几个", "很多", "不少", "很大", "更多", "比如", "比起", "看到",
    "听到", "想到", "做到", "得到", "拿到", "找到", "走到", "感到",
    # KOL 文章 boilerplate 噪声(粥左罗 / 半佛仙人 等头部惯用)
    "这是", "这是粥左罗的第", "这是半佛仙人的第", "关注", "订阅", "星标", "置顶",
    "作者", "编辑", "分享", "公众号", "百万互联网", "未经授权", "引言",
}


def extract_keywords(text: str, *, top_n: int = 3) -> list[str]:
    """从 title + hook 抽 top_n 中文词 + 英文术语。"""
    if not text:
        return []
    cn = [w for w in _KW_CN.findall(text) if w not in _STOPWORDS]
    en = _KW_EN.findall(text)
    counter = Counter(cn + en)
    return [w for w, _ in counter.most_common(top_n)]


# =================================================================
# 结构层 · 段 / h2 / 图 / 单句段
# =================================================================
def analyze_structure(content_md: str) -> dict:
    """段落 + 标题 + 图密度 + 单句段比例。"""
    if not content_md:
        return {
            "h2_count": 0, "paragraph_count": 0, "avg_para_chars": 0,
            "single_sent_para_ratio": 0.0, "image_count": 0, "total_chars": 0,
        }
    lines = content_md.splitlines()
    h2_count = sum(1 for ln in lines if ln.strip().startswith("## "))
    image_count = sum(1 for ln in lines if ln.strip().startswith("!["))
    # 段 = 连续非空行(非 ##) ~ 简化版
    paras: list[str] = []
    cur: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if s.startswith("![") or s.startswith(">") or s.startswith("```"):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))

    para_count = len(paras)
    total_chars = sum(len(p) for p in paras)
    avg_chars = round(total_chars / para_count) if para_count else 0
    # 单句段:不含逗号/句号(以"。""!""?""!"为标准)的段 / 全长 < 25 字
    single_sent = 0
    for p in paras:
        if len(p) <= 25 or p.count("。") + p.count("?") + p.count("!") + p.count("?") + p.count("!") <= 1:
            single_sent += 1
    ratio = round(single_sent / para_count, 2) if para_count else 0.0

    return {
        "h2_count": h2_count,
        "paragraph_count": para_count,
        "avg_para_chars": avg_chars,
        "single_sent_para_ratio": ratio,
        "image_count": image_count,
        "total_chars": total_chars,
    }


# =================================================================
# 风格层 · emoji / exclaim / 数字 / 加粗
# =================================================================
_EMOJI_RE = re.compile(
    r"["
    r"\U0001F300-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F"
    r"\U00002600-\U000027BF"
    r"\U0001F000-\U0001F2FF"
    r"]"
)
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?[%倍万亿千千K]?")
_BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")


def analyze_style(content_md: str) -> dict:
    """emoji / exclaim / 数字 / bold · 全部 normalize 到 per 100 chars。"""
    if not content_md:
        return {
            "emoji_count": 0, "exclaim_count": 0, "number_count": 0,
            "bold_count": 0, "ellipsis_count": 0,
            "emoji_per_100": 0.0, "exclaim_per_100": 0.0,
            "number_per_100": 0.0, "bold_per_100": 0.0,
            "top_emojis": [],
        }
    n = len(content_md) or 1
    emojis = _EMOJI_RE.findall(content_md)
    exclaims = content_md.count("!!") + content_md.count("!!")  # 中文 + 英文
    numbers = _NUMBER_RE.findall(content_md)
    bolds = _BOLD_RE.findall(content_md)
    ellipsis = content_md.count("...") + content_md.count("…")
    return {
        "emoji_count": len(emojis),
        "exclaim_count": exclaims,
        "number_count": len(numbers),
        "bold_count": len(bolds),
        "ellipsis_count": ellipsis,
        "emoji_per_100": round(len(emojis) * 100 / n, 2),
        "exclaim_per_100": round(exclaims * 100 / n, 2),
        "number_per_100": round(len(numbers) * 100 / n, 2),
        "bold_per_100": round(len(bolds) * 100 / n, 2),
        "top_emojis": [e for e, _ in Counter(emojis).most_common(5)],
    }


# =================================================================
# 主流程
# =================================================================
def load_corpus() -> dict:
    if not KOL_CORPUS.exists():
        return {"articles": []}
    return yaml.safe_load(KOL_CORPUS.read_text(encoding="utf-8")) or {"articles": []}


def filter_recent(articles: list[dict], *, days: int) -> list[dict]:
    """过滤最近 N 天的文章 · 用 fetched_at 字段。"""
    cutoff = datetime.now(_CST) - timedelta(days=days)
    out = []
    for a in articles:
        fetched_at = a.get("fetched_at") or ""
        try:
            dt = datetime.fromisoformat(fetched_at)
            if dt >= cutoff:
                out.append(a)
        except ValueError:
            continue
    return out


def analyze_one(article: dict) -> dict:
    """一篇文章 → metadata 3 层(传播 P4 才做)。"""
    md = article.get("content_md", "")
    title = article.get("title", "")
    hook = extract_hook(md)
    return {
        "kol": article.get("kol", ""),
        "title": title,
        "hook": hook,
        "url": article.get("url", ""),
        "pub_date": (article.get("pub_date") or "")[:10],
        "weight": article.get("weight", 50),
        "tags": list(article.get("tags") or []),
        "kw": extract_keywords(title + " " + hook),
        "structure": analyze_structure(md),
        "style": analyze_style(md),
    }


def aggregate(per_article: list[dict]) -> dict:
    """N 篇文章 → 全局聚合 metric。"""
    if not per_article:
        return {}
    # 排序 · 取 top hook(weight × recency 简化为 weight)
    sorted_articles = sorted(per_article,
                             key=lambda a: (-a["weight"], a.get("pub_date", "")))
    top_hooks = [
        {"kol": a["kol"], "title": a["title"], "hook": a["hook"],
         "weight": a["weight"], "url": a["url"]}
        for a in sorted_articles[:10] if a["hook"]
    ]

    # 结构基线 · 全样本中位数(剔异常)
    h2 = [a["structure"]["h2_count"] for a in per_article]
    para = [a["structure"]["paragraph_count"] for a in per_article]
    avg_p = [a["structure"]["avg_para_chars"] for a in per_article if a["structure"]["avg_para_chars"]]
    img = [a["structure"]["image_count"] for a in per_article]
    chars = [a["structure"]["total_chars"] for a in per_article if a["structure"]["total_chars"]]
    single = [a["structure"]["single_sent_para_ratio"] for a in per_article]
    structural_norms = {
        "median_h2_count": int(statistics.median(h2)) if h2 else 0,
        "median_paragraph_count": int(statistics.median(para)) if para else 0,
        "median_avg_para_chars": int(statistics.median(avg_p)) if avg_p else 0,
        "median_single_sent_ratio": round(statistics.median(single), 2) if single else 0.0,
        "median_image_count": int(statistics.median(img)) if img else 0,
        "median_total_chars": int(statistics.median(chars)) if chars else 0,
    }

    # 风格签名
    all_emojis = Counter()
    for a in per_article:
        all_emojis.update(a["style"]["top_emojis"])
    exclaim_per = [a["style"]["exclaim_per_100"] for a in per_article]
    number_per = [a["style"]["number_per_100"] for a in per_article]
    bold_per = [a["style"]["bold_per_100"] for a in per_article]
    style_signature = {
        "top_emojis": [e for e, _ in all_emojis.most_common(10)],
        "median_exclaim_per_100": round(statistics.median(exclaim_per), 2) if exclaim_per else 0.0,
        "median_number_per_100": round(statistics.median(number_per), 2) if number_per else 0.0,
        "median_bold_per_100": round(statistics.median(bold_per), 2) if bold_per else 0.0,
    }

    # KW 频次
    kw_counter = Counter()
    for a in per_article:
        kw_counter.update(a["kw"])
    top_kw = [{"kw": k, "count": c} for k, c in kw_counter.most_common(15)]

    return {
        "analyzed_at": _now_iso(),
        "total_articles": len(per_article),
        "top_hooks": top_hooks,
        "top_keywords": top_kw,
        "structural_norms": structural_norms,
        "style_signature": style_signature,
    }


def push_discord(text: str) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            timeout=30, check=False,
        )
    except Exception:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="抽 KOL corpus 的 metadata 4 层")
    p.add_argument("--days", type=int, default=7,
                   help="滑动窗口天数(默认 7)")
    p.add_argument("--no-push", action="store_true",
                   help="不 push Discord(测试用)")
    p.add_argument("--dry-run", action="store_true",
                   help="不写 patterns.yaml · 只打印")
    args = p.parse_args()

    corpus = load_corpus()
    articles = corpus.get("articles") or []
    recent = filter_recent(articles, days=args.days)

    if not recent:
        msg = f"⚠ 0 篇近 {args.days} 天文章 · 跳过分析(等 fetch_kol.py 先填充 corpus)"
        print(msg, file=sys.stderr)
        if not args.no_push:
            push_discord(f"📊 KOL analyze · {msg}")
        return 0

    print(f"→ 分析 {len(recent)} 篇文章(近 {args.days} 天)")
    per_article = [analyze_one(a) for a in recent]
    patterns = aggregate(per_article)
    patterns["window_days"] = args.days

    if not args.dry_run:
        KOL_PATTERNS.parent.mkdir(parents=True, exist_ok=True)
        KOL_PATTERNS.write_text(
            yaml.safe_dump(patterns, allow_unicode=True, sort_keys=False, indent=2),
            encoding="utf-8",
        )
        try:
            display = KOL_PATTERNS.relative_to(ROOT)
        except ValueError:
            display = KOL_PATTERNS
        print(f"✓ 写出 {display}")

    # Discord 报告
    sn = patterns.get("structural_norms", {})
    ss = patterns.get("style_signature", {})
    lines = [
        f"📊 **KOL 模式报告 · 近 {args.days} 天 · {len(recent)} 篇**",
        "",
        f"**结构基线**(中位):h2={sn.get('median_h2_count', 0)} · "
        f"段={sn.get('median_paragraph_count', 0)} · "
        f"段长={sn.get('median_avg_para_chars', 0)} 字 · "
        f"图={sn.get('median_image_count', 0)} 张 · "
        f"全文={sn.get('median_total_chars', 0)} 字",
        f"**风格基线**:emoji={','.join(ss.get('top_emojis', [])[:5])} · "
        f"!! 密度={ss.get('median_exclaim_per_100', 0)}/100 · "
        f"数字={ss.get('median_number_per_100', 0)}/100 · "
        f"bold={ss.get('median_bold_per_100', 0)}/100",
        "",
        "**Top 5 钩子**(weight 排序):",
    ]
    for h in patterns.get("top_hooks", [])[:5]:
        lines.append(f"  - [{h['kol']}] {h['title'][:35]}")
        lines.append(f"     钩子:{h['hook'][:60]}")
    if not args.no_push:
        push_discord("\n".join(lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
