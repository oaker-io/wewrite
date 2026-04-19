# WeWrite · 日常自动化(launchd + push)

每天 08:30 自动抓 5 条热点,推送到你 iPhone,提醒你今天写不写稿。不自动生成文章(避免浪费额度 + 生成废稿)。

## 架构

```
08:30 每天  · launchd 触发 com.wewrite.daily
        ↓
daily-brief.sh
  → 跑 scripts/fetch_hotspots.py 抓 Top 20 热点
  → 抽 Top 5 标题拼文
  → notify.sh "WeWrite 早报" "5 条热点..."
        ↓
notify.sh
  → 按优先级 Bark > ntfy.sh > macOS 本地通知
        ↓
iPhone 收到推送
  → 你看完决定
  → 要写就打开 Mac 说「/wewrite 今天写」,触发完整 Step 1-8
```

## 一键安装

**步骤 1**:选一种推送方式(推荐 Bark,国内好用)

### 方案 A · Bark(推荐国内用户)

1. 在 iPhone App Store 搜 **「Bark」**,安装
2. 打开 app → 复制你的个人 URL(类似 `https://api.day.app/xxxxxxxxxx/`)
3. Key 就是 `xxxxxxxxxx` 那段(10 字母数字)

```bash
./routine/install.sh xxxxxxxxxx
```

### 方案 B · ntfy.sh(推荐海外用户)

1. 在 iPhone 装 **ntfy** app(App Store)
2. 订阅一个你自己定的 topic,比如 `wewrite-mahaochen-x7k2`(不要太简单,否则别人订阅同个 topic 能收到你的推送)

```bash
./routine/install.sh @ntfy wewrite-mahaochen-x7k2
```

### 方案 C · 先试本地通知(不装任何 app,只弹 Mac 自己的通知中心)

```bash
./routine/install.sh
```

**步骤 2**:立即测试(不等到明天 08:30)

```bash
bash routine/daily-brief.sh
```

应该看到 `[bark] pushed` 或 `[ntfy] pushed` 或 `[osascript] local notified`。
iPhone 上马上能看到:

> **WeWrite 早报 · 04-19 08:30**
>
> 📰 今日 Top 5 热点
> 1. xxxx
> 2. xxxx
> ...
>
> 📝 最近草稿:2026-04-18-xxx.md
>
> 🚀 想写的话,在 Claude Code 里说「/wewrite 写今天」

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.wewrite.daily.plist
rm ~/Library/LaunchAgents/com.wewrite.daily.plist
```

## 改时间

编辑 `routine/com.wewrite.daily.plist` 里的:

```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>8</integer>      ← 改这里
  <key>Minute</key><integer>30</integer>   ← 改这里
</dict>
```

然后重跑 `./routine/install.sh <KEY>` 重新安装。

## 日志

```bash
tail -f routine/logs/daily-brief.out.log
tail -f routine/logs/daily-brief.err.log
```

## 为什么不自动跑全流程?

1. **生成废稿风险**:没有你的选题审核,AI 可能每天生成一篇没人要的文章
2. **浪费 Poe 额度**:每篇 5 张图,每天烧 5 张,一个月 150 张很贵
3. **内容质量无人把关**:标题/框架/配色 AI 自己决定 ≠ 你的风格

**正确姿势**:早上收到推送 → 上班路上看热点 → 到办公室打开 Mac 说「/wewrite 写第 2 条」→ 15 分钟出草稿 → 你审一下 → 发布。

## 未来扩展

- 每周日晚推送「本周数据复盘」(阅读量/新增粉丝)
- 每篇草稿推送后追踪 24 小时效果,送「阅读量低于平均」的重写提醒
- 结合 Discord bot,做双向对话(见 `discord-bot/README.md`)
