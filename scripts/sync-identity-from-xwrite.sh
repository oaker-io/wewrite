#!/usr/bin/env bash
# sync-identity-from-xwrite.sh · 从 xwrite/identity/ 反向 vendor 到 wewrite/identity/
#
# 跟 sync-to-xwrite.sh 互补:那个是 wewrite 干货系列 → xwrite,这个是 xwrite identity → wewrite。
# 两边都是「不共用 · 单向手动同步」 模式。
#
# 用法:
#   scripts/sync-identity-from-xwrite.sh                  # 默认 diff 模式 · 看变化但不覆盖
#   scripts/sync-identity-from-xwrite.sh --apply          # 真覆盖 wewrite/identity/
#   scripts/sync-identity-from-xwrite.sh --check-staleness  # 输出 N 天未同步(给 brief 用)
#   scripts/sync-identity-from-xwrite.sh --help

set -euo pipefail

XWRITE_IDENTITY="$HOME/xwrite/identity"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEWRITE_IDENTITY="$REPO_ROOT/identity"
LAST_SYNC="$WEWRITE_IDENTITY/.last-synced"

# 同步清单(只 vendor 这些 · assets 不 vendor 因为体积大且 wewrite 用不到)
SYNC_FILES=(
  "identity.md"
  "profile.yaml"
  "audiences.md"
  "voice/catchphrases.md"
  "voice/forbidden.md"
)

MODE="diff"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)            MODE="apply"; shift ;;
    --check-staleness)  MODE="staleness"; shift ;;
    --help|-h)
      sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# *//'
      exit 0 ;;
    *)
      echo "❌ 未知参数: $1" >&2
      echo "用法: $0 [--apply | --check-staleness]" >&2
      exit 1 ;;
  esac
done

# === --check-staleness 模式 ===
if [[ "$MODE" == "staleness" ]]; then
  if [[ ! -f "$LAST_SYNC" ]]; then
    echo "999"  # 从未同步过
    exit 0
  fi
  last=$(cat "$LAST_SYNC")
  # 用 python 算天数差(BSD date 处理 ISO 8601 麻烦)
  days=$(python3 -c "
from datetime import datetime, timezone
last = datetime.fromisoformat('$last'.replace('Z', '+00:00'))
now = datetime.now(timezone.utc)
print((now - last).days)
" 2>/dev/null || echo "999")
  echo "$days"
  exit 0
fi

# 检查 xwrite identity 存在
if [[ ! -d "$XWRITE_IDENTITY" ]]; then
  echo "❌ xwrite identity 目录不存在: $XWRITE_IDENTITY" >&2
  echo "   预期路径:~/xwrite/identity/" >&2
  exit 1
fi

# === --apply 模式:真同步 ===
if [[ "$MODE" == "apply" ]]; then
  echo "🔄 同步 xwrite/identity/ → wewrite/identity/"
  echo ''
  mkdir -p "$WEWRITE_IDENTITY/voice"
  for f in "${SYNC_FILES[@]}"; do
    src="$XWRITE_IDENTITY/$f"
    dst="$WEWRITE_IDENTITY/$f"
    if [[ ! -f "$src" ]]; then
      echo "  ⚠️  跳过(源不存在):$f"
      continue
    fi
    # 如果目标已存在且内容相同,标 unchanged
    if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
      echo "  · $f (unchanged)"
    else
      cp "$src" "$dst"
      echo "  ✓ $f"
    fi
  done
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAST_SYNC"
  echo ''
  echo "✓ 已同步 · last-synced 更新为 $(cat "$LAST_SYNC")"
  exit 0
fi

# === 默认模式:diff ===
echo "# identity sync 预览(xwrite → wewrite · 当前是 diff 模式)"
echo ''
if [[ -f "$LAST_SYNC" ]]; then
  echo "上次同步:$(cat "$LAST_SYNC")"
else
  echo "上次同步:(未同步过)"
fi
echo ''

CHANGED=false
for f in "${SYNC_FILES[@]}"; do
  src="$XWRITE_IDENTITY/$f"
  dst="$WEWRITE_IDENTITY/$f"
  if [[ ! -f "$src" ]]; then
    echo "## $f"
    echo "⚠️  xwrite 端不存在 · 跳过"
    echo ''
    continue
  fi
  if [[ ! -f "$dst" ]]; then
    echo "## $f"
    echo "🆕 wewrite 端不存在 · --apply 时会新建"
    echo ''
    CHANGED=true
    continue
  fi
  if cmp -s "$src" "$dst"; then
    echo "## $f"
    echo "✓ 无变化"
    echo ''
  else
    echo "## $f"
    echo "📝 有变化:"
    echo '```diff'
    diff -u "$dst" "$src" | head -40 || true
    echo '```'
    echo ''
    CHANGED=true
  fi
done

if [[ "$CHANGED" == "true" ]]; then
  echo '---'
  echo "⚠️  有改动 · 跑 \`scripts/sync-identity-from-xwrite.sh --apply\` 真同步"
else
  echo '---'
  echo "✓ wewrite/identity/ 已与 xwrite/identity/ 一致 · 无需 --apply"
fi
