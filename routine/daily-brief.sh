#!/usr/bin/env bash
# 每日早报:推送"今日可做什么"的提醒到 iPhone
# - 抓一轮热点摘要(10 条,简短)
# - push 给手机,用户看到后在 Claude Code 里说「/wewrite」触发完整流程
# 风险控制:**不**自动跑 Step 1-8(避免半夜消耗 Poe 额度 + 生成废稿)

set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_ROOT"

PY="${PY:-$REPO_ROOT/venv/bin/python3}"
[ -x "$PY" ] || PY="python3"

# 1. 抓热点(20 条取 5 条最热的)
HOT_JSON="$(mktemp)"
trap "rm -f '$HOT_JSON'" EXIT

"$PY" scripts/fetch_hotspots.py --limit 20 > "$HOT_JSON" 2>/dev/null || {
  "$SCRIPT_DIR/notify.sh" "WeWrite 早报失败" "热点抓取失败,请到 Mac 手动检查" ""
  exit 1
}

# 2. 抽 top 5 标题拼成推送正文
TOP5="$("$PY" - <<'PY' "$HOT_JSON"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
items = data.get("items", [])[:5]
for i, it in enumerate(items, 1):
    print(f"{i}. {it['title']} · {it['source']}")
PY
)"

# 3. 昨日/近期是否有未发表的草稿
LAST_ARTICLE="$(ls -t output/*.md 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo '-')"

# 4. 推送
BODY="📰 今日 Top 5 热点
${TOP5}

📝 最近草稿:${LAST_ARTICLE}

🚀 想写的话,在 Claude Code 里说「/wewrite 写今天」"
"$SCRIPT_DIR/notify.sh" "WeWrite 早报 · $(date '+%m-%d %H:%M')" "$BODY" ""
