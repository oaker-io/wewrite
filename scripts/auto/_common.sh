#!/usr/bin/env bash
# auto-* shell 包装层公用 helper · source 即用 · 不直接执行
#
# 提供:
#   REPO_ROOT  · 仓库根
#   PY         · python3 路径(优先 venv)
#   PUSH       · discord-bot/push.py 路径
#   STEP_LOG   · 当天分 step 的 log 文件
#   load_keys  · 加载 secrets/keys.env 到 env(若存在)
#   step_check_enabled <step_name> · 读 config/auto-schedule.yaml#steps · false 时 exit 0
#   notify_failure <step_name> <error_msg>  · push Discord 失败通知

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$REPO_ROOT"

PY="${PY:-$REPO_ROOT/venv/bin/python3}"
[ -x "$PY" ] || PY="python3"

PUSH="$REPO_ROOT/discord-bot/push.py"

LOG_DIR="$REPO_ROOT/routine/logs"
mkdir -p "$LOG_DIR"

load_keys() {
  if [ -f "$REPO_ROOT/secrets/keys.env" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$REPO_ROOT/secrets/keys.env"
    set +a
  fi
}

step_check_enabled() {
  local step="$1"
  local cfg="$REPO_ROOT/config/auto-schedule.yaml"
  [ -f "$cfg" ] || return 0  # 没 config · 默认开
  # 用 python 解析(避免装 yq)
  local enabled
  enabled=$("$PY" -c "
import sys, yaml
try:
    cfg = yaml.safe_load(open('$cfg', encoding='utf-8')) or {}
    if not cfg.get('enabled', True):
        print('off-global')
        sys.exit(0)
    if not (cfg.get('steps') or {}).get('$step', True):
        print('off-step')
        sys.exit(0)
    print('on')
except Exception as e:
    print(f'err:{e}', file=sys.stderr)
    print('on')  # 解析失败 · 默认开 · 别卡死
" 2>/dev/null) || enabled="on"
  if [[ "$enabled" == "off-global" ]]; then
    echo "[auto] config.enabled=false · skip $step" >&2
    exit 0
  fi
  if [[ "$enabled" == "off-step" ]]; then
    echo "[auto] steps.$step=false · skip" >&2
    exit 0
  fi
}

notify_failure() {
  local step="$1"
  local msg="$2"
  load_keys
  local text
  text="❌ **auto_${step} 失败**
$(date '+%F %T')

$msg

详见日志:routine/logs/auto-${step}.$(date +%F).log"
  "$PY" "$PUSH" --text "$text" 2>/dev/null || true
}

# launchd 子进程 PATH 跟登录 shell 不一致 · claude / 其他 binary 可能找不到
# 调用方在 step_check_enabled 后加这一行 · 第一时间发现 PATH 问题
# 用法: require_binary claude
require_binary() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    notify_failure "$(basename "${BASH_SOURCE[1]:-unknown}" .sh)" \
      "binary '$bin' 不在 PATH(PATH=$PATH)· 修 plist 的 EnvironmentVariables/PATH"
    echo "[auto] ❌ require_binary $bin 失败 · PATH=$PATH" >&2
    exit 1
  fi
}
