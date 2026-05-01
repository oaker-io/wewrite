#!/usr/bin/env bash
# 装 launchd 定时任务 · 每天 08:30 触发 brief → 推 Discord
# ──
# 主推送:Discord(bot.py 已常驻 · brief.py 自带推送逻辑)
# 降级:notify.sh(从 secrets/keys.env 读 BARK_KEY / NTFY_TOPIC)
# ──
# 用法:./routine/install.sh     # 无参数

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
PLIST_SRC="$SCRIPT_DIR/com.wewrite.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.wewrite.daily.plist"
LABEL="com.wewrite.daily"

mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

# 替换 __REPO_ROOT__ 为实际路径
sed "s|__REPO_ROOT__|$REPO_ROOT|g" "$PLIST_SRC" > "$PLIST_DST"

# 卸载旧版(如存在)· 不存在不报错
launchctl unload -w "$PLIST_DST" 2>/dev/null || true

# 加载
launchctl load -w "$PLIST_DST"

# 验证
if launchctl list | grep -q "$LABEL"; then
  echo "✅ $LABEL 已装 · 每天 08:30 触发"
else
  echo "⚠️  launchctl list 里没看到 $LABEL · 可能 load 失败" >&2
  exit 1
fi

# 检查 secrets
if [ ! -f "$REPO_ROOT/secrets/keys.env" ]; then
  echo "⚠️  $REPO_ROOT/secrets/keys.env 不存在 · brief 会找不到 DISCORD_BOT_TOKEN" >&2
fi

echo ""
echo "下次触发:每天 08:30"
echo "立即测试:bash $SCRIPT_DIR/daily-brief.sh"
echo "看日志:   tail -f $SCRIPT_DIR/logs/daily-brief.\$(date +%F).log"
echo "卸载:     launchctl unload $PLIST_DST && rm $PLIST_DST"
