#!/usr/bin/env bash
# 安全轮换 Discord bot token · token 不回显 / 不进 shell history / 不打印到终端
# 用法:./discord-bot/rotate-token.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$(pwd)"

# 立即关闭 shell history,防止 token 误入
set +o history 2>/dev/null || true

echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│  Discord Bot Token 轮换 · 3 步                                   │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo "│  1. 浏览器打开:                                                  │"
echo "│     https://discord.com/developers/applications                  │"
echo "│  2. 选 WeWrite application → Bot → 点 'Reset Token'              │"
echo "│  3. 复制新 token,回到这个终端粘贴                               │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""
echo -n "粘贴新 token(输入不会回显,按 Enter 确认):"
IFS= read -rs NEW_TOKEN
echo ""

if [ -z "$NEW_TOKEN" ]; then
  echo "❌ 空 token,取消。"
  exit 1
fi
if [[ ! "$NEW_TOKEN" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "❌ token 字符不合法(只应含字母数字/点/下划线/横线),请重试。"
  unset NEW_TOKEN
  exit 1
fi

export NEW_TOKEN
# 写入 secrets/keys.env(不打印 token)
python3 <<'PY'
import re, os
from pathlib import Path
kf = Path("secrets/keys.env")
s = kf.read_text()
token = os.environ["NEW_TOKEN"]
if not re.search(r'^DISCORD_BOT_TOKEN=', s, flags=re.M):
    s = s.rstrip() + f'\nDISCORD_BOT_TOKEN="{token}"\n'
else:
    s = re.sub(r'^DISCORD_BOT_TOKEN=.*$', f'DISCORD_BOT_TOKEN="{token}"', s, flags=re.M)
kf.write_text(s)
os.chmod(kf, 0o600)
print(f"✓ secrets/keys.env updated ({len(token)} chars · chmod 600)")
PY

# 更新 launchd 环境变量
launchctl setenv DISCORD_BOT_TOKEN "$NEW_TOKEN"
echo "✓ launchctl setenv DISCORD_BOT_TOKEN 完成"

# 立即清内存变量
unset NEW_TOKEN

# 先用新 token 验证一下 Discord API(用 python 读 env 再请求,避免 shell 里带 token)
python3 <<'PY' 2>&1
import os, subprocess, requests
r = subprocess.run(["launchctl", "getenv", "DISCORD_BOT_TOKEN"], capture_output=True, text=True)
token = r.stdout.strip()
resp = requests.get("https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {token}"}, timeout=15)
if resp.status_code == 200:
    me = resp.json()
    print(f"✓ 新 token 有效 · bot identity: {me['username']}#{me.get('discriminator','')} (id={me['id']})")
else:
    print(f"❌ 新 token 验证失败 {resp.status_code}: {resp.text[:200]}")
    print("  这一般意味着你粘了旧 token 或 token 不完整。请重跑本脚本。")
    exit(1)
PY

# 重启 bot daemon
launchctl unload "$HOME/Library/LaunchAgents/com.wewrite.discord.plist" 2>/dev/null || true
sleep 1
launchctl load -w "$HOME/Library/LaunchAgents/com.wewrite.discord.plist"
echo "✓ bot daemon 已重启"

# 等 gateway 连接
echo "  等 8 秒 bot 重新连接 gateway..."
sleep 8

# 看启动 log
if tail -30 discord-bot/logs/bot.out.log | tail -4 | grep -q "Logged in as"; then
  echo "✓ bot 新 token 登录成功:"
  tail -4 discord-bot/logs/bot.out.log | sed 's/^/    /'
else
  echo "⚠️  log 里没看到 'Logged in',可能还在连接 · 请过 10s 再 tail -20 discord-bot/logs/bot.out.log"
fi

# 重新开启 shell history(下次命令会进 history)
set -o history 2>/dev/null || true

echo ""
echo "🎉 轮换完成。旧 token 已失效,不必再担心之前的泄露。"
echo "   下一步:在 Discord 里 @WeWrite 今日热点 测试。"
