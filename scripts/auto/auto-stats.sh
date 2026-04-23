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
  echo "[$(date '+%F %T')] ✓ stats done" >> "$LOG"
  # 推一份周报
  STATS_MSG="📊 **周日 02:00 · 数据回填完成**
本周 fan_count / read_count 已写入 output/history.yaml
看趋势:cat output/history.yaml | grep -A 2 fan_count_after | tail -20"
  "$PY" "$PUSH" --text "$STATS_MSG" 2>/dev/null || true
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ stats exit=$rc" >> "$LOG"
  notify_failure "stats" "fetch_stats.py 退出 $rc"
  exit $rc
fi
