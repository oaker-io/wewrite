#!/usr/bin/env bash
# auto-review.sh · 11:00 launchd 触发 · 调 auto_review.py 自审
# 不达标(exit 2)→ 触发重写一次(只写不重新生图 · 因为图通常 OK)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "review"
load_keys

LOG="$LOG_DIR/auto-review.$(date +%F).log"
echo "[$(date '+%F %T')] → auto_review.py" >> "$LOG"

# 读 max_retries
MAX_RETRIES=$("$PY" -c "
import yaml
try:
    cfg = yaml.safe_load(open('config/auto-schedule.yaml', encoding='utf-8')) or {}
    print(int((cfg.get('review') or {}).get('max_retries', 1)))
except Exception:
    print(1)
" 2>/dev/null)
MAX_RETRIES="${MAX_RETRIES:-1}"

# 第一次 review
if "$PY" scripts/workflow/auto_review.py >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ review pass · 一次过" >> "$LOG"
  exit 0
fi

rc=$?
if [[ $rc -ne 2 ]]; then
  # 非 retry 信号 · 是真错误
  echo "[$(date '+%F %T')] ✗ review hard error exit=$rc" >> "$LOG"
  notify_failure "review" "auto_review.py 退出 $rc(非 retry · 是错误)"
  exit $rc
fi

# 进入 retry · 当前实现 = 不重写,只 push 通知人工 review
# (重写需要保留旧 md / 调 write.py 重生 / 处理 images 一致性 · 第一版先简单 push 让人审)
if [[ $MAX_RETRIES -ge 1 ]]; then
  echo "[$(date '+%F %T')] ⚠ 不达标 · push 人工 review(后续可加自动重写)" >> "$LOG"
  notify_failure "review" "auto_review 不达标 · 人工 review · 看上一条 push 的评分明细"
fi

# 不达标但不阻断 publish · 让用户决定要不要继续
# (因为大多数情况下 word_count / catchphrase 这种小不达标 · 直接发也行)
echo "[$(date '+%F %T')] · review 不达标但放行 publish · 人工 review" >> "$LOG"
exit 0
