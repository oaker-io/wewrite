#!/usr/bin/env bash
# auto-sync-xhs.sh · 凌晨 03:05 launchd 兜底 · Push 模型(xhswrite publish 直 fire)
# 漏的 event 这里捞回来 · 让 xhs 主题永远不漏入 wewrite idea_bank
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "sync_xhs"
load_keys

LOG="$LOG_DIR/auto-sync-xhs.$(date +%F).log"
echo "[$(date '+%F %T')] → sync_from_xhs.py" >> "$LOG"

if "$PY" scripts/sync_from_xhs.py "$@" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ sync done" >> "$LOG"
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ sync exit=$rc" >> "$LOG"
  notify_failure "sync_xhs" "sync_from_xhs.py 退出 $rc · xhswrite events.jsonl 不存在 / Discord push 失败 ?"
  exit $rc
fi
