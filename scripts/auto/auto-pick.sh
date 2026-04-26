#!/usr/bin/env bash
# auto-pick.sh · 07:00 launchd 触发 · 调 auto_pick.py 选今日选题
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "pick"
load_keys

LOG="$LOG_DIR/auto-pick.$(date +%F).log"
echo "[$(date '+%F %T')] → auto_pick.py" >> "$LOG"

# 跨日 / done · 自动 reset · 防 4/26 root cause(state=done 不是当日 → auto-write SKIP)
if "$PY" -c "import sys;sys.path.insert(0,'scripts/workflow');import _state;
sys.exit(0 if _state.reset_if_stale() else 1)" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] · session stale → auto-reset 触发" >> "$LOG"
fi

if "$PY" scripts/workflow/auto_pick.py "$@" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ pick done" >> "$LOG"
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ pick exit=$rc" >> "$LOG"
  notify_failure "pick" "auto_pick.py 退出码 $rc · 可能 idea 库为空 · 请发「存 idea: ...」"
  exit $rc
fi
