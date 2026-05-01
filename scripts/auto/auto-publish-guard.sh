#!/usr/bin/env bash
# auto-publish-guard.sh · 21:30 launchd 触发 · 检查今天没发干货 → 推 Discord 警报
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "publish_guard"
load_keys

LOG="$LOG_DIR/auto-publish-guard.$(date +%F).log"
echo "[$(date '+%F %T')] → publish_guard" >> "$LOG"

# 看 _state.is_today_published(对应 mp.weixin 草稿已生成 + state=done + media_id 非空)
TODAY=$(date +%F)
PUBLISHED=$("$PY" -c "
import sys; sys.path.insert(0, 'scripts/workflow')
import _state
print('1' if _state.is_today_published('$TODAY') else '0')
" 2>/dev/null)

# 兜底:扫 output/ 看今天是否有 .md(说明文章至少写出了)
HAS_MD=$(ls "$REPO_ROOT/output/$TODAY"-*.md 2>/dev/null | head -1 || echo "")

if [[ "$PUBLISHED" == "1" ]]; then
  echo "[$(date '+%F %T')] ✓ 今日 publish 已完成 · 静默退出" >> "$LOG"
  exit 0
fi

if [[ -n "$HAS_MD" ]]; then
  # 写了但没推 · 推 Discord 提醒手动 publish
  MSG="⚠️ **publish-guard · 今天有 md 但没推草稿**

📝 已写:$(basename "$HAS_MD")
🚧 状态:state ≠ done · 没 media_id · 没推 mp.weixin

📋 你需要:
1. 检查 \`output/session.yaml\` state · 看卡哪步
2. 手动跑 \`bash scripts/auto/auto-publish.sh\` 重推
3. 或重 reset:\`venv/bin/python3 -c \"import sys;sys.path.insert(0,'scripts/workflow');import _state;_state.reset()\"\`

距明天 7:00 auto_pick 还有 ~9 小时 · 不补救会断更 1 天。"
  "$PY" "$PUSH" --text "$MSG" >> "$LOG" 2>&1 || true
  echo "[$(date '+%F %T')] ⚠ 写了但没推 · 已 push 警报" >> "$LOG"
  exit 0
fi

# 完全没写 · 红色警报
MSG="🔴 **publish-guard · 今天 0 发(MD 都没写)**

🚨 状态:0 markdown / 0 草稿 / 0 publish
📋 根因排查:
- auto-pick.sh 没跑成?(看 routine/logs/auto-pick.$(date +%F).log)
- auto-write.sh 没跑成?(看 routine/logs/auto-write.$(date +%F).log)
- session.state 卡住?(\`cat output/session.yaml | head\`)

🛠 立即补救(可在 23:00 前还能赶上):
1. 重 reset:\`venv/bin/python3 -c \"import sys;sys.path.insert(0,'scripts/workflow');import _state;_state.reset()\"\`
2. 跑全链:\`bash scripts/auto/auto-pick.sh && bash scripts/auto/auto-write.sh && bash scripts/auto/auto-publish.sh\`

明天 03:00 fetch_kol → 07:00 pick 自动续 · 但今天断更 1 天。"
"$PY" "$PUSH" --text "$MSG" >> "$LOG" 2>&1 || true
echo "[$(date '+%F %T')] 🔴 0 发警报已 push" >> "$LOG"
exit 0
