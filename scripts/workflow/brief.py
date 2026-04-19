#!/usr/bin/env python3
"""Workflow 1 · 选题 brief
跑 Step 1-2 · 生成 Top 3 选题 · push 到手机等用户回复序号。

用法: python3 scripts/workflow/brief.py
"""
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
FETCH = ROOT / "scripts" / "fetch_hotspots.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def fetch_hotspots(limit=15):
    r = subprocess.run(
        [str(PY), str(FETCH), "--limit", str(limit)],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        raise RuntimeError(f"fetch_hotspots: {r.stderr[:300]}")
    return json.loads(r.stdout).get("items", [])


def load_style_topics():
    sf = ROOT / "style.yaml"
    if not sf.exists():
        return []
    import yaml
    d = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
    return d.get("topics", [])


def score_topic(item, focus_topics):
    hot = item.get("hot_normalized", 0) or 0
    title = item.get("title", "")
    match = 0
    for t in focus_topics:
        for kw in (t or "").split("/"):
            kw = kw.strip()
            if kw and kw in title:
                match = 100
                break
        if match:
            break
    return round(hot * 0.5 + match * 0.3 + 80 * 0.2, 1)


def pick_top3(items, focus_topics):
    scored = []
    for i, item in enumerate(items):
        scored.append({
            "idx": i,
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "hot": item.get("hot_normalized", 0),
            "score": score_topic(item, focus_topics),
            "url": item.get("url", ""),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


def format_message(topics):
    date = datetime.now().strftime("%m-%d")
    lines = [
        f"📰 **{date} · 今日选题 Top 3**",
        "_AI 非共识视角 · 综合评分排序_", "",
    ]
    for i, t in enumerate(topics, 1):
        lines.append(f"**{i}.** {t['title']}")
        lines.append(
            f"    📊 {t['score']} · 🔥 {t['source']} · 热度 {t['hot']:.0f}"
        )
        lines.append("")
    lines.append("---")
    lines.append("👉 回复 `1` / `2` / `3` 选一个 · 或 `pass` 今天跳过")
    return "\n".join(lines)


def push(text):
    r = subprocess.run(
        [str(PY), str(PUSH), "--text", text],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"push: {r.stderr[:300]}")


def main():
    print("→ fetching hotspots...")
    items = fetch_hotspots(15)
    print(f"  got {len(items)} items")
    top3 = pick_top3(items, load_style_topics())
    _state.advance(
        _state.STATE_BRIEFED,
        article_date=datetime.now().strftime("%Y-%m-%d"),
        topics=top3,
        selected_idx=None,
        article_md=None,
        images_dir=None,
        draft_media_id=None,
    )
    msg = format_message(top3)
    push(msg)
    print("✓ briefed · top 3 pushed · awaiting user pick")
    return 0


if __name__ == "__main__":
    sys.exit(main())
