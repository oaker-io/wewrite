"""Idea bank · output/idea_bank.yaml 持久化。

数据模型(YAML):
    next_id: 7
    ideas:
      - id: 1
        title: "claude design 9 个使用技巧"
        added_at: "2026-04-21T11:38:00+08:00"
        category: "tutorial"      # tutorial | hotspot | flexible
        source: "user"            # user | changelog | github | manual
        tags: ["claude", "tutorial"]
        priority: 50              # 0-100 · list 时排序
        used: false
        used_at: null
        used_article_md: null
        notes: ""

设计公约:
    - 纯函数接口(load / save / add / list / mark_used / remove)
    - 文件不存在时返回空模型 · 不报错
    - id 自增 · 不复用
    - tags 是字符串列表 · 用于后续筛选
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_BANK_FILE = _ROOT / "output" / "idea_bank.yaml"

CATEGORIES = ("tutorial", "hotspot", "flexible")
SOURCES = ("user", "changelog", "github", "manual")
DEFAULT_CATEGORY = "flexible"
DEFAULT_SOURCE = "user"
DEFAULT_PRIORITY = 50

# 北京时区(避免 ISO 时间戳无 tz 信息)
_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def _empty_model() -> dict:
    return {"next_id": 1, "ideas": []}


def _file() -> Path:
    """暴露文件路径 · 测试可 monkeypatch。"""
    return Path(os.environ.get("WEWRITE_IDEA_BANK", str(_BANK_FILE)))


def load() -> dict:
    """读 idea_bank.yaml · 不存在返回空模型。"""
    f = _file()
    if not f.exists():
        return _empty_model()
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return _empty_model()
    if "next_id" not in data:
        data["next_id"] = 1
    if "ideas" not in data:
        data["ideas"] = []
    return data


def save(model: dict) -> None:
    """写 idea_bank.yaml · 父目录确保存在。"""
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        yaml.safe_dump(model, allow_unicode=True, sort_keys=False, indent=2),
        encoding="utf-8",
    )


def add(
    title: str,
    *,
    category: str = DEFAULT_CATEGORY,
    source: str = DEFAULT_SOURCE,
    priority: int = DEFAULT_PRIORITY,
    tags: list[str] | None = None,
    notes: str = "",
) -> dict:
    """添加一条 idea · 返回完整记录(含分配的 id)。"""
    title = (title or "").strip()
    if not title:
        raise ValueError("idea title 不能为空")
    if category not in CATEGORIES:
        raise ValueError(f"category 必须 ∈ {CATEGORIES} · 收到 {category!r}")
    if source not in SOURCES:
        raise ValueError(f"source 必须 ∈ {SOURCES} · 收到 {source!r}")
    priority = max(0, min(100, int(priority)))

    model = load()
    new_id = model["next_id"]
    record = {
        "id": new_id,
        "title": title,
        "added_at": _now_iso(),
        "category": category,
        "source": source,
        "tags": list(tags or []),
        "priority": priority,
        "used": False,
        "used_at": None,
        "used_article_md": None,
        "notes": notes,
    }
    model["ideas"].append(record)
    model["next_id"] = new_id + 1
    save(model)
    return record


def list_ideas(
    *,
    category: str | None = None,
    only_unused: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """列 idea · 默认只返回未用的 · 按 (priority desc, id desc) 排序。"""
    model = load()
    ideas = model["ideas"]
    if category:
        if category not in CATEGORIES:
            raise ValueError(f"category 必须 ∈ {CATEGORIES}")
        ideas = [i for i in ideas if i.get("category") == category]
    if only_unused:
        ideas = [i for i in ideas if not i.get("used")]
    ideas = sorted(ideas, key=lambda i: (-i.get("priority", 0), -i["id"]))
    if limit is not None and limit > 0:
        ideas = ideas[:limit]
    return ideas


def get(idea_id: int) -> dict | None:
    """按 id 取一条 · 找不到返回 None。"""
    model = load()
    for i in model["ideas"]:
        if i["id"] == idea_id:
            return i
    return None


def mark_used(idea_id: int, *, article_md: str | None = None) -> dict:
    """标记某条 idea 已用 · 返回更新后的记录。"""
    model = load()
    for i in model["ideas"]:
        if i["id"] == idea_id:
            i["used"] = True
            i["used_at"] = _now_iso()
            if article_md:
                i["used_article_md"] = article_md
            save(model)
            return i
    raise KeyError(f"idea id={idea_id} 不存在")


def remove(idea_id: int) -> dict:
    """删除某条 idea · 返回被删的记录。"""
    model = load()
    for idx, i in enumerate(model["ideas"]):
        if i["id"] == idea_id:
            removed = model["ideas"].pop(idx)
            save(model)
            return removed
    raise KeyError(f"idea id={idea_id} 不存在")


def stats() -> dict:
    """快照 · 总数 / 未用 / 各 category 分布。"""
    model = load()
    ideas = model["ideas"]
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    for i in ideas:
        cat = i.get("category", DEFAULT_CATEGORY)
        if cat in by_cat:
            by_cat[cat] += 1
    return {
        "total": len(ideas),
        "unused": sum(1 for i in ideas if not i.get("used")),
        "used": sum(1 for i in ideas if i.get("used")),
        "by_category": by_cat,
    }
