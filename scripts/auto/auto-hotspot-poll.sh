#!/usr/bin/env bash
# auto-hotspot-poll.sh · 半小时 launchd 触发 · 拉 news_hub 高分 hotspot · LLM 改写入 idea_bank
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "hotspot_poll"
load_keys

LOG="$LOG_DIR/auto-hotspot-poll.$(date +%F).log"
echo "[$(date '+%F %T')] → hotspot_to_idea" >> "$LOG"

H2I="$REPO_ROOT/scripts/workflow/hotspot_to_idea.py"
if [ ! -f "$H2I" ]; then
  echo "[$(date '+%F %T')] · skip · $H2I 不存在" >> "$LOG"
  exit 0
fi

if "$PY" "$H2I" --limit 5 >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ hotspot_poll done" >> "$LOG"
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ hotspot_poll exit=$rc" >> "$LOG"
  # 半小时一次 · 失败不 push 避免刷屏 · 只打日志
fi
