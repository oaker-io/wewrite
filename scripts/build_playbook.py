#!/usr/bin/env python3
"""
Build a writing playbook from historical articles.

Reads all .md files in corpus/, analyzes writing patterns
in batches via LLM, and outputs a structured playbook.md.

Usage:
    python3 build_playbook.py
    python3 build_playbook.py --batch-size 10

Requires: ANTHROPIC_API_KEY or ARK API key in environment/config.
This script outputs analysis prompts to stdout for the Agent (LLM) to process.
The Agent reads the output and generates playbook.md.
"""

import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


def load_corpus() -> list[dict]:
    """Load all markdown files from corpus directory."""
    corpus_dir = SKILL_DIR / "corpus"
    if not corpus_dir.exists():
        print(f"Error: corpus directory not found: {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    articles = []
    for md_file in sorted(corpus_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        if not text.strip():
            continue

        # Extract title (first H1)
        title = ""
        for line in text.split("\n"):
            if line.strip().startswith("# ") and not line.strip().startswith("## "):
                title = line.strip()[2:].strip()
                break

        # Basic stats
        lines = [l for l in text.split("\n") if l.strip()]
        paragraphs = text.split("\n\n")
        h2_count = sum(1 for l in text.split("\n") if l.strip().startswith("## "))
        char_count = len(text.replace("\n", "").replace(" ", ""))

        articles.append({
            "filename": md_file.name,
            "title": title,
            "char_count": char_count,
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "h2_count": h2_count,
            "text": text,
        })

    return articles


def compute_corpus_stats(articles: list[dict]) -> dict:
    """Compute aggregate statistics from the corpus."""
    if not articles:
        return {}

    titles = [a["title"] for a in articles if a["title"]]
    title_lengths = [len(t) for t in titles]
    char_counts = [a["char_count"] for a in articles]
    para_counts = [a["paragraph_count"] for a in articles]
    h2_counts = [a["h2_count"] for a in articles]

    return {
        "total_articles": len(articles),
        "avg_char_count": round(sum(char_counts) / len(char_counts)),
        "avg_title_length": round(sum(title_lengths) / len(title_lengths), 1) if title_lengths else 0,
        "title_length_range": f"{min(title_lengths)}-{max(title_lengths)}" if title_lengths else "N/A",
        "avg_paragraphs": round(sum(para_counts) / len(para_counts), 1),
        "avg_h2_count": round(sum(h2_counts) / len(h2_counts), 1),
    }


def build_analysis_batches(articles: list[dict], batch_size: int) -> list[list[dict]]:
    """Split articles into batches for LLM analysis."""
    batches = []
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batches.append(batch)
    return batches


def output_analysis_prompt(articles: list[dict], stats: dict, batch_idx: int, total_batches: int):
    """Output a structured analysis prompt for the Agent to process."""
    print(f"\n{'='*60}")
    print(f"BATCH {batch_idx + 1}/{total_batches} — {len(articles)} articles")
    print(f"{'='*60}\n")

    for i, article in enumerate(articles):
        print(f"--- Article {i+1}: {article['title']} ({article['char_count']}字) ---")
        # Truncate very long articles to first 2000 chars for analysis
        text = article["text"]
        if len(text) > 3000:
            text = text[:3000] + "\n\n[...truncated...]"
        print(text)
        print()


def main():
    parser = argparse.ArgumentParser(description="Build writing playbook from corpus")
    parser.add_argument("--batch-size", type=int, default=10, help="Articles per batch")
    parser.add_argument("--stats-only", action="store_true", help="Only show corpus stats")
    args = parser.parse_args()

    # Load corpus
    articles = load_corpus()
    if not articles:
        print("Error: no articles found in corpus/", file=sys.stderr)
        sys.exit(1)

    # Compute stats
    stats = compute_corpus_stats(articles)

    print("=" * 60)
    print("CORPUS ANALYSIS")
    print("=" * 60)
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    if args.stats_only:
        return

    # Build batches
    batches = build_analysis_batches(articles, args.batch_size)

    print(f"\nTotal: {stats['total_articles']} articles in {len(batches)} batch(es)")
    print(f"Average: {stats['avg_char_count']} chars, {stats['avg_title_length']} char titles, {stats['avg_h2_count']} H2s")

    # Output analysis instructions
    print(f"""
{'='*60}
ANALYSIS INSTRUCTIONS FOR AGENT
{'='*60}

Read all articles below, then generate playbook.md with these sections:

## 标题模式
- 平均字数和范围
- 常用策略分布（数字/反直觉/痛点/疑问/陈述，给百分比）
- 标点习惯（逗号断句？问号？感叹号？）
- 示例：列出 3 个最典型的标题

## 开头模式
- 最常用的开头方式（场景/数据/反问/新闻引述/个人经历）
- 第一段平均长度
- 从不出现的开头方式
- 示例：列出 3 个典型开头的第一段

## 段落节奏
- 平均段落长度（字数）
- 短段（<30字）占比
- 最长段落上限
- 长短交替规律

## 用词指纹
- 高频标志词/口头禅（出现 3 次以上的特征性表达）
- 禁用词（从未使用的常见 AI 用语）
- 英文/专业术语使用习惯
- 语气词偏好

## H2 命名习惯
- 用问句？短语？数字编号？
- 平均长度
- 示例

## 结尾模式
- 收尾方式（个人观点/开放提问/行动建议/金句）
- CTA 风格
- 示例

## 情绪基调
- 理性 vs 感性的比例
- 幽默频率
- 批判性强度

## 配图风格（如果历史文章有配图描述）
- 色调偏好
- 风格关键词

请用量化数据（百分比、平均值、范围）支撑每个结论，不要只做定性描述。
""")

    # Output article batches
    for i, batch in enumerate(batches):
        output_analysis_prompt(batch, stats, i, len(batches))


if __name__ == "__main__":
    main()
