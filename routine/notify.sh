#!/usr/bin/env bash
# 统一推送封装 · 按优先级:Bark(国内 iOS)→ ntfy.sh(国际)→ macOS 原生
# 用法:notify.sh "标题" "内容 · 支持多行\\n" [URL]
# 配置(二选一):
#   export BARK_KEY=xxxxxxxxxx          # https://apps.apple.com/app/bark/id1403753865
#   export NTFY_TOPIC=wewrite-myname    # https://ntfy.sh

set -euo pipefail
TITLE="${1:-WeWrite}"
BODY="${2:-(空消息)}"
URL="${3:-}"

# URL encode for Bark
urlencode() { python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$1"; }

if [ -n "${BARK_KEY:-}" ]; then
  # Bark: https://api.day.app/<key>/<title>/<body>?url=<url>&group=wewrite
  endpoint="https://api.day.app/${BARK_KEY}/$(urlencode "$TITLE")/$(urlencode "$BODY")"
  if [ -n "$URL" ]; then
    endpoint="${endpoint}?url=$(urlencode "$URL")&group=wewrite"
  else
    endpoint="${endpoint}?group=wewrite"
  fi
  curl -s -o /dev/null "$endpoint" && echo "[bark] pushed" && exit 0
fi

if [ -n "${NTFY_TOPIC:-}" ]; then
  if [ -n "$URL" ]; then
    curl -s -H "Title: $TITLE" -H "Click: $URL" -d "$BODY" "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null
  else
    curl -s -H "Title: $TITLE" -d "$BODY" "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null
  fi
  echo "[ntfy] pushed"
  exit 0
fi

# Fallback:macOS 本地弹窗(仅本机可见,适合测试)
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$BODY\" with title \"$TITLE\""
  echo "[osascript] local notified"
  exit 0
fi

echo "⚠️  No notifier configured. Set BARK_KEY or NTFY_TOPIC." >&2
exit 1
