#!/usr/bin/env python3
"""comment_kickoff · 群发后推 Discord 提醒用户去置顶留言 + 候选话术。

WeChat 评论 写入 API 没公开 · 这步必须用户手动到 mp.weixin.qq.com 操作。
本 script 自动化「候选话术准备 + 提醒时机」 · user 1 tap 复制粘贴即可。

策略:
  - 读 session.yaml 拿当天 style / weekday / category
  - 从 references/comment-playbook.md 选 2 个最适合的置顶模板
  - 替换模板里的占位符(系列名 / 关键词 / 下篇预告)
  - push Discord · 含 2 个候选 + 自动回复速查表

用法:
  # 默认 · 读 session 当前 article
  python3 scripts/workflow/comment_kickoff.py

  # 指定模板(覆盖自动选)
  python3 scripts/workflow/comment_kickoff.py --templates A,C

  # 自定义关键词
  python3 scripts/workflow/comment_kickoff.py --keyword "Cursor"

  # 不 push (测试用 · 看候选输出)
  python3 scripts/workflow/comment_kickoff.py --no-push
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

_CST = timezone(timedelta(hours=8))

# 7 天 weekday → 系列名(对接 config/auto-schedule.yaml#schedule)
WEEKDAY_TO_SERIES = {
    0: "AI 使用手册",
    1: "干货教程",
    2: "AI 真实成功案例",
    3: "AI 工具评测",
    4: "深度解读热点",
    5: "轻量分享",
    6: "本周精华合集",
}

# style/category → 推荐的 2 套模板
# (模板 A=连载钩子 / B=问题引导 / C=资源补充 / D=社群引流 / E=反向问 / F=数据来源 / G=30 天约定)
STYLE_TO_TEMPLATES = {
    "tutorial": ("A", "C"),     # 干货 · 连载 + 资源
    "case": ("A", "D"),          # 案例 · 连载 + 引流
    "hotspot": ("E", "B"),       # 热点 · 反向问 + 问题引导
    "shortform": ("D", "B"),     # 短文 · 引流 + 问题
    "default": ("A", "B"),       # 兜底
}

# 模板内容(跟 references/comment-playbook.md 同步)
TEMPLATES = {
    "A": (
        "连载钩子",
        "🐉 【下篇预告】\n本文是「{series}」第 N 篇 · 下一篇:\n「<下篇标题>」<2026-MM-DD>\n\n关注一下不迷路。",
    ),
    "B": (
        "问题引导",
        "☝️ 【问个问题】\n你们用 {keyword} · 最大的坑是哪个?\n评论区告诉我 · 我下篇统一回答 Top 3。",
    ),
    "C": (
        "资源补充",
        "📦 【完整资源】\n本文用到的 SOP / 模板 · 已整理成 Notion。\n评论区扣「{keyword}」· 我私发链接。",
    ),
    "D": (
        "社群引流",
        "💬 【感兴趣的可以聊】\n做这事踩过 N 个坑 · 文章只能写主线 · 细节都在我读者群里。\n加我微信备注「{keyword}」· 我拉你进群。",
    ),
    "E": (
        "反向问",
        "🔥 【你怎么看?】\n本文观点比较冲 · 我知道有人不同意。\n不同意的来评论区辩 · 我每条都回。",
    ),
    "F": (
        "数据来源",
        "📊 【数据来源】\n本文 N 个数据点 全部来自:\n<source-1>: <url>\n<source-2>: <url>\n有疑问可以原文核对。",
    ),
    "G": (
        "30 天约定",
        "📅 【30 天复盘约定】\n我接下来 30 天会日更 {series}。\n关注一下 · 30 天后回来看变化。",
    ),
}

# 自动回复速查(给 user 看 · 评论区每条回时参考)
QUICK_REPLY_CHEATSHEET = """
**评论区自动回复速查**(WeChat 评论 API 不开放 · 这些手动复制):

正向「同感/学到了」 → `🤝` 或 `+1`
共鸣「我也踩过」    → `这个坑大家都踩 · 我下篇统一总结 · 关注一下`
需求「能不能写 X」  → `已记下 · 周内安排 · 想看 X 的可以扣 1`
技术「具体怎么做」  → `这个细节比较深 · 加我微信备注「{keyword}」我详细聊`
反驳「你说错了」    → `<具体回应 1-2 句> · 你的场景特殊 · 加我「{keyword}」聊聊?`
广告/引流          → 不回 + 后台删除
"""


def _extract_keyword(title: str) -> str:
    """从标题抽 1 个关键词作引流暗号。

    优先抽英文(如 Cursor / Claude / Notion)· 没有再抽前 4 个汉字。
    """
    eng = re.findall(r"[A-Za-z][A-Za-z0-9]+", title)
    if eng:
        # 跳过常见无意义短词
        skip = {"AI", "Day", "Week", "How", "Why", "When", "What"}
        for w in eng:
            if w not in skip and len(w) >= 3:
                return w
    # fallback 中文
    chinese = re.findall(r"[一-鿿]+", title)
    if chinese:
        return chinese[0][:4]
    return "AI"


def _resolve_session_meta() -> dict:
    """从 session.yaml 读当天信息 · 兜底默认值。"""
    s = _state.load()
    sched = s.get("auto_schedule") or {}
    topic = s.get("selected_topic") or {}
    weekday = sched.get("weekday")
    if weekday is None:
        weekday = datetime.now(_CST).weekday()
    style = sched.get("style", "default")
    title = topic.get("title", "(本篇)")
    media_id = s.get("draft_media_id", "?")
    return {
        "weekday": weekday,
        "style": style,
        "title": title,
        "media_id": media_id,
        "series": WEEKDAY_TO_SERIES.get(weekday, "AI 笔记"),
    }


def _pick_templates(style: str, override: list[str] | None) -> list[str]:
    if override:
        return [t for t in override if t in TEMPLATES][:3]
    pair = STYLE_TO_TEMPLATES.get(style, STYLE_TO_TEMPLATES["default"])
    return list(pair)


def _render_template(tid: str, *, series: str, keyword: str) -> str:
    label, body = TEMPLATES[tid]
    return f"**模板 {tid} · {label}**\n```\n" + body.format(series=series, keyword=keyword) + "\n```"


def build_message(
    *, title: str, media_id: str, series: str, keyword: str,
    template_ids: list[str],
) -> str:
    rendered = "\n\n".join(_render_template(t, series=series, keyword=keyword) for t in template_ids)
    return (
        f"🔔 **评论区 kickoff** · {datetime.now(_CST).strftime('%H:%M')}\n"
        f"📝 {title[:60]}\n"
        f"🆔 {media_id[:20]}\n\n"
        "**【现在做】**:群发出去后立即:\n"
        "1. mp.weixin.qq.com → 文章详情 → 评论区\n"
        "2. 复制下面任一模板 → 发评论 → 长按置顶\n\n"
        f"{rendered}\n\n"
        f"{QUICK_REPLY_CHEATSHEET.format(keyword=keyword).strip()}\n\n"
        "**【1 小时后】**:回评论区 · 每条新评论回 1-2 句(参考速查表)。\n"
        "**【24 小时内】**:必须每条都回(哪怕 1 个 emoji)· 评论数 + 互动数计入 CES 算法 · 拉曝光。"
    )


def push_discord(text: str) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            check=True, timeout=60,
        )
    except Exception as e:
        print(f"⚠ push 失败: {e}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="comment_kickoff · 群发后推置顶话术")
    p.add_argument("--templates", help="逗号分隔模板 ID(eg A,C)· 默认按 style 自动选")
    p.add_argument("--keyword", help="引流暗号(默认从标题抽)")
    p.add_argument("--no-push", action="store_true", help="不 push · 只 stdout")
    args = p.parse_args()

    meta = _resolve_session_meta()
    title = meta["title"]
    keyword = args.keyword or _extract_keyword(title)
    series = meta["series"]
    media_id = meta["media_id"]
    style = meta["style"]

    override = None
    if args.templates:
        override = [t.strip().upper() for t in args.templates.split(",") if t.strip()]
    template_ids = _pick_templates(style, override)

    msg = build_message(
        title=title, media_id=media_id, series=series,
        keyword=keyword, template_ids=template_ids,
    )

    print(msg)

    if not args.no_push:
        push_discord(msg)
        print(f"\n✓ pushed · weekday={meta['weekday']} style={style} · "
              f"templates={template_ids} keyword={keyword!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
