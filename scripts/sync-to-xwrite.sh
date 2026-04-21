#!/usr/bin/env bash
# sync-to-xwrite.sh · 生成 wewrite → xwrite 干货系列同步报告
#
# **不真改 xwrite 任何文件** · 因为平台转化(长文 vs thread)需要人工判断。
# 脚本只做两件事:
#   1. 列出 wewrite 端干货相关文件最近 N 天的 commit
#   2. 输出一份 markdown 报告给 xwrite 维护者(或 xwrite 那边的 Claude session)review
#
# 用法:
#   scripts/sync-to-xwrite.sh                        # 默认 7 天窗口
#   scripts/sync-to-xwrite.sh --since "2026-04-19"   # 自定义起点
#   scripts/sync-to-xwrite.sh --diff <file>          # 只看某个文件 wewrite vs xwrite 的差异
#   scripts/sync-to-xwrite.sh --help                 # 帮助
#
# 输出:
#   - stdout:markdown 报告
#   - /tmp/xwrite-tutorial-sync-<日期>.md:同样的报告(给 xwrite 那边贴)

set -euo pipefail

# === 干货相关文件清单(wewrite 端 + 对应的 xwrite 端) ===
# 加新文件时改这里 · 用 "|" 分隔 wewrite 路径和 xwrite 对应(空字符串 "" = 无对应)
TUTORIAL_PAIRS=(
  "personas/tutorial-instructor.yaml|~/xwrite/personas/tutorial-instructor.yaml"
  "references/tutorial-frameworks.md|~/xwrite/references/frameworks/tutorial-thread.md"
  "references/visuals/styles/mockup-macos-app.md|"
  "references/visuals/styles/mockup-ios-mobile.md|"
  "references/visuals/styles/mockup-terminal.md|"
  "references/visuals/styles/mockup-code-editor.md|"
  "scripts/workflow/write.py|"
  "scripts/workflow/_idea_bank.py|"
  "scripts/workflow/idea.py|"
  "scripts/fetch_changelog.py|"
  "discord-bot/bot.py|"
)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XWRITE_ROOT="$(cd ~ && pwd)/xwrite"

SINCE="7 days ago"
DIFF_FILE=""

# === 参数解析 ===
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)
      SINCE="$2"; shift 2 ;;
    --diff)
      DIFF_FILE="$2"; shift 2 ;;
    --help|-h)
      sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# *//'
      exit 0 ;;
    *)
      echo "❌ 未知参数: $1" >&2
      echo "用法: $0 [--since DATE] [--diff FILE]" >&2
      exit 1 ;;
  esac
done

cd "$REPO_ROOT"

# === --diff 模式:对比单文件 wewrite vs xwrite ===
if [[ -n "$DIFF_FILE" ]]; then
  WEWRITE_PATH="$REPO_ROOT/$DIFF_FILE"
  if [[ ! -f "$WEWRITE_PATH" ]]; then
    echo "❌ wewrite 端文件不存在: $DIFF_FILE" >&2
    exit 1
  fi
  # 找 xwrite 对应
  XWRITE_PATH=""
  for pair in "${TUTORIAL_PAIRS[@]}"; do
    src="${pair%%|*}"
    dst="${pair#*|}"
    if [[ "$src" == "$DIFF_FILE" ]]; then
      XWRITE_PATH="${dst/#\~/$HOME}"
      break
    fi
  done
  if [[ -z "$XWRITE_PATH" ]]; then
    echo "ℹ️  $DIFF_FILE 在 TUTORIAL_PAIRS 里无 xwrite 对应(wewrite 独有)" >&2
    exit 0
  fi
  if [[ ! -f "$XWRITE_PATH" ]]; then
    echo "ℹ️  xwrite 端对应文件不存在: $XWRITE_PATH(可能还没 vendor)" >&2
    exit 0
  fi
  echo "## diff: $DIFF_FILE  vs  $XWRITE_PATH"
  echo ''
  diff -u "$WEWRITE_PATH" "$XWRITE_PATH" || true
  exit 0
fi

# === 默认模式:生成同步报告 ===
TODAY="$(date +%Y-%m-%d)"
REPORT="/tmp/xwrite-tutorial-sync-${TODAY}.md"

# 提取 wewrite 端文件列表
WEWRITE_FILES=()
for pair in "${TUTORIAL_PAIRS[@]}"; do
  WEWRITE_FILES+=("${pair%%|*}")
done

# 写报告(同时落 /tmp 和 stdout)
{
  echo "# wewrite → xwrite 干货系列同步报告 · $TODAY"
  echo ''
  echo "> 时间窗:since \`$SINCE\`"
  echo "> 用法:把这份报告贴给 xwrite 那边的 Claude Code session,问「这次 wewrite 改了 XYZ,xwrite 要不要跟?」"
  echo ''
  echo '---'
  echo ''
  echo '## 1. wewrite 端最近改动(干货相关文件)'
  echo ''

  HAS_CHANGES=false
  for f in "${WEWRITE_FILES[@]}"; do
    # 处理通配符(eg mockup-*.md)
    matches=()
    while IFS= read -r -d '' match; do
      matches+=("$match")
    done < <(find . -path "./$f" -print0 2>/dev/null || true)
    # 没匹配 · 直接试原路径
    if [[ ${#matches[@]} -eq 0 ]] && [[ -f "$f" ]]; then
      matches=("$f")
    fi

    for actual_file in "${matches[@]}"; do
      actual_file="${actual_file#./}"
      log=$(git log --since="$SINCE" --pretty=format:'%h · %ad · %s' --date=short -- "$actual_file" 2>/dev/null | head -5)
      if [[ -n "$log" ]]; then
        HAS_CHANGES=true
        # 找 xwrite 对应
        xwrite_corresponding=""
        for pair in "${TUTORIAL_PAIRS[@]}"; do
          src="${pair%%|*}"
          dst="${pair#*|}"
          if [[ "$src" == "$f" ]]; then
            xwrite_corresponding="$dst"
            break
          fi
        done

        echo "### \`$actual_file\`"
        echo ''
        echo "**最近 commits**(≤ 5):"
        echo '```'
        echo "$log"
        echo '```'
        # diff stat
        oldest_commit=$(git log --since="$SINCE" --pretty=format:'%h' -- "$actual_file" | tail -1)
        if [[ -n "$oldest_commit" ]]; then
          stat=$(git diff --stat "${oldest_commit}~..HEAD" -- "$actual_file" 2>/dev/null | tail -1)
          [[ -n "$stat" ]] && echo "**diff 统计**:\`$stat\`"
          echo ''
        fi
        # xwrite 对应
        if [[ -n "$xwrite_corresponding" ]]; then
          echo "**xwrite 对应**:\`$xwrite_corresponding\`"
          # 检查文件存不存在
          actual_xwrite="${xwrite_corresponding/#\~/$HOME}"
          if [[ -f "$actual_xwrite" ]]; then
            echo "→ 状态:**已 vendor** · review 是否需要同步(注意平台转化:长文 vs thread)"
          else
            echo "→ 状态:**未 vendor** · 考虑是否要在 xwrite 那边新建对应文件"
          fi
        else
          echo "**xwrite 对应**:无(wewrite 独有 · 跳过)"
        fi
        echo ''
        echo '---'
        echo ''
      fi
    done
  done

  if [[ "$HAS_CHANGES" == "false" ]]; then
    echo "_时间窗 \`$SINCE\` 内,干货相关文件没有 commit 改动 · 无需同步_"
    echo ''
  fi

  echo ''
  echo '## 2. 干货相关文件 全量清单(供 review)'
  echo ''
  echo "| wewrite | xwrite 对应 | 状态 |"
  echo "|---|---|---|"
  for pair in "${TUTORIAL_PAIRS[@]}"; do
    src="${pair%%|*}"
    dst="${pair#*|}"
    actual_dst="${dst/#\~/$HOME}"
    if [[ -z "$dst" ]]; then
      echo "| ~~\`$src\`~~ | × 无 | wewrite 独有(不适配 X 平台) |"
    elif [[ -f "$actual_dst" ]]; then
      echo "| \`$src\` | \`$dst\` | ✅ vendor 中 |"
    else
      echo "| \`$src\` | \`$dst\` | ⚠️ 未 vendor |"
    fi
  done
  echo ''

  echo ''
  echo '## 3. 下一步建议'
  echo ''
  echo '到 \`~/xwrite\` 那边 chat 一个新 Claude Code session(或 cd 进 xwrite 目录跑 \`claude\`),贴这份报告,告诉那边的 Claude:'
  echo ''
  echo '```'
  echo 'wewrite 那边最近改了干货系列相关文件(见同步报告)。请你 review 改动,'
  echo '并按 X 平台节奏(thread/micro · 不是长文)适配性同步到对应文件。'
  echo '不要直接 cp · 注意平台转化。改完跟我汇报改了什么。'
  echo '```'
  echo ''
  echo '保留原则:'
  echo '- T1-T5 编号在两边保持一致(同一思路 · 不同节奏)'
  echo '- persona 字段名一致(name / description / voice_density 等),数值可不同'
  echo '- mockup style / idea_bank / bot intent 等是 wewrite 独有,**不要**移植到 xwrite'
  echo ''
  echo '---'
  echo "_报告生成于:$(date '+%Y-%m-%d %H:%M:%S')_"
  echo "_脚本:\`scripts/sync-to-xwrite.sh\`_"
} | tee "$REPORT"

echo ''
echo "📋 报告已存到:$REPORT"
echo "✓ 不动 xwrite 任何文件 · 只输出报告"
