#!/usr/bin/env bash
# auto-stats.sh · 周日 02:00 launchd 触发 · 回填 fan_count + read_count 到 history.yaml
# 调用 scripts/fetch_stats.py(已有 · 拉 wechat data API)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "stats"
load_keys

LOG="$LOG_DIR/auto-stats.$(date +%F).log"
echo "[$(date '+%F %T')] → auto_stats" >> "$LOG"

# fetch_stats.py 是仓里现有脚本(可能要传 --week 参数 · 看 README)
FETCH="$REPO_ROOT/scripts/fetch_stats.py"

if [ ! -f "$FETCH" ]; then
  echo "[$(date '+%F %T')] · skip · $FETCH 不存在" >> "$LOG"
  exit 0
fi

if "$PY" "$FETCH" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ fetch_stats done" >> "$LOG"
  STATS_MSG="📊 **周日 02:00 · 数据回填完成**
本周 fan_count / read_count 已写入 output/history.yaml
看趋势:cat output/history.yaml | grep -A 2 fan_count_after | tail -20"
  "$PY" "$PUSH" --text "$STATS_MSG" 2>/dev/null || true
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ fetch_stats exit=$rc" >> "$LOG"
  notify_failure "stats" "fetch_stats.py 退出 $rc"
  # 不 exit · 继续跑配额报告(独立功能 · 不依赖 fetch_stats)
fi

# 配额周报(POE / GEMINI)· 独立步骤 · fetch_stats 失败也跑
echo "[$(date '+%F %T')] → check_poe_quota" >> "$LOG"
QUOTA_SCRIPT="$REPO_ROOT/scripts/check_poe_quota.py"
if [ -f "$QUOTA_SCRIPT" ]; then
  if "$PY" "$QUOTA_SCRIPT" --push >> "$LOG" 2>&1; then
    echo "[$(date '+%F %T')] ✓ quota report pushed" >> "$LOG"
  else
    rc=$?
    echo "[$(date '+%F %T')] ⚠ quota report exit=$rc" >> "$LOG"
    # 不 notify_failure · 配额报告失败不重要
  fi
fi

exit 0
