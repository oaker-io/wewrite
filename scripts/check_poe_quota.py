#!/usr/bin/env python3
"""check_poe_quota · 汇总 POE / GEMINI / 其他图模型本日/周/月用量。

数据源:`~/.claude/wewrite-quota.json` (wewrite + xwrite 共用 · 同一个 image_gen.py 模块)

POE 没公开 quota 查询 API · 用本地记账(每次成功/失败都 +1)汇总。
不是「真实 POE 余额」· 但能看出消耗趋势 · 撞顶趋势可预警。

POE 自动续费已开 → 撞顶会自动加 · 但仍建议:
  - 月初看一次实际 poe.com/settings 余额(本地记账可能漏统计 · 有 5-10% 偏差)
  - 异常增长(单日 > 50)立即看是不是哪里循环 retry

用法:
  python3 scripts/check_poe_quota.py             # 标准报告(stdout markdown)
  python3 scripts/check_poe_quota.py --json      # JSON 输出
  python3 scripts/check_poe_quota.py --push      # push Discord
  python3 scripts/check_poe_quota.py --week 2026-W17  # 指定 ISO week(默认本周)

设计:
  - 纯函数 + 文件 IO · 不调外部 API · 安全
  - quota.json 不存在或损坏 → 输出空报告(兜底)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUOTA_FILE = Path.home() / ".claude" / "wewrite-quota.json"
PUSH = REPO_ROOT / "discord-bot" / "push.py"
PY = REPO_ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def load_quota(path: Path = QUOTA_FILE) -> dict:
    """读 quota.json · 不存在或损坏返回空 dict。"""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _parse_key(key: str) -> tuple[str, date] | None:
    """key 格式 'provider:YYYY-MM-DD' · 解析失败返回 None。"""
    if ":" not in key:
        return None
    provider, dstr = key.split(":", 1)
    try:
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
    except ValueError:
        return None
    return provider, d


def aggregate(
    quota: dict,
    *,
    today: date | None = None,
) -> dict:
    """聚合 quota.json · 返回:

    {
      "today":   {"poe": {"success": N, "fail": N}, "gemini": {...}, ...},
      "week":    {"poe": {"success": N, "fail": N}, ...},
      "month":   {"poe": ..., ...},
      "last_week": {"poe": ..., ...},  # 上周对比用
      "by_day":  [{"date": "2026-04-23", "poe": 6, "gemini": 0}, ...],  # 最近 14 天
    }
    """
    today = today or datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())  # 周一
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    month_start = today.replace(day=1)

    def _new_bucket() -> dict:
        return {}

    out = {
        "today": _new_bucket(),
        "week": _new_bucket(),
        "last_week": _new_bucket(),
        "month": _new_bucket(),
    }

    by_day_map: dict[date, dict] = {}

    for k, v in quota.items():
        parsed = _parse_key(k)
        if not parsed:
            continue
        provider, d = parsed
        success = int(v.get("success", 0))
        fail = int(v.get("fail", 0))

        # 14 天 by-day
        if (today - d).days <= 13 and d <= today:
            day_entry = by_day_map.setdefault(d, {})
            day_entry[provider] = day_entry.get(provider, 0) + success

        # today
        if d == today:
            entry = out["today"].setdefault(provider, {"success": 0, "fail": 0})
            entry["success"] += success
            entry["fail"] += fail

        # this week (Mon-Sun · 含今天)
        if week_start <= d <= today:
            entry = out["week"].setdefault(provider, {"success": 0, "fail": 0})
            entry["success"] += success
            entry["fail"] += fail

        # last week
        if last_week_start <= d <= last_week_end:
            entry = out["last_week"].setdefault(provider, {"success": 0, "fail": 0})
            entry["success"] += success
            entry["fail"] += fail

        # this month
        if month_start <= d <= today:
            entry = out["month"].setdefault(provider, {"success": 0, "fail": 0})
            entry["success"] += success
            entry["fail"] += fail

    # by_day 排序 + 填空(没记录的日子写 0)
    by_day = []
    for i in range(13, -1, -1):  # 14 天 · 老的在前
        d = today - timedelta(days=i)
        entry = by_day_map.get(d, {})
        by_day.append({
            "date": d.isoformat(),
            **entry,
        })
    out["by_day"] = by_day
    return out


def _trend_arrow(now: int, prev: int) -> str:
    if prev == 0:
        return "🆕" if now > 0 else "·"
    pct = (now - prev) / prev * 100
    if pct >= 30:
        return f"🔺{pct:+.0f}%"
    if pct <= -30:
        return f"🔻{pct:+.0f}%"
    return f"·{pct:+.0f}%"


def format_report(agg: dict) -> str:
    """汇总成 markdown 报告(给 Discord push 用)。"""
    today_data = agg["today"]
    week_data = agg["week"]
    last_week_data = agg["last_week"]
    month_data = agg["month"]
    by_day = agg["by_day"]

    # 涉及哪些 provider
    providers = set()
    for d in (today_data, week_data, month_data):
        providers.update(d.keys())
    providers = sorted(providers)

    if not providers:
        return ("📊 **图模型配额报告** · 暂无数据\n"
                f"`{QUOTA_FILE}` 不存在或本月没生过图。")

    lines = [
        "📊 **图模型配额周报** · " + datetime.now().strftime("%Y-%m-%d"),
        f"_数据源:`{QUOTA_FILE.name}` (wewrite + xwrite 共用)_",
        "",
    ]

    # 今日 / 本周 / 本月 三栏
    lines.append("**今日 / 本周 / 上周 / 本月** (成功 / 失败):")
    lines.append("```")
    lines.append(f"{'provider':<10} {'today':<12} {'week':<14} {'last week':<12} {'month':<12}")
    for p in providers:
        td = today_data.get(p, {"success": 0, "fail": 0})
        wk = week_data.get(p, {"success": 0, "fail": 0})
        lw = last_week_data.get(p, {"success": 0, "fail": 0})
        mo = month_data.get(p, {"success": 0, "fail": 0})
        trend = _trend_arrow(wk["success"], lw["success"])
        lines.append(
            f"{p:<10} "
            f"{td['success']}/{td['fail']:<10} "
            f"{wk['success']}/{wk['fail']} {trend:<6} "
            f"{lw['success']}/{lw['fail']:<10} "
            f"{mo['success']}/{mo['fail']}"
        )
    lines.append("```")
    lines.append("")

    # 14 天趋势(只看 success)
    lines.append("**最近 14 天 success 数**(柱状)·")
    lines.append("```")
    for entry in by_day:
        d = entry["date"][-5:]  # MM-DD
        bars = []
        for p in providers:
            n = entry.get(p, 0)
            bar = "█" * n if n > 0 else ""
            bars.append(f"{p[:6]:>6}={n:>2} {bar}")
        lines.append(f"{d}  " + " | ".join(bars))
    lines.append("```")
    lines.append("")

    # 风险提示
    week_total = sum(week_data.get(p, {"success": 0})["success"] for p in providers)
    last_week_total = sum(last_week_data.get(p, {"success": 0})["success"] for p in providers)

    lines.append("**判断**:")
    if week_total == 0:
        lines.append("· 本周 0 调用 · 是否 wewrite/xwrite cron 都停了?")
    elif last_week_total > 0 and week_total > last_week_total * 1.5:
        lines.append(f"· ⚠ 本周用量 {week_total} 比上周 {last_week_total} 涨 50%+ · 检查是否有循环 retry")
    elif week_total > 100:
        lines.append(f"· 本周累计 {week_total} 张图 · 量级正常 · 月底看 poe.com/settings")
    else:
        lines.append(f"· 本周 {week_total} 张图 · 健康")

    poe_fail = week_data.get("poe", {"fail": 0})["fail"]
    poe_succ = week_data.get("poe", {"success": 0})["success"]
    if poe_succ + poe_fail > 0 and poe_fail / (poe_succ + poe_fail) > 0.3:
        lines.append(f"· ⚠ POE 失败率 {poe_fail}/{poe_succ + poe_fail} > 30% · 检查 API key 或网络")

    lines.append("")
    lines.append("**POE 自动续费已开** → 撞顶自动加 · 但建议:")
    lines.append("· 月初看一次实际余额:https://poe.com/settings/subscription")
    lines.append("· 异常激增(单日 > 50)立即查 wewrite/xwrite cron 是否循环")

    return "\n".join(lines)


def push_discord(text: str) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            check=True, timeout=60,
        )
    except Exception as e:
        print(f"⚠ push 失败: {e}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="POE / GEMINI 图模型配额周报")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--push", action="store_true", help="push Discord")
    p.add_argument("--quota-file", default=str(QUOTA_FILE),
                   help="quota json 路径(默认 ~/.claude/wewrite-quota.json)")
    args = p.parse_args()

    quota = load_quota(Path(args.quota_file))
    agg = aggregate(quota)

    if args.json:
        print(json.dumps(agg, ensure_ascii=False, indent=2, default=str))
    else:
        report = format_report(agg)
        print(report)
        if args.push:
            push_discord(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
