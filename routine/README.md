# WeWrite · 日常自动化(launchd + Discord)

每天 08:30 launchd 触发 `daily-brief.sh` → `scripts/workflow/brief.py` → **AI 白名单过滤** → Top N 选题推 Discord。你在手机上回复 `1/2/3` 驱动后续步骤(写文/生图/发布)。

**不自动写文 / 不自动生图 / 不自动发布** — 这 3 步必须你审过才跑(防止生成废稿 + 烧 Poe 额度)。

## 流程

```
每天 08:30 · launchd
    ↓
daily-brief.sh
  · source secrets/keys.env  (DISCORD_BOT_TOKEN 等)
  · run scripts/workflow/brief.py
    ↓
brief.py
  · fetch hotspots(60 条)
  · AI 白名单过滤 · 机器人话题降权 + cap 2
  · Top 5 推 Discord DM(走 push.py · bot.py token)
    ↓
你的 iPhone Discord
  · 收到 "📰 今日 AI 选题 Top N" · 每条带分数 + 命中词
  · 回 `1/2/3` → bot.py 触发 write.py → 3-8 分钟预览
  · 回 `ok/继续` → images.py / publish.py 按状态自动派发
  · 回 `pass/跳过` → 清 session 等明天

失败降级:brief 异常 → notify.sh(Bark / ntfy / osascript 本地弹窗)
```

## 安装

前置条件(都已具备可跳过):
- `secrets/keys.env` 有 `DISCORD_BOT_TOKEN` + `ALLOWED_USER_IDS`
- `com.wewrite.discord`(bot 主进程)已装 launchd 并在线
- `venv/bin/python3` 可用

```bash
./routine/install.sh
```

装完 `launchctl list | grep com.wewrite.daily` 能看到 PID。

## 立即测试(不等 08:30)

```bash
bash routine/daily-brief.sh
tail routine/logs/daily-brief.$(date +%F).log
```

手机 Discord 应马上收到 Top 选题推送。

## 改时间

编辑 `routine/com.wewrite.daily.plist`:

```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>8</integer>      ← 改
  <key>Minute</key><integer>30</integer>   ← 改
</dict>
```

然后重跑 `./routine/install.sh`(内部会 unload 旧的再 load 新的)。

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.wewrite.daily.plist
rm ~/Library/LaunchAgents/com.wewrite.daily.plist
```

## 为什么只自动触发 brief,不跑全流程?

1. **生成废稿风险** · 没你的选题审核,AI 每天可能生成没人要的稿
2. **烧 Poe 额度** · 每篇 5 张图 · 一天一篇一个月 150 张
3. **质量无人把关** · 标题/框架/配色 AI 自决 ≠ 你的风格

**正确姿势**:早 08:30 推送 Top N 选题 → 通勤路上看 → 挑一条回 `1` → 中午回 Mac 已经有预览了 → Discord `ok` 进生图 → 再 `ok` 推草稿箱 → 去微信后台加公众号卡片 → 发。

## 故障排查

| 现象 | 检查 |
|------|------|
| 08:30 没收到 Discord | `launchctl list \| grep wewrite` 看两个服务(discord + daily)都在 |
| brief 跑了但无推送 | `tail routine/logs/daily-brief.*.log` · 看有无 Discord HTTP 错 |
| "DISCORD_BOT_TOKEN 未设置" | `secrets/keys.env` 有没有这行 + chmod 600 |
| bot 在线但不响应 `1/2/3` | bot.py 改过后要 `launchctl unload/load ~/Library/LaunchAgents/com.wewrite.discord.plist` |

## 未来扩展

- 周日晚推「本周阅读量复盘」(要先对接微信数据 API)
- 草稿发布后 24h 追踪阅读量 · 触发重写提醒
- 直接 Discord 里说「改开头」/「重做 chart-3」路由到对应子流程
