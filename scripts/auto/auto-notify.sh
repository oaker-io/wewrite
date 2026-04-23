#!/usr/bin/env bash
# auto-notify.sh · 19:30 launchd 触发 · 提醒用户去 mp.weixin.qq.com 点群发
# (不实现 masssend API · 决策 3:用户每晚 1 tap 替代)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "notify"
load_keys

LOG="$LOG_DIR/auto-notify.$(date +%F).log"

# 只有当 state=done 才推(说明今天确实推了草稿)
STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)

TITLE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    t = s.get('selected_topic') or {}
    print(t.get('title', '(无题)')[:50])
except Exception:
    print('(无题)')
" 2>/dev/null)

MEDIA_ID=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('draft_media_id', '?')[:20])
except Exception:
    print('?')
" 2>/dev/null)

echo "[$(date '+%F %T')] → auto_notify · state=$STATE" >> "$LOG"

if [[ "$STATE" != "done" ]]; then
  echo "[$(date '+%F %T')] · skip · state=$STATE 不是 done · 今天没草稿可发" >> "$LOG"
  exit 0
fi

# 防 stale session(防上次老 session 被反复推)
# 检查 session.article_date / updated_at 是不是今天
TODAY=$(date +%F)
SESSION_DATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    # 优先用 article_date · 兜底 updated_at(取日期前缀)
    d = s.get('article_date')
    if not d:
        u = s.get('updated_at') or ''
        d = u.split('T')[0] if u else ''
    print(d)
except Exception:
    print('')
" 2>/dev/null)

if [[ "$SESSION_DATE" != "$TODAY" ]]; then
  echo "[$(date '+%F %T')] · skip · session.date=$SESSION_DATE 不是 today=$TODAY · 不推老文章" >> "$LOG"
  exit 0
fi

TEXT="🔔 **该群发了** · $(date +%H:%M)
📝 ${TITLE}
🆔 ${MEDIA_ID}

📲 1 步操作:
1. mp.weixin.qq.com → 草稿箱
2. 编辑文末「智辰老师」卡片 → 选公众号「宸的 AI 掘金笔记」
3. 通读 → 群发(订阅号每日 1 次配额)

(订阅号配额:每日 1 次群发 · 错过今天就明天)"

if "$PY" "$PUSH" --text "$TEXT" 2>>"$LOG"; then
  echo "[$(date '+%F %T')] ✓ notify pushed" >> "$LOG"
  exit 0
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ notify push failed · rc=$rc" >> "$LOG"
  exit $rc
fi
