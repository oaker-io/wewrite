#!/usr/bin/env python3
"""news_hub_reader.py · 从 ~/ai-news-hub/ 共享层拉素材。

公众号长文与 xwrite/xhswrite 共享同一份素材，但评分偏向：
  - 深度长文友好（release with body / multi-KOL reactions / multi-card eval）
  - 轻视纯模型权重发布（HF 单纯 model release 公众号读者不关心）
  - 重视有完整 prompt+response 配对的 eval bundle（直接出测评长文）

Fail-safe: hub 不在 / subprocess 失败 / JSON 损坏全部 return []。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

NEWS_HUB_DIR = Path.home() / "ai-news-hub"
NEWS_HUB_PY = NEWS_HUB_DIR / "venv" / "bin" / "python"
NEWS_HUB_READER = NEWS_HUB_DIR / "reader.py"
RELEASE_REACTIONS_DIR = NEWS_HUB_DIR / "release_reactions"
REVIEWS_DIR = NEWS_HUB_DIR / "reviews"


def read_news(limit: int = 15, since_hours: int = 72) -> list[dict]:
    if not NEWS_HUB_READER.exists() or not NEWS_HUB_PY.exists():
        return []
    try:
        proc = subprocess.run(
            [str(NEWS_HUB_PY), str(NEWS_HUB_READER),
             "--platform", "wewrite",
             "--limit", str(limit),
             "--since-hours", str(since_hours),
             "--json"],
            capture_output=True, text=True, timeout=20, cwd=str(NEWS_HUB_DIR),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[news_hub] subprocess failed: {exc}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        return []
    try:
        items = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return [_score_for_wx(it) for it in items if _score_for_wx(it).get("wx_score", 0) > 0]


def _score_for_wx(d: dict) -> dict:
    """公众号评分：偏向"能写出 1500 字的素材"。"""
    score = 0
    title = (d.get("title") or "").lower()
    summary = (d.get("summary") or "").lower()
    text = title + " " + summary

    # +号：深度题材（评测/对比/方法论/案例）
    for kw in ("evaluation", "benchmark", "compare", "deep dive",
               "methodology", "case study", "实测", "横向对比",
               "深度", "方法论", "案例"):
        if kw in text:
            score += 8

    # +号：模型/重大发布 — 公众号读者爱长解读
    if d.get("source") in ("anthropic", "openai", "google_ai", "deepmind"):
        score += 12
    elif d.get("source") == "deepseek":
        score += 10  # 中文圈关心
    # release body 越长越好（公众号能写得越深）
    if len(summary) >= 300:
        score += 6
    if len(summary) >= 800:
        score += 8

    # -号：纯权重发布（公众号长文写不出 1500 字）
    if d.get("source") == "huggingface":
        ex = d.get("extra", {}) or {}
        # HF 上有 pipeline_tag 但没 description 的纯 weights → 减分
        if not d.get("summary") and ex.get("repo_type") == "model":
            score -= 12

    # -号：纯娱乐 / 营销
    for kw in ("marketing", "promo", "swag"):
        if kw in text:
            score -= 5

    d["wx_score"] = score
    return d


def read_release_reactions(slug: str | None = None) -> list[dict]:
    if not RELEASE_REACTIONS_DIR.exists():
        return []
    bundles = []
    for path in sorted(RELEASE_REACTIONS_DIR.glob("*.json"), reverse=True):
        if slug and slug not in path.stem:
            continue
        try:
            bundles.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return bundles


def read_reviews(model_slug: str | None = None) -> list[dict]:
    if not REVIEWS_DIR.exists():
        return []
    out = []
    for sub in sorted(REVIEWS_DIR.iterdir(), reverse=True):
        if not sub.is_dir():
            continue
        if model_slug and model_slug not in sub.name:
            continue
        summary = sub / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text())
            data["_dir"] = str(sub)
            out.append(data)
        except json.JSONDecodeError:
            continue
    return out


if __name__ == "__main__":
    print("=== read_news (wewrite scoring) ===")
    items = read_news(limit=8)
    for it in items[:5]:
        print(f"  [{it.get('wx_score', 0):+3d}] [{it.get('source')}] {it.get('title')[:80]}")
    print(f"\n=== read_release_reactions ===")
    rxns = read_release_reactions()
    for r in rxns[:3]:
        rel = r.get("release", {})
        print(f"  · {rel.get('title','?')[:60]} ({r.get('n_total_matches', 0)} KOL)")
    print(f"\n=== read_reviews ===")
    revs = read_reviews()
    for r in revs[:3]:
        print(f"  · {r.get('model_label')} ({r.get('n_successful')}/{r.get('n_prompts')} cards)")
