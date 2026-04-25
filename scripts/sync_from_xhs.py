#!/usr/bin/env python3
"""sync_from_xhs.py · 从 xhswrite 事件总线拉「小红书发布完成」事件 · 入 wewrite idea_bank。

为什么:
    用户在 xhswrite(/Users/mahaochen/xhswrite/)发了 1 篇小红书图文笔记 ·
    希望同主题在 wewrite 这边也起一篇微信公众号短文 · 形成跨平台覆盖。

最小桥(P1):
    - 不复用 xhs 文字(平台风格不一样 · 标题党 vs 工程派 · 改写比抄省事)
    - 不复用 xhs 图(3:4 竖图 vs 公众号 1:1 thumb · 比例不对)
    - **只复用主题(title)**:作为 idea 入 wewrite idea_bank · auto_pick 下次能选 ·
      然后 wewrite 自己的 write.py 用 wewrite 风格重写 · 自己的 images.py 生 1:1 thumb

数据源:
    /Users/mahaochen/xhswrite/bus/events.jsonl 每行一条 JSON event
    形如:
      {"ts": "2026-04-25T05:09:00+00:00", "agent": "publish", "kind": "done",
       "title": "GPT-5.5 上线...", "images": 6}

去重:
    output/xhs_sync_state.yaml 记 last_processed_ts · 只处理 ts > last 的 event

跑法:
    venv/bin/python3 scripts/sync_from_xhs.py            # 默认 · 拉 + 入库 + push
    venv/bin/python3 scripts/sync_from_xhs.py --dry-run  # 不写 idea_bank · 只看
    venv/bin/python3 scripts/sync_from_xhs.py --no-push  # 不 push Discord
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import _idea_bank  # noqa: E402

XHS_EVENTS = Path("/Users/mahaochen/xhswrite/bus/events.jsonl")
SYNC_STATE = ROOT / "output" / "xhs_sync_state.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def load_sync_state() -> dict:
    if not SYNC_STATE.exists():
        return {"last_processed_ts": None, "synced_count": 0}
    return yaml.safe_load(SYNC_STATE.read_text(encoding="utf-8")) or {}


def save_sync_state(state: dict) -> None:
    SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def read_xhs_events() -> list[dict]:
    """读 xhswrite events.jsonl · 返回所有 event(每行一条 JSON)。"""
    if not XHS_EVENTS.exists():
        return []
    out = []
    for line in XHS_EVENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def find_new_publish_events(events: list[dict], last_ts: str | None) -> list[dict]:
    """筛 agent=publish kind=done 且 ts > last_ts 的 event。"""
    out = []
    for e in events:
        if e.get("agent") != "publish" or e.get("kind") != "done":
            continue
        if not e.get("title"):  # 没标题的跳过(发布失败兜底)
            continue
        ts = e.get("ts", "")
        if last_ts and ts <= last_ts:
            continue
        out.append(e)
    return out


def add_to_idea_bank(event: dict) -> int | None:
    """xhs publish event → idea_bank · 标 source=xhs · category=flexible。"""
    title = (event.get("title") or "").strip()
    if not title:
        return None
    notes = (
        f"from xhswrite · {event.get('ts', '?')[:19]}\n"
        f"images: {event.get('images', 0)} 张\n"
        f"url: {event.get('url') or '(xhs internal · MCP 没回 url)'}"
    )
    try:
        rec = _idea_bank.add(
            title=title,
            category="flexible",
            source="xhs",
            priority=80,
            tags=["xhs", "跨平台"],
            notes=notes,
        )
        return rec["id"]
    except Exception as e:
        print(f"  ✗ idea_bank add fail: {e}", file=sys.stderr)
        return None


def push_discord(text: str) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            timeout=30, check=False,
        )
    except Exception:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="拉 xhswrite 发布事件 · 入 wewrite idea_bank")
    p.add_argument("--dry-run", action="store_true", help="不写 idea_bank · 只打印")
    p.add_argument("--no-push", action="store_true", help="不 push Discord")
    p.add_argument("--reset", action="store_true",
                   help="重置 last_processed_ts · 重跑全部历史(慎)")
    args = p.parse_args()

    if not XHS_EVENTS.exists():
        print(f"❌ {XHS_EVENTS} 不存在 · xhswrite 还没产生事件?", file=sys.stderr)
        return 0  # 不报错(xhswrite 可能还没装)

    state = load_sync_state()
    if args.reset:
        state["last_processed_ts"] = None
        print("⚠ 重置 last_processed_ts · 全部历史重跑")

    last_ts = state.get("last_processed_ts")
    events = read_xhs_events()
    new_events = find_new_publish_events(events, last_ts)

    print(f"→ xhswrite events: 总 {len(events)} 条 · 新 publish done {len(new_events)} 条")

    if not new_events:
        print(f"  · 无新发布 · 上次处理到 ts={last_ts or '从未'}")
        return 0

    added_ids: list[int] = []
    for e in new_events:
        ts = e.get("ts", "?")
        title = e.get("title", "")[:50]
        print(f"  + [{ts[:19]}] {title}")
        if not args.dry_run:
            idea_id = add_to_idea_bank(e)
            if idea_id is not None:
                added_ids.append(idea_id)

    # 更新 state · last_ts = 最新 event 的 ts
    if new_events and not args.dry_run:
        state["last_processed_ts"] = new_events[-1]["ts"]
        state["synced_count"] = state.get("synced_count", 0) + len(added_ids)
        state["last_synced_at"] = _now_iso()
        save_sync_state(state)

    print(f"\n✓ 新入 wewrite idea_bank · {len(added_ids)} 条 · idea_id={added_ids}")

    # Discord 报告
    if not args.no_push and added_ids:
        lines = [
            f"🔗 **xhs → wewrite 同步** · {len(added_ids)} 条新 idea",
            "",
        ]
        for e, idea_id in zip(new_events, added_ids):
            lines.append(f"  [#{idea_id}] {(e.get('title') or '')[:50]}")
        lines.append("")
        lines.append("→ 明早 07:00 auto_pick 选题时 · 这些 xhs 主题进候选(weight=80)")
        lines.append("→ wewrite 用自己风格重写短文 · 不复用 xhs 文字 / 图")
        push_discord("\n".join(lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
