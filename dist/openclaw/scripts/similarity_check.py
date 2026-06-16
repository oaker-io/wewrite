#!/usr/bin/env python3
"""文本相似度闸门：字符 3-gram Jaccard，用于跨平台改写的去重检测。

用法：
    python3 scripts/similarity_check.py a.md b.md [c.md ...]   # 两两最大相似度
    python3 scripts/similarity_check.py a.md b.md --json       # agent 解析用
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_NORM = re.compile(r"[^\w一-鿿]+")


def _normalize(text: str) -> str:
    """去除 markdown 标记、空白、标点，只留字母数字与中日韩字，聚焦内容本身。"""
    return _NORM.sub("", text)


def char_ngrams(text: str, n: int = 3) -> set[str]:
    t = _normalize(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def similarity(a: str, b: str, n: int = 3) -> float:
    """字符 n-gram 的 Jaccard 相似度，0-1。"""
    A, B = char_ngrams(a, n), char_ngrams(b, n)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def max_pairwise(texts: list[str], n: int = 3) -> float:
    m = 0.0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            m = max(m, similarity(texts[i], texts[j], n))
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="字符 n-gram Jaccard 相似度闸门")
    ap.add_argument("files", nargs="+", help="待比较的文本文件（≥2）")
    ap.add_argument("--json", action="store_true", help="JSON 输出（agent 用）")
    ap.add_argument("-n", type=int, default=3, help="n-gram 长度（默认 3）")
    args = ap.parse_args(argv)
    texts = [Path(f).read_text(encoding="utf-8") for f in args.files]
    m = max_pairwise(texts, args.n) if len(texts) >= 2 else 0.0
    if args.json:
        print(json.dumps({"max_similarity": round(m, 4),
                          "param": "similarity_threshold"}, ensure_ascii=False))
    else:
        print(f"max_similarity = {m:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
