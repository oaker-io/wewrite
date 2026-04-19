#!/usr/bin/env bash
# 安装 launchd 定时任务:每天 08:30 推送 WeWrite 早报
# 用法:./routine/install.sh [BARK_KEY | @ntfy NTFY_TOPIC]
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
PLIST_SRC="$SCRIPT_DIR/com.wewrite.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.wewrite.daily.plist"
LABEL="com.wewrite.daily"

mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

# 替换 __REPO_ROOT__ 为实际路径,写到目标位置
sed "s|__REPO_ROOT__|$REPO_ROOT|g" "$PLIST_SRC" > "$PLIST_DST"

# 卸载旧版(如存在)
launchctl unload -w "$PLIST_DST" 2>/dev/null || true

# 加载
launchctl load -w "$PLIST_DST"

# 设置推送环境(可选参数)
if [ $# -gt 0 ]; then
  if [[ "$1" == "@ntfy" && $# -ge 2 ]]; then
    launchctl setenv NTFY_TOPIC "$2"
    echo "✓ NTFY_TOPIC set to '$2'"
  else
    launchctl setenv BARK_KEY "$1"
    echo "✓ BARK_KEY configured (first 6 chars: ${1:0:6}...)"
  fi
fi

echo ""
echo "✅ WeWrite daily routine installed"
echo ""
echo "下次触发:每天 08:30"
echo "立即测试(不等到明天):"
echo "    bash $SCRIPT_DIR/daily-brief.sh"
echo ""
echo "查看日志:"
echo "    tail -f $SCRIPT_DIR/logs/daily-brief.out.log"
echo ""
echo "卸载:"
echo "    launchctl unload $PLIST_DST"
echo "    rm $PLIST_DST"
