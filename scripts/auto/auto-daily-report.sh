#!/usr/bin/env bash
# auto-daily-report.sh · 22:00 launchd 触发 · Discord 日报(爬了啥/发了啥/明天计划)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "daily_report"
load_keys

LOG="$LOG_DIR/auto-daily-report.$(date +%F).log"
echo "[$(date '+%F %T')] → daily_report" >> "$LOG"

REPORT="$REPO_ROOT/scripts/workflow/daily_report.py"
if [ ! -f "$REPORT" ]; then
  echo "[$(date '+%F %T')] · skip · $REPORT 不存在" >> "$LOG"
  exit 0
fi

if "$PY" "$REPORT" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ daily_report done" >> "$LOG"
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ daily_report exit=$rc" >> "$LOG"
  notify_failure "daily_report" "exit=$rc · 看 $LOG" || true
fi
