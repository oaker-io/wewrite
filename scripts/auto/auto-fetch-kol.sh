#!/usr/bin/env bash
# auto-fetch-kol.sh · 凌晨 03:00 launchd 触发 · 抓 KOL 公众号 RSS 入 idea_bank
# 错峰原因:用户睡觉时段 · 不抢白天/晚上的 claude token
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "fetch_kol"
load_keys

LOG="$LOG_DIR/auto-fetch-kol.$(date +%F).log"
echo "[$(date '+%F %T')] → fetch_kol.py" >> "$LOG"

if "$PY" scripts/fetch_kol.py "$@" >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ fetch_kol done" >> "$LOG"
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ fetch_kol exit=$rc" >> "$LOG"
  notify_failure "fetch_kol" "fetch_kol.py 退出 $rc · 可能 wewe-rss 没起 / cookie 失效 / RSS url 错"
  exit $rc
fi
