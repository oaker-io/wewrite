"""Session state helper · 跨 claude -p session 的 workflow 状态机。

状态持久化到 output/session.yaml · 被 4 个 workflow 脚本(brief/write/images/publish)
+ bot.py 共享读写。

State transitions:
    idle → briefed → writing → wrote → generating → imaged → publishing → done
    (回退:任一 state → idle 代表用户说 "pass" 或 "重来")

Field schema:
    state: str            当前状态
    article_date: str     YYYY-MM-DD
    topics: list          brief 产出的 Top 3 选题
    selected_idx: int     用户选的序号(0/1/2)
    selected_topic: dict  等于 topics[selected_idx]
    article_md: str       写出的文章路径(相对 repo)
    images_dir: str       output/images/
    draft_media_id: str   微信草稿 id
    updated_at: str       ISO 时间戳
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE_FILE = _ROOT / "output" / "session.yaml"

STATE_IDLE = "idle"
STATE_BRIEFED = "briefed"
STATE_WROTE = "wrote"
STATE_IMAGED = "imaged"
STATE_DONE = "done"


def _default():
    return {
        "state": STATE_IDLE,
        "article_date": None,
        "topics": [],
        "selected_idx": None,
        "selected_topic": None,
        "article_md": None,
        "images_dir": None,
        "draft_media_id": None,
        "updated_at": None,
    }


def load() -> dict:
    """Read session.yaml · 不存在返回 default。"""
    if not _STATE_FILE.exists():
        return _default()
    try:
        data = yaml.safe_load(_STATE_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return _default()
    d = _default()
    d.update(data)
    return d


def save(state_dict: dict) -> None:
    state_dict["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(
        yaml.safe_dump(state_dict, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def advance(new_state: str, **updates) -> dict:
    """Update state field + merge other fields · return new state."""
    s = load()
    s["state"] = new_state
    s.update(updates)
    save(s)
    return s


def reset() -> dict:
    """Clear to idle(用户 'pass' / 'reset' 时调)。"""
    d = _default()
    save(d)
    return d


def get_state() -> str:
    return load().get("state", STATE_IDLE)
