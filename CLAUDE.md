# WeWrite — Claude Code onboarding

> 新 Claude Code session 在本目录启动时会自动读这份文档。读完应该秒懂:这是什么、当前做到哪、下一步该干什么。不用翻对话历史。

## 一句话定位

**WeWrite** 是微信公众号内容**全流程 skill**:热点抓取 → 选题 → 写作 → 图片 → 排版 → 推送草稿箱。目前个人化为 **智辰 / 宸的 AI 掘金笔记** 公众号的专属自动化工作站。

## 🎯 主题范围(WeWrite 的核心宗旨 · 2026-04-25 锁)

**所有文章必须命中以下 6 个主题之一 · 越界即重写**:

1. **AI 搞钱** — 副业 / 变现 / 月入 / 路径 / ROI / 红利窗口
2. **AI 实战** — 跑通流程 / 上手操作 / 工程化落地 / 路径具体到「明天能用」
3. **AI 真实案例** — Day 0/Day N 时间线 + 具体数字 + 失败/坑(可信度三件套)
4. **AI 心得** — 反共识 / 冷观察 / 工程派判断 · 不堆 hype 不喊口号
5. **AI 最新测试** — 工具评测 / 横向对比 / 实测数据(不只是「我觉得」)
6. **AI 咨询** — 行业判断 / 投资视角 / 趋势分析 / 红利路径推演

**为什么这 6 个**:用户智辰的人设是「哈工大本硕 + 6 年半导体 → AI 创业实战派」(见 `identity/identity.md`)·
偏「搞钱实战派」(xwrite 4/23 转向)· 不写情绪八卦 / 不写空洞 hype / 不做泛科技资讯。

**违规清单**(任一命中 · prompt 重写):
- ❌ 政治 / 股票币圈 / 同行八卦 / 个人感情(`identity/voice/forbidden.md`)
- ❌ 翻译式无价值复述外文 · 必须有非共识 take
- ❌ 「AI 让生活更美好」「未来已来」式空话
- ❌ 跟 6 大主题任一都搭不上的话题(健康 / 教育 / 旅游 / 养生 / 娱乐...)

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
- ✅ **图像生成**:Poe gpt-image-2 主 · Gemini API 备 · quota-aware fallback · overlay_text.py 中文叠字兜底(2026-04-25 从 nano-banana-2 切到 gpt-image-2)
- ✅ **排版双引擎**:native(自带 16 主题,零依赖)+ md2wx(50 主题,`--engine md2wx` 切换)
- ✅ **`:::author-card` 容器**:8 style preset · 66 theme 自动映射(50 md2wx + 16 native)· **table 布局**(WeChat-safe)+ linear-gradient 渐变 · **mp_brand 现在渲染成虚线占位框**(2026-04-25 改 · 用户发表前在 mp.weixin.qq.com 工具栏「资源引用→公众号」手插真卡覆盖)
- ✅ **微信草稿箱发布**:`cli.py publish` 自动上传图片 + src 重写 · 默认接 `sanitize` 中间件(去 H1 / 清 cover alt / 兜底 author-card / 补 mp_brand / **加 QR 块**)· AppID/AppSecret + IP 白名单已配
- ✅ **routine 已上线**:launchd 每日 08:30 · `daily-brief.sh` → `brief.py` → AI 白名单过滤 → Discord Top N · Bark/ntfy 仅作异常降级
- ✅ **Discord bot**:入站 `bot.py` daemon · ACL 白名单 · 出站 `push.py` CLI(主动推送 + DM/channel fallback + 图片附件)
- ✅ **个人 IP 化**:author=智辰 · brand=宸的 AI 掘金笔记 · 私域二维码 + aipickgold 推广固定在文末

### ✅ **阶段 B 已完成** · 手机审阅驱动的分步流程
- `scripts/workflow/{brief,write,images,publish,revise,revise_image}.py` 6 个子脚本
- `output/session.yaml` 状态机(`_state.py` 维护 · idle/briefed/wrote/imaged/done)
- `bot.py` · `_classify_intent()` 8 种 action 自然语言路由:
  - brief(今日热点/开始/「选题」单独成词)· custom_idea(写 XXX / **选题:XXX** / **主题:XXX** / **话题:XXX**)
  - write_idx(1-5)· revise(state=wrote · 改 XX / 加段 XX / 重写)
  - revise_image(state=imaged · 重做 cover / 换 chart-3)· **republish**(state=done · 重新排版/重新发布)
  - next(ok/继续)· reset(pass/跳过)
- `routine/daily-brief.sh` · 08:30 调 brief.py · AI 白名单过滤 · Top N 推 Discord
- `tests/test_revise.py` · 34 条 + `tests/test_sanitize.py` · 81 条(全绿)

### ✅ **阶段 E 已完成** · 全自动 1 篇/天 + 7 天内容轮播(2026-04-23)
- `config/auto-schedule.yaml` 7 天 category 轮播(周一 AI 使用手册 / 周二干货 / 周三 ★案例 / 周四评测 / 周五热点 / 周六轻量 / 周日合集)
- `scripts/workflow/auto_pick.py` LLM-free 选题(weekday → category → idea_bank Top 1 主+1 备)
- `scripts/workflow/auto_review.py` 5+1 维度自审(钩子/字数/图数/口头禅/禁忌词 + 案例真实感)
- `references/visuals/styles/case-realistic.md` ★ 案例配图拟真套件(5 张图 prompt + negative + 信任三件套)
- `write.py` `_build_prompt_case()` · 案例类强制要求具体数字 + 5 张拟真截图占位符
- `images.py --auto --style case` · 案例类走 case-realistic 套件 · 取消 ok gate
- `publish.py --auto` · 全自动推草稿 · push Discord 通知 · 不等用户回复
- `sanitize.py` · aipickgold 链接自动加 UTM(utm_source=mp&utm_date=YYYY-MM-DD)
- 7 个 launchd plist:`com.wewrite.auto-{pick,write,images,review,publish,notify,stats}.plist`
- 时间表:07:00 pick → 08:00 write → 10:00 images → 11:00 review → 12:00 publish → 19:30 群发提醒 → 周日 02:00 回填
- `routine/install-auto.sh` · 一键装/卸/列(替换 __REPO_ROOT__ + launchctl load -w)
- 群发限制:订阅号每日 1 次 · 没实现 masssend API · 用户每晚 1 tap 即可(决策 3)
- `tests/test_auto_pick.py` 7 + `test_auto_review.py` 7 + `test_case_prompt.py` 7 + `test_sanitize_utm.py` 6 = 27 新条 · 总 181 条全绿

### 🟣 **P1+P2+P3 进行中** · KOL 公众号语料库 + 头部模式注入(2026-04-25)
- **P1 框架就绪**:`scripts/fetch_kol.py` · 03:00 凌晨抓 KOL RSS → corpus + idea_bank · 错峰避开白天 claude token
- **P2 metadata 抽取**:`scripts/analyze_kol.py` · 4 层(选题/结构/风格/传播) · 输出 `output/kol_patterns.yaml`
- **P3 prompt 注入**:`write.py:_load_kol_patterns_block()` · hotspot/shortform/case/tutorial 4 个 prompt 都注入「今日头部对标」段
- `config/kol_list.yaml` · 15 KOL 清单(8 用户 + 7 Claude 补 · 偏个人 IP / 副业搞钱 / AI 实战)
- `infra/wewe-rss/` · Docker compose + README · 用户起 wewe-rss 后扫码 · web UI 订阅 KOL · 拿 RSS url 填 kol_list.yaml
- `auto-fetch-kol.sh` · 03:00 触发 fetch → 自动链 analyze · 失败 push Discord 不阻断
- 阻塞:用户须装 OrbStack + 启 wewe-rss + 扫码 + 订阅 · 之后填 kol_list.yaml#rss_url + 改 status=active
- 测试:`test_fetch_kol.py` 10 + `test_analyze_kol.py` 22 = 32 新条 · 总 291 全绿

## 关键文件地图

| 文件 | 作用 | 改它时要注意 |
|------|------|-------------|
| `SKILL.md` | 主管道(Step 1-8) | 改结构要同步 references/ |
| `style.yaml` | 个人配置(author/brand/persona/topics) | 在 gitignore · 本地修改 |
| `identity/` | 个人身份档案 · 从 xwrite vendor · write.py 注入 prompt | 在 gitignore · 别手改 · 跑 `scripts/sync-identity-from-xwrite.sh --apply` 同步 |
| `config.yaml` | API keys + wechat appid/secret | 在 gitignore · 永不 commit |
| `secrets/keys.env` | 集中密钥存储 | chmod 600 · 在 gitignore |
| `toolkit/author_card.py` | `:::author-card` 容器 Python 端 | **必须同步** `md2wx/skill/src/preprocessor.ts` · **CSS 严守 WeChat 白名单**(见下) |
| `toolkit/sanitize.py` | 发布前五件套兜底(H1/cover-alt/author-card/mp_brand/**QR 块**) | 纯函数幂等 · cli.py + workflow.publish.py 双接入 |
| `toolkit/cli.py` | CLI 入口(preview / publish / themes) | `publish` 默认开 sanitize · `--no-sanitize` opt-out |
| `discord-bot/bot.py` | 入站 daemon(常驻) | launchctl 管理 · 修改后 `unload + load` 重启 |
| `discord-bot/push.py` | 出站 CLI(一次性) | routine + hook + shell 都能调 |
| `routine/daily-brief.sh` | 每日 08:30 推送(brief 半自动 · 仍保留) | 阶段 B 要改这个串起全流程 |
| `config/auto-schedule.yaml` | **阶段 E** 全自动 7 天轮播 + 各 step 开关 + review 阈值 | 改 schedule 立即生效 · 全停用 enabled: false |
| `scripts/workflow/auto_pick.py` | 07:00 LLM-free 选题(weekday → category → idea_bank) | 周三必选 case · 不要改 weekday=2 那条 |
| `scripts/workflow/auto_review.py` | 11:00 LLM 自审 5+1 维度 · skip-llm 模式给测试用 | LLM 维度失败不阻断 · 阈值在 yaml 改 |
| `references/visuals/styles/case-realistic.md` | ★ 案例配图拟真套件 prompt 模板 | 改了等于改了周三所有案例文的视觉 · 慎重 |
| `scripts/auto/*.sh` | 7 个 cron 包装(_common.sh + auto-{pick,write,images,review,publish,notify,stats}.sh) | step_check_enabled 读 yaml · 失败 push Discord |
| `routine/install-auto.sh` | 一键装/卸/列 7 个 launchd plist | 装完看 launchctl list · 用 --uninstall 卸 |

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
| `POE_API_KEY` | 图像生成主(gpt-image-2) | poe.com/api_key |
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
7. **自动开 skills**(2026-04-25 用户要求 · 不要等提醒):
   - 非平凡编码任务前 → invoke `andrej-karpathy-skills:karpathy-guidelines`(防过度工程化)
   - 用户问"以前 / 上次 / 历史" → invoke `claude-mem:mem-search`(跨 session 持久 memory)
   - 探索某个 module 结构 → 用 `claude-mem:smart-explore` 替代 Read 全文(token 优化)
8. **wewrite 团队 sub-agent**(`.claude/agents/`)· 主线程协作时优先 delegate:
   - `topic-curator` 选题判 6 大主题 · `hook-writer` 生 5 钩子候选
   - `kol-pattern-analyst` KOL 文章拆解 · `review-critic` 7 维度自审
   - `revise-editor` 外科改稿 · `visual-art-director` 视觉决策

## WeChat 公众号 CSS 白名单(2026-04-20 踩坑实战)

WeChat 公众号编辑器对**草稿写入的内联 HTML** 应用严格 CSS 白名单。**不在白名单**的属性
会让渲染器**静默丢弃整个块**——`draft/get` API 拉的 HTML 完整存在,但用户在草稿箱/预览/手机端
都看不到。改 `:::author-card` 或新增任何**自定义内联 HTML 块**时严格遵守:

**❌ 必死(整块消失)**:
- `display: flex` / `gap` / `align-items` / `justify-content` 任何 flex 属性
- `-webkit-line-clamp` / `-webkit-box` / `object-fit` 任何 -webkit-* 前缀
- `text-overflow: ellipsis`
- `position: absolute/fixed/relative`

**✅ 实测安全**:
- `linear-gradient(135deg/90deg, ...)` 渐变(背景 / 头像 / 品牌条)
- `<table cellpadding=0 cellspacing=0>` + `<tr>` + `<td vertical-align: middle>` 横排布局
- `border-radius` / `padding` / `margin` / `border` / `background-color` / 字体 / 行高 / 颜色

**⚠️ 不确定**:`box-shadow`(暂不用,稳)

**调试 WeChat 渲染问题的方法论**:
1. 永远用 `publisher.get_draft(token, media_id)` 拉**真实 HTML**对比,别只信本地浏览器渲染
2. HTML 在 ≠ 渲染出来——WeChat 可能静默剥块
3. 用户报「看不到」连续 2 次以上,先怀疑自己的修复假设而非用户位置感
4. 详见 `~/.claude/projects/-Users-mahaochen-wechatgzh-wewrite/memory/` 下两条 memory

`toolkit/author_card.py:_build_tokens` 是 WeChat-safe 范本(table 布局 + 渐变 + 零 shadow)。
新加内联 HTML 块前**先看那里**。

## 个人 IP 体系(固化,不要乱改)

- **作者名**:智辰(公众号顶部 · `style.yaml` author)
- **品牌**:宸的 AI 掘金笔记(封面副标 + chart 页脚 · `style.yaml` brand)
- **口号**:AI 红利,看智辰(每篇文末固定 · 2026-04-25 替换 · 旧口号「AI 非共识,掘金看智辰」已淘汰 · 同步 xwrite/identity/identity.md:390)
- **私域**:微信「智辰老师聊 ai」+ openclaw 武汉创业群
- **工具推广位**:aipickgold.com(每篇文末固定)

这些在 `output/2026-04-18-ai-coding-non-consensus.md` 末尾有完整参考模板,新文章照抄 + 换内容即可。

---

最后更新:见 `git log -1 CLAUDE.md` 的时间。
