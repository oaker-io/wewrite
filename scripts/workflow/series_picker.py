"""series_picker.py · 干货系列调度 · 给 auto_pick 用。

逻辑:
  - 读 config/series.yaml · 找今天到期的 series
  - 到期 = next_due ≤ today AND topic_queue 非空 AND published < total
  - 取 topic_queue[0] 当今日主推
  - 推:published+1 · 删 topic_queue[0] · next_due += cadence_days(原子写)

跟 auto_pick 集成:
  - auto_pick 主推选题前先 pick_due_today()
  - 返回 dict → 顶替主推 #1
  - 返回 None → 走原 idea_bank 逻辑

幂等:
  - 同一天多次跑 pick_due_today() · 第 1 次会推进 · 第 2+ 次因 next_due 已 > today · 不再触发
  - 用户 reset session · 重跑 auto_pick · 不会再推进 series(因 next_due 已变)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SERIES_FILE = ROOT / "config" / "series.yaml"


def load_series() -> dict:
    """读 config/series.yaml · 不存在返默认空。"""
    if not SERIES_FILE.exists():
        return {"version": 1, "series": []}
    try:
        return yaml.safe_load(SERIES_FILE.read_text(encoding="utf-8")) or {"series": []}
    except yaml.YAMLError:
        return {"series": []}


def save_series(data: dict) -> None:
    SERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SERIES_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def pick_due_today(today: str | None = None, *, dry_run: bool = False) -> dict | None:
    """找今天到期的系列 · 返回今日主推 dict · 无返 None。

    返回结构:
      {
        "series_id": "claude-30",
        "series_name": "Claude 实战 30 讲",
        "title": "Claude Code 30 分钟从 0 到 1 · 我的真实流程",
        "theme": "AI 干货",
        "episode": 1,         # 第几篇(1-indexed)
        "total": 30,
      }
    """
    today = today or date.today().isoformat()
    data = load_series()
    series_list = data.get("series") or []

    # 优先级:next_due 越早 + cadence 越短(高频) 优先
    due = []
    for s in series_list:
        if not isinstance(s, dict):
            continue
        if (s.get("published", 0) >= s.get("total", 0)):
            continue
        if not s.get("topic_queue"):
            continue
        nd = s.get("next_due", "9999-12-31")
        if isinstance(nd, date):
            nd = nd.isoformat()
        if nd <= today:
            due.append(s)

    if not due:
        return None

    # 按 next_due 升序 · cadence 升序
    due.sort(key=lambda s: (str(s.get("next_due", "")), int(s.get("cadence_days", 99))))
    target = due[0]

    title = target["topic_queue"][0]
    episode = target.get("published", 0) + 1
    out = {
        "series_id": target.get("id", ""),
        "series_name": target.get("name", ""),
        "title": title,
        "theme": target.get("theme", "AI 干货"),
        "episode": episode,
        "total": target.get("total", 0),
    }

    if dry_run:
        return out

    # 真实推进 · 原子写
    target["topic_queue"] = target["topic_queue"][1:]
    target["published"] = episode
    cadence = int(target.get("cadence_days", 2))
    target["next_due"] = (date.fromisoformat(today) + timedelta(days=cadence)).isoformat()
    save_series(data)
    return out


def list_series_status() -> list[dict]:
    """列出所有 series 当前进度 · daily-report 用。"""
    data = load_series()
    out = []
    for s in data.get("series") or []:
        if not isinstance(s, dict):
            continue
        nd = s.get("next_due", "?")
        if isinstance(nd, date):
            nd = nd.isoformat()
        out.append({
            "id": s.get("id", ""),
            "name": s.get("name", ""),
            "theme": s.get("theme", ""),
            "published": s.get("published", 0),
            "total": s.get("total", 0),
            "next_due": nd,
            "queue_left": len(s.get("topic_queue") or []),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只查今天哪个到期 · 不推进")
    ap.add_argument("--status", action="store_true", help="列所有 series 进度")
    ap.add_argument("--today", default=None, help="覆盖 today(测试用)· YYYY-MM-DD")
    args = ap.parse_args()

    if args.status:
        for s in list_series_status():
            mark = "🟢" if s["next_due"] <= date.today().isoformat() else "⚪"
            print(f"  {mark} {s['name']:25s} {s['published']}/{s['total']} · next={s['next_due']} · queue={s['queue_left']} · theme={s['theme']}")
        return 0

    pick = pick_due_today(today=args.today, dry_run=args.check)
    if not pick:
        print("⚪ 今日无系列到期")
        return 0

    print(f"🟢 今日到期系列:")
    print(f"  · series:{pick['series_name']}")
    print(f"  · 第 {pick['episode']}/{pick['total']} 篇")
    print(f"  · 标题:{pick['title']}")
    print(f"  · 主题:{pick['theme']}")
    if args.check:
        print("  · (--check 模式 · 未推进 · 真跑会消费 topic_queue + 推 next_due)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
