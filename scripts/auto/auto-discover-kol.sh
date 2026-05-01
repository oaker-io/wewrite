#!/usr/bin/env bash
# auto-discover-kol.sh · 03:30 launchd 触发 · 选 5 个 AI KOL 候选 · 写 output/kol_candidates.yaml
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "discover_kol"
load_keys

LOG="$LOG_DIR/auto-discover-kol.$(date +%F).log"
echo "[$(date '+%F %T')] → discover_kol" >> "$LOG"

DISCOVER="$REPO_ROOT/scripts/workflow/discover_kol.py"
if [ ! -f "$DISCOVER" ]; then
  echo "[$(date '+%F %T')] · skip · $DISCOVER 不存在" >> "$LOG"
  exit 0
fi

if "$PY" "$DISCOVER" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ discover_kol done" >> "$LOG"
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ discover_kol exit=$rc" >> "$LOG"
  notify_failure "discover_kol" "exit=$rc · 看 $LOG" || true
fi
