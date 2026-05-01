#!/usr/bin/env python3
"""idea.py · 文章 idea 库 CLI · 给用户和 Discord bot 调用。

用法:
    idea.py add <title> [--category cat] [--priority N] [--tags t1,t2]
                        [--source src] [--notes ...]
    idea.py list [--category cat] [--all]
    idea.py show <id>
    idea.py done <id> [--article-md PATH]
    idea.py rm <id>
    idea.py stats

设计公约:
    - thin wrapper over scripts/workflow/_idea_bank.py
    - 输出给 Discord bot 直接显示 · emoji + markdown 表格友好
    - 错误统一 ❌ 前缀写到 stderr · exit 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _idea_bank  # noqa: E402


# ---------- helpers ----------

def _err(msg: str) -> None:
    """统一错误输出 → stderr · 调用方负责 sys.exit。"""
    print(f"❌ {msg}", file=sys.stderr)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _truncate(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_table(ideas: list[dict]) -> str:
    """markdown 表格 · id / cat / pri / title。"""
    if not ideas:
        return "(空)"
    lines = [
        "| # | cat | pri | title |",
        "|---|---|---|---|",
    ]
    for i in ideas:
        used_mark = " ✓" if i.get("used") else ""
        lines.append(
            f"| {i['id']} | {i.get('category', '?')} | "
            f"{i.get('priority', 0)} | {_truncate(i['title'], 40)}{used_mark} |"
        )
    return "\n".join(lines)


# ---------- commands ----------

def cmd_add(args: argparse.Namespace) -> int:
    try:
        rec = _idea_bank.add(
            args.title,
            category=args.category,
            source=args.source,
            priority=args.priority,
            tags=_parse_tags(args.tags),
            notes=args.notes or "",
        )
    except ValueError as e:
        _err(str(e))
        return 1
    print(f"✓ 已存 #{rec['id']} · {rec['category']} · {rec['title']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        ideas = _idea_bank.list_ideas(
            category=args.category,
            only_unused=not args.all,
        )
    except ValueError as e:
        _err(str(e))
        return 1
    total = len(ideas)
    head = ideas[:5]
    print(_fmt_table(head))
    extra = total - len(head)
    if extra > 0:
        print(f"\n还有 {extra} 条 · idea list --all 看全")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    rec = _idea_bank.get(args.id)
    if rec is None:
        _err(f"idea #{args.id} 不存在")
        return 1
    tags = ", ".join(rec.get("tags") or []) or "-"
    used = "已用" if rec.get("used") else "未用"
    if rec.get("used") and rec.get("used_at"):
        used = f"已用 @ {rec['used_at']}"
        if rec.get("used_article_md"):
            used += f" → {rec['used_article_md']}"
    notes = rec.get("notes") or "-"
    print(f"id        : #{rec['id']}")
    print(f"title     : {rec['title']}")
    print(f"category  : {rec.get('category', '?')}")
    print(f"priority  : {rec.get('priority', 0)}")
    print(f"source    : {rec.get('source', '?')}")
    print(f"tags      : {tags}")
    print(f"added_at  : {rec.get('added_at', '-')}")
    print(f"used      : {used}")
    print(f"notes     : {notes}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    try:
        rec = _idea_bank.mark_used(args.id, article_md=args.article_md)
    except KeyError:
        _err(f"idea #{args.id} 不存在")
        return 1
    print(f"✓ idea #{rec['id']} 已标记用过 · {rec['title']}")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    try:
        rec = _idea_bank.remove(args.id)
    except KeyError:
        _err(f"idea #{args.id} 不存在")
        return 1
    print(f"🗑️ 已删 #{rec['id']} · {rec['title']}")
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    s = _idea_bank.stats()
    by = s.get("by_category", {})
    parts = " / ".join(f"{c}:{by.get(c, 0)}" for c in _idea_bank.CATEGORIES)
    print(
        f"📊 总 {s['total']} 条 · 未用 {s['unused']} · 已用 {s['used']} · {parts}"
    )
    return 0


# ---------- argparse ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idea.py", description="文章 idea 库")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="添加 idea")
    p_add.add_argument("title", help="idea 标题")
    p_add.add_argument(
        "--category", default=_idea_bank.DEFAULT_CATEGORY,
        choices=_idea_bank.CATEGORIES,
    )
    p_add.add_argument("--priority", type=int, default=_idea_bank.DEFAULT_PRIORITY)
    p_add.add_argument("--tags", default="", help="逗号分隔 · t1,t2")
    p_add.add_argument(
        "--source", default=_idea_bank.DEFAULT_SOURCE,
        choices=_idea_bank.SOURCES,
    )
    p_add.add_argument("--notes", default="")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="列 idea")
    p_list.add_argument("--category", default=None, choices=_idea_bank.CATEGORIES)
    p_list.add_argument("--all", action="store_true", help="包含已用")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="看一条 idea 详情")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_done = sub.add_parser("done", help="标记 idea 已用")
    p_done.add_argument("id", type=int)
    p_done.add_argument("--article-md", default=None, help="关联文章 md 路径")
    p_done.set_defaults(func=cmd_done)

    p_rm = sub.add_parser("rm", help="删除 idea")
    p_rm.add_argument("id", type=int)
    p_rm.set_defaults(func=cmd_rm)

    p_stats = sub.add_parser("stats", help="统计快照")
    p_stats.set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
