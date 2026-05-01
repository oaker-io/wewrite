#!/usr/bin/env bash
# install-auto.sh · 装 7 个全自动 launchd plist
#
# 8 个时间点:
#   03:00  auto-fetch-kol 抓 KOL 公众号 RSS 入 idea_bank(P1 · 凌晨错峰)
#   07:00  auto-pick     选今日 idea
#   08:00  auto-write    写文章
#   10:00  auto-images   配图(case-realistic 套件)
#   11:00  auto-review   LLM 自审
#   12:00  auto-publish  推草稿箱
#   19:30  auto-notify   提醒群发
#   Sun 02:00  auto-stats  回填指标
#
# 用法:
#   ./routine/install-auto.sh           # 装全部 7 个
#   ./routine/install-auto.sh --list    # 看哪些已装
#   ./routine/install-auto.sh --uninstall  # 全卸
#   ./routine/install-auto.sh pick      # 只装 pick(逐个调试用)

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

ALL_NAMES=("fetch-kol" "sync-xhs" "discover-kol" "hotspot-poll" "pick" "write" "images" "review" "publish" "notify" "comment-kickoff" "publish-guard" "daily-report" "stats")

mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

list_installed() {
  echo "已装 launchd 任务(grep com.wewrite.auto-):"
  launchctl list | grep -E "^[^[:space:]]+[[:space:]]+.*com.wewrite.auto-" || echo "  (无)"
}

uninstall_one() {
  local name="$1"
  local label="com.wewrite.auto-$name"
  local dst="$HOME/Library/LaunchAgents/$label.plist"
  if [[ -f "$dst" ]]; then
    launchctl unload -w "$dst" 2>/dev/null || true
    rm -f "$dst"
    echo "  ✓ uninstalled $label"
  else
    echo "  · $label 未装"
  fi
}

install_one() {
  local name="$1"
  local label="com.wewrite.auto-$name"
  local src="$SCRIPT_DIR/$label.plist"
  local dst="$HOME/Library/LaunchAgents/$label.plist"

  if [[ ! -f "$src" ]]; then
    echo "❌ 找不到 $src" >&2
    return 0  # 不阻断整个 install loop
  fi

  # 替换 __REPO_ROOT__
  sed "s|__REPO_ROOT__|$REPO_ROOT|g" "$src" > "$dst"

  # 卸再装(若已装会先卸)
  launchctl unload -w "$dst" 2>/dev/null || true
  launchctl load -w "$dst" 2>/dev/null || true
  # 等 macOS 注册一下(launchctl list 偶尔 race · 0.3s 缓冲)
  sleep 0.3
  if launchctl list 2>/dev/null | grep -qE "(^|\s)$label(\s|$)"; then
    echo "  ✓ $label 已装"
  else
    echo "  ⚠ $label 装了但 list 没 match · 第二天 02:00 再 launchctl list 验证 · 不阻断 install" >&2
  fi
  return 0
}

case "${1:-}" in
  --list|-l)
    list_installed
    exit 0
    ;;
  --uninstall|-u)
    echo "卸载全部 7 个 auto-* launchd 任务..."
    for n in "${ALL_NAMES[@]}"; do uninstall_one "$n"; done
    echo ""
    list_installed
    exit 0
    ;;
  --help|-h)
    head -25 "${BASH_SOURCE[0]}" | sed 's/^# *//'
    exit 0
    ;;
  "")
    # 默认 · 装全部
    echo "装全部 ${#ALL_NAMES[@]} 个 auto-* launchd 任务..."
    for n in "${ALL_NAMES[@]}"; do install_one "$n"; done
    ;;
  *)
    # 装某一个(传 name eg pick / write)
    install_one "$1"
    ;;
esac

# 检查 secrets
if [ ! -f "$REPO_ROOT/secrets/keys.env" ]; then
  echo ""
  echo "⚠️  $REPO_ROOT/secrets/keys.env 不存在 · auto-* 找不到 DISCORD_BOT_TOKEN" >&2
fi

# 检查 config
if [ ! -f "$REPO_ROOT/config/auto-schedule.yaml" ]; then
  echo ""
  echo "⚠️  $REPO_ROOT/config/auto-schedule.yaml 不存在 · auto_pick 会失败" >&2
fi

echo ""
echo "时间表:"
echo "  03:00  auto-fetch-kol 抓 KOL 公众号 RSS 入 idea_bank(凌晨错峰)"
echo "  03:05  auto-sync-xhs  兜底从 xhswrite 拉 publish event 入 idea_bank"
echo "  03:30  auto-discover-kol 选 5 个 AI KOL 候选 · 用户审入 wewe-rss"
echo "  04-23 半小时 auto-hotspot-poll 拉 news_hub + LLM 改写入 idea_bank"
echo "  07:00  auto-pick     选今日 idea(读 config/auto-schedule.yaml)"
echo "  08:00  auto-write    claude -p 写 1 篇文(5-15 分钟)"
echo "  10:00  auto-images   生 5 张图(case 类走拟真套件)"
echo "  11:00  auto-review   LLM 自审 5+1 维度"
echo "  12:00  auto-publish  推 mp.weixin.qq.com 草稿箱 + push 通知"
echo "  19:30  auto-notify          提醒去手动 1 tap 群发(订阅号每日 1 次)"
echo "  20:00  auto-comment-kickoff  推 Discord 候选置顶话术 + 自动回复速查"
echo "  21:30  auto-publish-guard    没发干货 → Discord 警报 + 补救线索"
echo "  22:00  auto-daily-report     Discord 日报(爬了啥/发了啥/明日计划)"
echo "  Sun 02:00  auto-stats        回填本周 fan_count / read_count"
echo ""
echo "停某一步:编辑 config/auto-schedule.yaml#steps · 把对应 step 设 false"
echo "全停:    edit config/auto-schedule.yaml#enabled: false"
echo "看日志:  tail -f routine/logs/auto-*.log"
echo "立即测试:scripts/auto/auto-pick.sh"
