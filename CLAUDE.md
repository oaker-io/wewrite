# WeWrite — Claude Code onboarding

> 新 Claude Code session 在本目录启动时会自动读这份文档。读完应该秒懂:这是什么、当前做到哪、下一步该干什么。不用翻对话历史。

## 一句话定位

**WeWrite** 是微信公众号内容**全流程 skill**:热点抓取 → 选题 → 写作 → 图片 → 排版 → 推送草稿箱。目前个人化为 **智辰 / 宸的 AI 掘金笔记** 公众号的专属自动化工作站。

## 架构速览

```
┌──────────────────────────────────────────────────────────────────┐
│  用户手机 Discord                                                 │
│  ↑↓ 审阅 / 回复                                                   │
│  ─── discord-bot/ ────────── push.py(出站)+ bot.py(入站)       │
│                                                                  │
│  WeWrite skill(SKILL.md · Step 1-8)                             │
│  ├── scripts/fetch_hotspots.py  热点抓取                         │
│  ├── references/                 框架 / 写作 / 视觉规范          │
│  ├── toolkit/                    渲染 + 发布                     │
│  │   ├── converter.py              WeChatConverter(native · 16 主题)│
│  │   ├── converter_md2wx.py        md2wx 引擎(50 主题 · HTTP API) │
│  │   ├── author_card.py            :::author-card 容器(8 style)│
│  │   ├── overlay_text.py           图片叠字(Pillow · T2 workflow)│
│  │   ├── image_gen.py              多 provider 图像生成 + 配额感知 │
│  │   └── cli.py                    preview / publish 入口        │
│  └── personas/                    5 套写作人格                   │
└──────────────────────────────────────────────────────────────────┘
```

## 当前状态(截至 `git log -1`)

### 已完成
- ✅ **视觉工作流**:T0/T1/T2 三档 · 高密度 infographic-dense 模板 · 21 layout × 20 style(vendor 自 baoyu-infographic)
- ✅ **图像生成**:Poe nano-banana-2 主 · Gemini API 备 · quota-aware fallback · overlay_text.py 中文叠字兜底
- ✅ **排版双引擎**:native(自带 16 主题,零依赖)+ md2wx(50 主题,`--engine md2wx` 切换)
- ✅ **`:::author-card` 容器**:8 style preset · 61 theme 自动映射(50 md2wx + 16 native + 1 default)· 渐变 + 顶部品牌色条
- ✅ **微信草稿箱发布**:`cli.py publish` 自动上传图片 + src 重写 · AppID/AppSecret + IP 白名单已配
- ✅ **routine 已上线**:launchd 每日 08:30 · `daily-brief.sh` → `brief.py` → AI 白名单过滤 → Discord Top N · Bark/ntfy 仅作异常降级
- ✅ **Discord bot**:入站 `bot.py` daemon · ACL 白名单 · 出站 `push.py` CLI(主动推送 + DM/channel fallback + 图片附件)
- ✅ **个人 IP 化**:author=智辰 · brand=宸的 AI 掘金笔记 · 私域二维码 + aipickgold 推广固定在文末

### ✅ **阶段 B 已完成** · 手机审阅驱动的分步流程
- `scripts/workflow/{brief,write,images,publish,revise,revise_image}.py` 6 个子脚本
- `output/session.yaml` 状态机(`_state.py` 维护 · idle/briefed/wrote/imaged/done)
- `bot.py` · `_classify_intent()` 7 种 action 自然语言路由:
  - brief(今日热点/开始)· custom_idea(写 XXX)· write_idx(1-5)
  - revise(state=wrote · 改 XX / 加段 XX / 重写)
  - revise_image(state=imaged · 重做 cover / 换 chart-3)
  - next(ok/继续)· reset(pass/跳过)
- `routine/daily-brief.sh` · 08:30 调 brief.py · AI 白名单过滤 · Top N 推 Discord
- `tests/test_revise.py` · 34 条 smoke + intent 路由 + 字数警告测试(全绿)

## 关键文件地图

| 文件 | 作用 | 改它时要注意 |
|------|------|-------------|
| `SKILL.md` | 主管道(Step 1-8) | 改结构要同步 references/ |
| `style.yaml` | 个人配置(author/brand/persona/topics) | 在 gitignore · 本地修改 |
| `config.yaml` | API keys + wechat appid/secret | 在 gitignore · 永不 commit |
| `secrets/keys.env` | 集中密钥存储 | chmod 600 · 在 gitignore |
| `toolkit/author_card.py` | `:::author-card` 容器 Python 端 | **必须同步** `md2wx/skill/src/preprocessor.ts`(色板 + 映射) |
| `toolkit/cli.py` | CLI 入口(preview / publish / themes) | 加新命令从这里开始 |
| `discord-bot/bot.py` | 入站 daemon(常驻) | launchctl 管理 · 修改后 `unload + load` 重启 |
| `discord-bot/push.py` | 出站 CLI(一次性) | routine + hook + shell 都能调 |
| `routine/daily-brief.sh` | 每日 08:30 推送 | 阶段 B 要改这个串起全流程 |

## 跨仓关系

| 仓库 | 路径 | 关系 |
|------|------|------|
| **WeWrite**(本仓) | `/Users/mahaochen/wechatgzh/wewrite` | 主 skill |
| **md2wx**(fork) | `/Users/mahaochen/wechatgzh/md2wx` | 排版引擎(只是 fork,有独立 CLAUDE.md + HANDOFF.md) |
| baoyu-infographic | `~/.agents/skills/baoyu-infographic/` | 视觉设计系统源(21 layout × 20 style),已 vendor 到 `references/visuals/` |
| aipickgold.com | `https://aipickgold.com/api/convert` | md2wx 的服务端,MD2WECHAT_API_KEY 认证 |

## 密钥一览(都在 `secrets/keys.env`)

| Env | 用途 | 获取 |
|-----|------|------|
| `WECHAT_APPID` / `WECHAT_APPSECRET` | `cli.py publish` 推草稿 | mp.weixin.qq.com · 基本配置 · 注意 IP 白名单需家宽 IP |
| `POE_API_KEY` | 图像生成主(nano-banana-2) | poe.com/api_key |
| `GEMINI_API_KEY` | 图像生成备(免费层) | aistudio.google.com/apikey |
| `MD2WECHAT_API_KEY` | `--engine md2wx` 排版 | aipickgold 账号 |
| `DISCORD_BOT_TOKEN` | bot.py / push.py Discord 认证 | discord.com/developers/applications |
| `ALLOWED_USER_IDS` | bot ACL + push 默认收件人 | Discord Developer Mode · 右键头像 copy id |
| `BARK_KEY` | iPhone 推送(routine) | Bark app |

## 常用命令

```bash
# 预览文章(不发)
venv/bin/python3 toolkit/cli.py preview <md> --theme focus-navy --engine md2wx

# 发布草稿箱
venv/bin/python3 toolkit/cli.py publish <md> --engine md2wx --theme focus-navy \
    --cover output/images/cover.png --title "..."

# 主动推手机(Discord)
set -a; source secrets/keys.env; set +a
venv/bin/python3 discord-bot/push.py --text "..." --image output/images/cover.png

# 重启 Discord bot
launchctl unload ~/Library/LaunchAgents/com.wewrite.discord.plist
launchctl load -w ~/Library/LaunchAgents/com.wewrite.discord.plist

# 看 bot 日志
tail -f discord-bot/logs/bot.out.log
```

## 给新 Claude Code session 的建议

1. **先 `git log --oneline -20`** 看近期都做了什么(比看对话历史快 10 倍)
2. **读 `style.yaml`** 知道当前用户是谁(智辰 / 宸的 AI 掘金笔记)
3. **读 `output/history.yaml`**(如有)知道最近写过什么文章
4. 改 `:::author-card` 或 `author_card.py` 时**必须同步** `md2wx/skill/src/preprocessor.ts` — 两边色板/映射表要一致
5. 改代码前 `git status` 确认 clean · 改完 commit 习惯中英文都有(代码改动用英文,中文写业务决策)
6. 密钥永远不在对话里出现完整值 — 只说"已填好"

## 个人 IP 体系(固化,不要乱改)

- **作者名**:智辰(公众号顶部 · `style.yaml` author)
- **品牌**:宸的 AI 掘金笔记(封面副标 + chart 页脚 · `style.yaml` brand)
- **口号**:AI 非共识,掘金看智辰(每篇文末固定)
- **私域**:微信「智辰老师聊 ai」+ openclaw 武汉创业群
- **工具推广位**:aipickgold.com(每篇文末固定)

这些在 `output/2026-04-18-ai-coding-non-consensus.md` 末尾有完整参考模板,新文章照抄 + 换内容即可。

---

最后更新:见 `git log -1 CLAUDE.md` 的时间。
