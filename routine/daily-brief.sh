#!/usr/bin/env bash
# 每日 08:30 自动触发 brief · 推 Discord 等用户手机审
# ──
# 流程:fetch hotspots → AI 白名单过滤 → Top N 推 Discord → 用户回 1/2/3
# 不自动写文 / 不自动生图 / 不自动发布 · 那 3 步必须用户手动驱动(Discord 自然语言)
# ──
# 失败降级:Discord 推送失败 → notify.sh 本地提醒 Mac(推 Bark / ntfy / osascript)

set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_ROOT"

PY="${PY:-$REPO_ROOT/venv/bin/python3}"
[ -x "$PY" ] || PY="python3"

# 加载 secrets(DISCORD_BOT_TOKEN + ALLOWED_USER_IDS 等)
if [ -f "$REPO_ROOT/secrets/keys.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$REPO_ROOT/secrets/keys.env"
  set +a
fi

LOG="$SCRIPT_DIR/logs/daily-brief.$(date +%Y-%m-%d).log"
mkdir -p "$SCRIPT_DIR/logs"

echo "[$(date '+%F %T')] → brief.py start" >> "$LOG"

if "$PY" scripts/workflow/brief.py >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ brief done" >> "$LOG"
  exit 0
fi

# 失败 · 本地 Mac 兜底提醒
echo "[$(date '+%F %T')] ✗ brief failed · fallback to notify.sh" >> "$LOG"
"$SCRIPT_DIR/notify.sh" \
  "WeWrite 早报失败" \
  "brief.py 异常退出 · 看 $LOG" \
  "" || true
exit 1
