#!/usr/bin/env python3
"""
Fixed humanness scoring pipeline for WeWrite optimization loop.

Two-layer scoring inspired by autoresearch + the "objective checklist + subjective feel" pattern:

Layer 1: Objective checklist (yes/no, deterministic, won't drift)
Layer 2: Subjective reader-feel (LLM judge, 1-10)

Composite = Layer1 pass_rate * 0.6 + Layer2 normalized * 0.4

DO NOT MODIFY this file during optimization. It is the fixed evaluation function.

Usage:
    python3 humanness_score.py article.md
    python3 humanness_score.py article.md --verbose
    python3 humanness_score.py article.md --json
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ============================================================
# Layer 1: Objective Checklist (deterministic yes/no)
# ============================================================

BANNED_WORDS = [
    "首先", "其次", "再者", "最后", "总之", "综上所述", "总而言之",
    "此外", "另外", "与此同时", "不仅如此", "更重要的是", "在此基础上",
    "作为一个", "让我们", "值得注意的是", "需要指出的是", "不可否认",
    "毋庸置疑", "众所周知", "事实上", "显而易见", "可以说", "从某种意义上说",
    "非常重要", "至关重要", "不言而喻", "具有重要意义", "发挥着重要作用",
    "意义深远", "影响深远", "引发了广泛关注", "引起了热烈讨论",
    "总的来说", "综合来看", "由此可见", "不难发现", "通过以上分析",
    "正如我们所看到的",
]

# Real-source indicators: named people, organizations, specific publications
REAL_SOURCE_PATTERNS = [
    r'[A-Z][a-z]+\s+[A-Z][a-z]+',  # Named person (English)
    r'[\u4e00-\u9fff]{2,4}(?:表示|指出|认为|写道|提到|说过)',  # Chinese name + said
    r'(?:据|根据|来自)\s*[\u4e00-\u9fff]+(?:报告|数据|研究|调查)',  # "according to X report"
    r'20[12]\d\s*年',  # Specific year reference
    r'\d+(?:\.\d+)?%',  # Specific percentage
    r'(?:亿|万)\s*(?:美元|元|人民币)',  # Specific monetary amount
]


def check_no_banned_words(text: str) -> tuple[bool, str]:
    """Check: zero banned words."""
    found = [w for w in BANNED_WORDS if w in text]
    if found:
        return False, f"Found {len(found)} banned words: {found[:5]}"
    return True, "0 banned words"


def check_real_sources(text: str) -> tuple[bool, str]:
    """Check: article references real external sources (≥3 instances)."""
    count = 0
    for pattern in REAL_SOURCE_PATTERNS:
        count += len(re.findall(pattern, text))
    if count >= 3:
        return True, f"{count} real-source indicators found"
    return False, f"Only {count} real-source indicators (need ≥3)"


def check_broken_sentences(text: str) -> tuple[bool, str]:
    """Check: ≥3 broken/incomplete sentences (dashes, ellipsis, self-corrections)."""
    patterns = [
        r'——(?!.*[，。！？])',  # em-dash interruption without ending punct
        r'\.{3,}|…',  # ellipsis
        r'不对[，,]',  # self-correction "不对，"
        r'算了',  # abandonment "算了"
        r'^.{1,6}[。！？]$',  # ultra-short sentence (≤6 chars + punct) as standalone line
    ]
    count = 0
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for p in patterns:
            count += len(re.findall(p, line))
        # Check for ultra-short standalone paragraphs (1-10 chars)
        if 1 <= len(line) <= 10 and not line.startswith('#'):
            count += 1
    if count >= 3:
        return True, f"{count} broken/incomplete structures"
    return False, f"Only {count} broken structures (need ≥3)"


def check_sentence_length_variance(text: str) -> tuple[bool, str]:
    """Check: sentence length standard deviation > threshold.

    AI text has suspiciously uniform sentence lengths.
    Human text varies wildly (3-char to 80-char sentences in the same paragraph).
    """
    # Split by Chinese sentence-ending punctuation
    sentences = re.split(r'[。！？\n]', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]

    if len(sentences) < 5:
        return False, "Too few sentences to measure"

    lengths = [len(s) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    stddev = variance ** 0.5

    # Threshold: human text typically has stddev > 15 chars
    # AI text tends to be 8-12
    if stddev > 15:
        return True, f"Sentence length stddev = {stddev:.1f} (good variance)"
    return False, f"Sentence length stddev = {stddev:.1f} (too uniform, need >15)"


def check_paragraph_length_variance(text: str) -> tuple[bool, str]:
    """Check: no consecutive paragraphs of similar length."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and not p.strip().startswith('#')]
    if len(paragraphs) < 3:
        return True, "Too few paragraphs to check"

    consecutive_similar = 0
    for i in range(len(paragraphs) - 1):
        len_a = len(paragraphs[i])
        len_b = len(paragraphs[i + 1])
        if abs(len_a - len_b) <= 20:
            consecutive_similar += 1

    if consecutive_similar <= 1:
        return True, f"{consecutive_similar} consecutive similar-length pairs (OK)"
    return False, f"{consecutive_similar} consecutive similar-length pairs (too uniform)"


def check_word_temperature_mix(text: str) -> tuple[bool, str]:
    """Check: mix of formal/colloquial/slang/wild vocabulary."""
    cold = ["边际", "认知负荷", "信息不对称", "路径依赖", "商业模式", "生态系统", "增量"]
    warm = ["说白了", "其实吧", "讲真", "说实话", "坦白讲", "懂的都懂", "怎么说呢"]
    hot = ["DNA动了", "格局打开", "遥遥领先", "卷", "内卷", "炸了", "杀疯了", "吃灰"]
    wild = ["整挺好", "不靠谱", "瞎折腾", "搁这儿", "糊弄", "扯", "嗯"]

    found_temps = 0
    if any(w in text for w in cold): found_temps += 1
    if any(w in text for w in warm): found_temps += 1
    if any(w in text for w in hot): found_temps += 1
    if any(w in text for w in wild): found_temps += 1

    if found_temps >= 3:
        return True, f"{found_temps}/4 temperature types found"
    return False, f"Only {found_temps}/4 temperature types (need ≥3)"


def run_layer1(text: str) -> dict:
    """Run all Layer 1 checks. Returns dict with results."""
    checks = [
        ("no_banned_words", check_no_banned_words),
        ("real_sources", check_real_sources),
        ("broken_sentences", check_broken_sentences),
        ("sentence_length_variance", check_sentence_length_variance),
        ("paragraph_length_variance", check_paragraph_length_variance),
        ("word_temperature_mix", check_word_temperature_mix),
    ]

    results = {}
    passed = 0
    total = len(checks)

    for name, fn in checks:
        ok, detail = fn(text)
        results[name] = {"passed": ok, "detail": detail}
        if ok:
            passed += 1

    results["_summary"] = {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4),
    }
    return results


# ============================================================
# Layer 2: Subjective Reader-Feel (LLM judge)
# ============================================================

JUDGE_PROMPT = """你是一个经验丰富的公众号读者。你对 AI 生成的内容非常敏感——你能凭直觉分辨出人写的和 AI 写的。

现在请你阅读下面这篇文章，然后回答一个问题：

**这篇文章读起来像人写的吗？**

评分标准（1-10）：
- 1-3：明显是 AI 写的。语言过于规整，没有个人色彩，像教科书。
- 4-5：有一些 AI 痕迹。整体流畅但缺乏个人经历、情感起伏或出人意料的表达。
- 6-7：大部分像人写的，偶尔有几句感觉"太完美了"。
- 8-9：很像人写的。有个人风格、情感波动、不完美感，像一个真人编辑的作品。
- 10：完全像人写的。如果不告诉我，我不会怀疑这是 AI 参与的。

请只输出一个 JSON：{"score": 数字, "reason": "一句话理由"}

---

文章内容：

{article}
"""


def run_layer2_stub(text: str) -> dict:
    """Layer 2 stub — returns placeholder when no LLM API available.

    In production, this calls Claude/GPT to judge the article.
    For the optimization loop, replace this with actual API call.
    """
    return {
        "score": 5.0,
        "reason": "(stub) LLM judge not configured — using default score",
        "is_stub": True,
    }


# ============================================================
# Composite Score
# ============================================================

def compute_composite(layer1: dict, layer2: dict) -> float:
    """Composite score: lower is better (like val_bpb in autoresearch).

    Inverted so that 0 = perfect human, 100 = obvious AI.
    """
    l1_pass_rate = layer1["_summary"]["pass_rate"]
    l2_score = layer2["score"] / 10.0  # normalize to 0-1

    # Composite: higher pass_rate and higher reader score = more human
    humanness = l1_pass_rate * 0.6 + l2_score * 0.4

    # Invert: 0 = perfect human, 100 = obvious AI
    return round((1 - humanness) * 100, 2)


# ============================================================
# Main
# ============================================================

def score_article(text: str, verbose: bool = False) -> dict:
    """Score an article. Returns full results dict."""
    # Strip markdown headers for scoring
    clean = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE).strip()

    layer1 = run_layer1(clean)
    layer2 = run_layer2_stub(clean)
    composite = compute_composite(layer1, layer2)

    result = {
        "composite_score": composite,
        "layer1": layer1,
        "layer2": layer2,
        "char_count": len(clean),
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"HUMANNESS SCORE: {composite:.1f}/100 (lower = more human)")
        print(f"{'='*60}")
        print(f"\nLayer 1 — Objective Checklist ({layer1['_summary']['passed']}/{layer1['_summary']['total']})")
        for name, data in layer1.items():
            if name.startswith('_'):
                continue
            status = "✓" if data["passed"] else "✗"
            print(f"  {status} {name}: {data['detail']}")
        print(f"\nLayer 2 — Reader Feel: {layer2['score']}/10")
        print(f"  {layer2['reason']}")
        print(f"\nComposite: {composite:.1f} (0=完美人类, 100=明显AI)")

    return result


def main():
    parser = argparse.ArgumentParser(description="Score article humanness")
    parser.add_argument("input", help="Markdown article file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    result = score_article(text, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not args.verbose:
        print(f"{result['composite_score']:.1f}")


if __name__ == "__main__":
    main()
