#!/usr/bin/env bash
# auto-comment-kickoff.sh · 20:00 launchd 触发 · 群发后推置顶话术
# 只有 state=done 才推(说明今天确实推了草稿且已群发)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "comment_kickoff"
load_keys

LOG="$LOG_DIR/auto-comment-kickoff.$(date +%F).log"

STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)

echo "[$(date '+%F %T')] → comment-kickoff · state=$STATE" >> "$LOG"

if [[ "$STATE" != "done" ]]; then
  echo "[$(date '+%F %T')] · skip · state=$STATE 不是 done · 没草稿可置顶" >> "$LOG"
  exit 0
fi

# 防 stale session (跟 auto-notify 同逻辑)
TODAY=$(date +%F)
SESSION_DATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    d = s.get('article_date')
    if not d:
        u = s.get('updated_at') or ''
        d = u.split('T')[0] if u else ''
    print(d)
except Exception:
    print('')
" 2>/dev/null)

if [[ "$SESSION_DATE" != "$TODAY" ]]; then
  echo "[$(date '+%F %T')] · skip · session.date=$SESSION_DATE 不是 today=$TODAY · 不推老话术" >> "$LOG"
  exit 0
fi

if "$PY" scripts/workflow/comment_kickoff.py >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ comment-kickoff pushed" >> "$LOG"
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ comment-kickoff exit=$rc" >> "$LOG"
  notify_failure "comment-kickoff" "comment_kickoff.py 退出 $rc"
  exit $rc
fi
