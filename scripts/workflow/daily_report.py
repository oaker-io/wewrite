"""daily_report.py · 每日 22:00 通过 Discord 汇报今天爬了啥/发了啥/明天计划。

数据源:
  - output/kol_corpus.yaml          KOL 公众号正文 + last_fetched
  - output/idea_bank.yaml           素材库 · 今日新增条数
  - ~/xhswrite/bus/events.jsonl     小红书发布事件(同步入草稿箱)
  - output/session.yaml             今日 publish state
  - output/*.md                     今日产出 markdown
  - bus/cost.jsonl                  今日 image 成本
  - config/auto-schedule.yaml       明日轮播 category + companions

输出格式:Discord markdown · 通过 discord-bot/push.py --text 发出。
失败 fail-safe:任何数据缺失都不阻断 · 用「(无数据)」占位。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
XHS_EVENTS = Path.home() / "xhswrite" / "bus" / "events.jsonl"


def _today_str() -> str:
    return date.today().isoformat()


def _is_today(ts: str, today: str) -> bool:
    """ts 形如 '2026-04-26T03:00:05+08:00' 或 '2026-04-26' · 取前 10 字符比 today。"""
    if not ts:
        return False
    return ts[:10] == today


def _kol_summary(today: str) -> dict:
    """统计今天 KOL 抓了多少篇 + 涉及哪些 KOL。"""
    p = ROOT / "output" / "kol_corpus.yaml"
    if not p.exists():
        return {"count": 0, "kols": [], "last_fetched": None}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    last_fetched = (data.get("last_fetched") or "")[:10]
    arts = data.get("articles") or []
    today_arts = [a for a in arts if _is_today(a.get("pub_date", ""), today)]
    kols = sorted({a.get("kol", "") for a in today_arts if a.get("kol")})
    return {
        "count": len(today_arts),
        "total": len(arts),
        "kols": kols,
        "last_fetched": last_fetched,
    }


def _idea_bank_today(today: str) -> int:
    """idea_bank 今日新增条数(按 added_at / created_at / date 字段过滤)。"""
    p = ROOT / "output" / "idea_bank.yaml"
    if not p.exists():
        return 0
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return 0
    items = data.get("ideas") or data.get("items") or (data if isinstance(data, list) else [])
    if not isinstance(items, list):
        return 0
    n = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        ts = it.get("added_at") or it.get("created_at") or it.get("date") or ""
        if isinstance(ts, str) and _is_today(ts, today):
            n += 1
    return n


def _xhs_today(today: str) -> dict:
    """读 xhswrite events · 今日 publish kind=done · 算同步入公众号草稿数。"""
    if not XHS_EVENTS.exists():
        return {"publish_count": 0, "image_count": 0}
    pub = img = 0
    for line in XHS_EVENTS.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not _is_today(ev.get("ts", ""), today):
            continue
        if ev.get("agent") == "publish" and ev.get("kind") == "done":
            pub += 1
            imgs = ev.get("images") or []
            if isinstance(imgs, list):
                img += len(imgs)
    return {"publish_count": pub, "image_count": img}


def _published_today(today: str) -> list[dict]:
    """今日发布的文章列表 · 优先看 session.yaml + output/{today}-*.md 文件名。"""
    out: list[dict] = []
    # 1. session.yaml 当前态(最近一篇)
    sp = ROOT / "output" / "session.yaml"
    if sp.exists():
        try:
            ses = yaml.safe_load(sp.read_text(encoding="utf-8")) or {}
            if ses.get("state") == "done" and ses.get("article_date") == today:
                topic = ses.get("selected_topic") or {}
                out.append({
                    "title": topic.get("title", "(无标题)"),
                    "md": ses.get("article_md", ""),
                    "media_id": ses.get("draft_media_id", ""),
                    "style": ses.get("style", ""),
                })
        except yaml.YAMLError:
            pass
    # 2. 扫 output/{today}-*.md(可能多于 session 当前态 · 主+副推)
    md_files = sorted((ROOT / "output").glob(f"{today}-*.md"))
    seen_md = {o["md"] for o in out}
    for md in md_files:
        rel = str(md.relative_to(ROOT))
        if rel in seen_md or md.name.endswith("-prompts.md"):
            continue
        out.append({
            "title": _extract_title_from_md(md),
            "md": rel,
            "media_id": "",
            "style": "shortform" if "shortform" in md.name else "main",
        })
    return out


def _extract_title_from_md(p: Path) -> str:
    try:
        first = p.read_text(encoding="utf-8").splitlines()[0]
        return re.sub(r"^#+\s*", "", first).strip() or p.stem
    except (OSError, IndexError):
        return p.stem


def _cost_today(today: str) -> dict:
    """统计 bus/cost.jsonl 今日 image 调用次数 + 总成本。"""
    p = ROOT / "bus" / "cost.jsonl"
    if not p.exists():
        return {"image_calls": 0, "cost_usd": 0.0, "by_tier": {}}
    calls = 0
    total = 0.0
    by_tier: dict[str, int] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if ev.get("date") != today or ev.get("kind") != "image":
            continue
        calls += int(ev.get("count", 0)) or 1
        total += float(ev.get("cost", 0) or 0)
        tier = ev.get("tier") or ev.get("model") or "?"
        by_tier[tier] = by_tier.get(tier, 0) + 1
    return {"image_calls": calls, "cost_usd": round(total, 3), "by_tier": by_tier}


def _tomorrow_plan() -> dict:
    """读 auto-schedule.yaml · 明日 weekday → label + companions count。"""
    cfg_p = ROOT / "config" / "auto-schedule.yaml"
    if not cfg_p.exists():
        return {"label": "(无配置)", "companions_count": 0}
    try:
        cfg = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"label": "(配置解析失败)", "companions_count": 0}
    schedule = cfg.get("schedule") or []
    tom_wd = (date.today() + timedelta(days=1)).weekday()
    for s in schedule:
        if s.get("weekday") == tom_wd:
            comps = s.get("companions") or []
            mains = s.get("mains") or []
            return {
                "label": s.get("label", f"weekday={tom_wd}"),
                "companions_count": len(comps),
                "mains_count": len(mains) or 1,
                "tags": list({tag for c in comps for tag in (c.get("topic_tags") or [])})[:4],
            }
    return {"label": f"weekday={tom_wd} · 未配置", "companions_count": 0}


def build_report() -> str:
    today = _today_str()
    tom = (date.today() + timedelta(days=1)).strftime("%-m/%-d")
    today_short = date.today().strftime("%-m/%-d")

    kol = _kol_summary(today)
    idea_n = _idea_bank_today(today)
    xhs = _xhs_today(today)
    pubs = _published_today(today)
    cost = _cost_today(today)
    plan = _tomorrow_plan()

    lines = [f"🌙 **智辰 · {today_short} 日报**", ""]

    # ── 爬取
    lines.append("📥 **爬取**")
    if kol["count"]:
        kol_preview = "/".join(kol["kols"][:5])
        more = f" · +{len(kol['kols'])-5}" if len(kol["kols"]) > 5 else ""
        lines.append(f"• KOL 公众号 {kol['count']} 篇({kol_preview}{more})")
    else:
        lines.append(f"• KOL 0 新篇 · 库存 {kol['total']} 篇 · 上次 {kol['last_fetched'] or '?'}")
    if idea_n:
        lines.append(f"• idea_bank 新增 {idea_n} 条")
    if xhs["publish_count"]:
        lines.append(f"• 小红书同步 {xhs['publish_count']} 篇 · {xhs['image_count']} 张图入草稿")
    if not (kol["count"] or idea_n or xhs["publish_count"]):
        lines.append("• (今日 0 抓取)")

    # ── 发布
    lines.append("")
    lines.append("📤 **发布**")
    if pubs:
        for p in pubs[:3]:
            tag = "主" if p["style"] in ("main", "case", "tutorial", "review") else "副"
            link = f"  https://mp.weixin.qq.com/cgi-bin/draft?mediaId={p['media_id']}" if p["media_id"] else ""
            lines.append(f"• [{tag}] {p['title'][:36]}{link}")
        if len(pubs) > 3:
            lines.append(f"• …还有 {len(pubs)-3} 篇")
    else:
        lines.append("• (今日 0 发布)")
    if cost["image_calls"]:
        tier_str = " · ".join(f"{k}×{v}" for k, v in cost["by_tier"].items())
        lines.append(f"• 配图 {cost['image_calls']} 张 · ${cost['cost_usd']:.3f} · {tier_str}")

    # ── 明日
    lines.append("")
    lines.append(f"🌅 **明日({tom})**")
    lines.append(f"• {plan['label']}")
    if plan.get("mains_count"):
        lines.append(f"• 主推 {plan['mains_count']} · 副推 {plan['companions_count']}")
    elif plan["companions_count"]:
        lines.append(f"• 副推 {plan['companions_count']} 篇")
    if plan.get("tags"):
        lines.append(f"• 标签:{' / '.join(plan['tags'])}")

    return "\n".join(lines)


def push(text: str) -> bool:
    """走 discord-bot/push.py 发出。"""
    push_py = ROOT / "discord-bot" / "push.py"
    if not push_py.exists():
        print("⚠ push.py 不存在 · 直接 print 不发", file=sys.stderr)
        print(text)
        return False
    py = ROOT / "venv" / "bin" / "python3"
    if not py.exists():
        py = "python3"
    try:
        r = subprocess.run(
            [str(py), str(push_py), "--text", text],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"⚠ push 失败 exit={r.returncode}: {r.stderr[-300:]}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("⚠ push 超时", file=sys.stderr)
        return False


def main() -> int:
    text = build_report()
    if "--dry-run" in sys.argv or os.environ.get("WEWRITE_DRY") == "1":
        print(text)
        return 0
    ok = push(text)
    if not ok:
        # 即便 push 失败也 print · 让 launchd log 能看到内容
        print(text)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
