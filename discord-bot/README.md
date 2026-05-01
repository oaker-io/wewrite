# WeWrite · Discord bot 桥

让你在 Discord 里 @bot 问 Claude Code 做事情——"今日热点"、"写一篇 XX"、"用 md2wx 重排"…… bot 把消息转给本机的 `claude -p`,Claude 跑 WeWrite skill,结果 chunk 回发到 Discord。

## 架构

```
[你在手机/任意设备]         [你 Mac 本机,bot 进程]        [Claude Code CLI]
Discord app  ──@bot──→  bot.py (discord.py 监听)  ──subprocess──→  claude -p "..."
                            ↓                                            ↓
                        拆分 ≤1900 字符                          跑 WeWrite skill
                            ↓                                            ↓
Discord app  ←──发回──  bot.py 分批 send   ←──────stdout─────────  完整回复
```

**前提**:bot 进程跑在你 Mac 上(launchd daemon,开机自启 + 崩溃自拉起)。
如果你 Mac 关机,bot 离线——这是最大限制。若要 24/7 在线,把 bot 放到 VPS(Oracle 永久免费机足够)。

## 安装(10 分钟)

### 1. 创建 Discord bot

1. 打开 https://discord.com/developers/applications
2. **New Application** → 起个名字(例 `WeWrite`)
3. 左栏 **Bot** → 如果没有 "Reset Token" 按钮就点 **Add Bot** → **Reset Token** → 复制 token(这串只显示一次)
4. 同页往下滚到 **Privileged Gateway Intents**,**打开** `Message Content Intent`
5. 左栏 **OAuth2** → **URL Generator**:
   - Scopes 勾 `bot`
   - Bot Permissions 勾 `Read Messages/View Channels`、`Send Messages`、`Read Message History`
6. 复制生成的 URL,浏览器打开 → 选一个你自己的服务器 → Authorize
7. 回到 Discord,bot 应该已经在你的服务器成员列表里

### 2. 拿到你自己的 Discord user ID(做 ACL 白名单)

在 Discord app 设置 → Advanced → 打开 Developer Mode,然后右键你自己的用户名 → Copy User ID,得到 18 位数字。

### 3. 一键装

```bash
./discord-bot/install.sh <TOKEN> <你的USER_ID>
```

例:

```bash
./discord-bot/install.sh "MTA3..." 123456789012345678
```

脚本会:
- 在 `venv/` 装 `discord.py`
- 把 plist 写到 `~/Library/LaunchAgents/`
- `launchctl setenv` 注入 token + ACL
- `launchctl load` 启动 daemon

### 4. 测试

在 Discord 里 @WeWrite(或你给 bot 起的名字),说:

> `@WeWrite 今日热点`

Bot 应该回 "🤔 Claude 思考中...",过 10-30 秒回带热点摘要的消息。

## 常用命令

| 说什么 | Claude 会做什么 |
|-------|----------------|
| `@bot 今日热点` | 跑 scripts/fetch_hotspots.py,回 Top 5-10 |
| `@bot /wewrite 写一篇关于 XX 的文章` | 触发完整 Step 1-8(5-10 分钟,Bot 每 30s 更新进度) |
| `@bot 用 md2wx 经典-暖橙 重排最近那篇` | 重新渲染 HTML 并返回路径 |
| `@bot 发布 output/xxx.md` | 调 cli.py publish 推送草稿箱 |
| `@bot 看看文章数据` | 跑 scripts/fetch_stats.py |

**注意**:bot 用的是你本机的 Claude Code + skill + 配置,所以它的能力 = 你在 Claude Code 里能做的所有事。

## 限制 + 风险

### 单条消息 ≤1900 字符

Discord 硬上限 2000,bot 自动拆分多条。长文章/长日志会分 10+ 条发出来。

### Claude 非交互模式的局限

`claude -p` 是一次性的,没有会话上下文。所以 bot 不记得上一条消息,每次 @ 都是新对话。
这对短命令(今日热点、数据、发布)足够,但"继续改一下"这种跟进命令不会 work。未来扩展可以用 `--resume` + session 管理。

### ACL 是字符串匹配

`ALLOWED_USER_IDS` 没设时**所有人**都能 @bot 让它跑。务必设白名单,不然陌生人可以让你的 Claude 做事(消耗 API 额度)。

### 网络

bot 需要持续连 `gateway.discord.gg`(Websocket)。家庭宽带一般没问题。

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.wewrite.discord.plist
rm ~/Library/LaunchAgents/com.wewrite.discord.plist
launchctl unsetenv DISCORD_BOT_TOKEN
launchctl unsetenv ALLOWED_USER_IDS
```

## 日志 / 排错

```bash
tail -f discord-bot/logs/bot.out.log    # stdout(包含 "Logged in as" 启动信息)
tail -f discord-bot/logs/bot.err.log    # stderr(报错/traceback)
```

典型问题:
- **"Message Content Intent is missing"** → 回 Developer Portal 打开那个开关
- **bot 启动后不回复** → 检查 bot 是否在频道有 Read + Send 权限
- **`claude: command not found`** → 改 `plist` 里 `PATH`,或 `CLAUDE_BIN` 指向绝对路径

## 升级想法(v2)

- `--output-format stream-json` → 实时展示 Claude 每一步(工具调用/文件修改)
- Slash commands(`/wewrite`、`/heat`)→ 比 @mention 体验好
- 把 push 通知(routine/notify.sh)集成:Claude 跑完一篇 → 自动发 bot channel 预览
- Discord thread 支持:每篇文章一个 thread,Claude 在里面分多步回复
