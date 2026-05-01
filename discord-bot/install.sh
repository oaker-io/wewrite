#!/usr/bin/env bash
# 一键装 Discord bot:venv 装依赖 + launchd daemon + setenv token
# 用法:./discord-bot/install.sh <DISCORD_BOT_TOKEN> [ALLOWED_USER_IDS]
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法:$0 <DISCORD_BOT_TOKEN> [ALLOWED_USER_IDS,逗号分隔]"
  echo ""
  echo "先去 Discord Developer Portal 创建 bot:"
  echo "  1. https://discord.com/developers/applications → New Application"
  echo "  2. Bot 标签 → Add Bot → Reset Token → 复制 token"
  echo "  3. Bot 标签 → Privileged Gateway Intents → **Message Content Intent** 打开"
  echo "  4. OAuth2 → URL Generator → Scope=bot, Permissions=Read Messages/Send Messages/Read Message History"
  echo "  5. 用生成的 URL 把 bot 加到你的 Discord 服务器"
  exit 1
fi

TOKEN="$1"
ALLOWED="${2:-}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
VENV="$REPO_ROOT/venv"
PLIST_SRC="$SCRIPT_DIR/com.wewrite.discord.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.wewrite.discord.plist"

mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

# 安装 discord.py 到 venv
if [ ! -x "$VENV/bin/python3" ]; then
  echo "→ 创建 venv..."
  python3 -m venv "$VENV"
fi

echo "→ 装 discord.py 到 venv..."
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

# 替换占位符写 plist
sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" -e "s|__HOME__|$HOME|g" \
  "$PLIST_SRC" > "$PLIST_DST"

# 注入环境变量到 launchd
launchctl setenv DISCORD_BOT_TOKEN "$TOKEN"
if [ -n "$ALLOWED" ]; then
  launchctl setenv ALLOWED_USER_IDS "$ALLOWED"
fi

# 重新加载
launchctl unload -w "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"

echo ""
echo "✅ WeWrite Discord bot 已安装 + 启动"
echo ""
echo "看状态:"
echo "    tail -f $SCRIPT_DIR/logs/bot.out.log"
echo "    tail -f $SCRIPT_DIR/logs/bot.err.log"
echo ""
echo "前端测试:"
echo "    在 Discord 服务器或 DM 里发 '@WeWrite 今日热点'"
echo ""
echo "卸载:"
echo "    launchctl unload $PLIST_DST"
echo "    rm $PLIST_DST"
echo "    launchctl unsetenv DISCORD_BOT_TOKEN"
