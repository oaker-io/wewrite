"""Session state helper · 跨 claude -p session 的 workflow 状态机。

状态持久化到 output/session.yaml · 被 4 个 workflow 脚本(brief/write/images/publish)
+ bot.py 共享读写。

State transitions:
    idle → briefed → writing → wrote → generating → imaged → publishing → done
    (回退:任一 state → idle 代表用户说 "pass" 或 "重来")

Field schema:
    state: str            当前状态
    article_date: str     YYYY-MM-DD
    topics: list          brief 产出的混合选题(热点 Top N + idea 库 Top M)
                          每个 topic 是 dict · 关键字段:
                            title / source / hot / score / ai_kw / url
                            from: "hotspot" | "idea"   ← 阶段 D 加 · 来源标识
                            idea_id: int | null        ← 阶段 D 加 · idea 库 id(hotspot 为 null)
                            category: str (idea 才有)  ← tutorial / hotspot / flexible
    selected_idx: int     用户选的序号(0/1/2/...)
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


def _resolve_state_file() -> Path:
    """单测把 WEWRITE_SESSION_FILE 指向 tmpdir · 避免改到真实 output/session.yaml。"""
    override = os.environ.get("WEWRITE_SESSION_FILE")
    if override:
        return Path(override)
    return _ROOT / "output" / "session.yaml"


_STATE_FILE = _resolve_state_file()

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


_TERMINAL_STATES = {STATE_WROTE, STATE_IMAGED, STATE_DONE}


class StateGuardError(RuntimeError):
    """advance 拒绝把进行中的工作状态打回 briefed/idle 时抛出。"""


def advance(new_state: str, *, force: bool = False, **updates) -> dict:
    """Update state field + merge other fields · return new state.

    Why: 旧 daily-brief plist 在 wrote 状态后又跑 brief.py,把 state 打回 briefed +
    article_md 清空,导致 images/review/publish 全 skip。加 guard 防御:
    当前在 wrote/imaged/done 时,不能未授权地往回退到 briefed/idle。

    显式重置请用 reset() 或传 force=True。
    """
    s = load()
    cur = s.get("state", STATE_IDLE)
    if (not force
            and cur in _TERMINAL_STATES
            and new_state in {STATE_BRIEFED, STATE_IDLE}):
        raise StateGuardError(
            f"refuse to overwrite state={cur} → {new_state} without force=True. "
            f"Call _state.reset() if user explicitly wants a new article."
        )
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
