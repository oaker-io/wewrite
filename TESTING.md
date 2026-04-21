# WeWrite 测试指南

> 给智辰用 · 把 2026-04-21 这一波加的所有功能(干货系列 / idea 库 / 抹道 / brief 集成 / mockup / sanitize / republish)按顺序过一遍。
> 每节统一三段:**做什么** · **期待结果** · **失败排查**。
> Discord 输入都可**直接复制粘贴**给 bot。

---

## 0. 测试前 60 秒环境检查

**做什么**
```bash
cd /Users/mahaochen/wechatgzh/wewrite
launchctl list | grep wewrite                      # bot 在不在
cat output/session.yaml | grep state               # 当前 state
ls venv/bin/python3 && ls toolkit/cli.py           # 关键路径
```

**期待结果**
- `com.wewrite.discord` 出现一行(PID 非 -)
- `state: idle` 或 `done` 或 `briefed/wrote/imaged`(任何一个都正常)
- 两个文件都存在

**失败排查**
- bot 不在:`launchctl load -w ~/Library/LaunchAgents/com.wewrite.discord.plist`
- venv 缺:跑 `python3 -m venv venv && venv/bin/pip install -r requirements.txt`(若有 requirements.txt)

---

## 1. 一键全套单元测试(2 分钟)

**做什么**
```bash
venv/bin/python3 -m unittest tests.test_sanitize tests.test_revise tests.test_idea_bank tests.test_brief_idea_integration tests.test_fetch_changelog 2>&1 | tail -3
```

**期待结果**
```
Ran 140 tests in ~1.7s
OK
```

**失败排查**
- 出现 FAIL/ERROR:`venv/bin/python3 -m unittest tests.<那个测试文件> -v` 看具体哪条
- import 报错:确认 `tests/__init__.py` 存在
- 网络相关 fail:`tests.test_fetch_changelog` 用 mock,**不该**有真实网络依赖,有就是测试漏 mock

---

## 2. idea 库管理(Discord 实测 · 5 分钟)

bot 必须在线。下面**直接复制粘贴**到 Discord 给 @WeWrite。

### 2.1 存 idea(自动推断 category)
```
存 idea: claude design 9 个使用细节 教程
```
**期待**:bot 回 `✓ 已存 #1 · tutorial · claude design 9 个使用细节 教程`(category 因为含「教程」自动 = tutorial)

```
存 idea: 豆包变豆脚的反共识观察 热点
```
**期待**:`✓ 已存 #2 · hotspot · ...`(因为含「热点」)

```
存 idea: 一个普通主题
```
**期待**:`✓ 已存 #3 · flexible · ...`(默认)

### 2.2 列 idea
```
今日 idea
```
或
```
我的 idea
```
**期待**:markdown 表(列前 5 条),格式类似:
```
| # | 标题 | category | priority | tags |
|---|------|----------|----------|------|
| 3 | ... | flexible | 50 | ... |
| 2 | ... | hotspot | 50 | ... |
| 1 | ... | tutorial | 50 | ... |
```

### 2.3 标已用 / 删
```
idea 1 用了
```
**期待**:`✓ idea #1 已标记用过 · ...`

```
删 idea 2
```
**期待**:`🗑️ 已删 #2 · ...`

```
今日 idea
```
**期待**:列表里 #1(已用)和 #2(已删)都不出现 · 只剩 #3

**失败排查**
- bot 没回:`tail -50 discord-bot/logs/bot.out.log` 看 intent 路由有没有触发
- 回了但报错:看错误信息(idea.py 的 stderr 会原样回来)
- 命令没识别:看 `discord-bot/bot.py:_classify_intent` 第 207-249 行的正则

---

## 3. 干货系列触发(Discord 实测 · 10 分钟 · 真跑 claude)

```
教程: 一个简单测试主题(比如:用 Python 写个 Hello World)
```

**期待**:
1. 立刻回:`🛠️ 收到干货 idea(🛠️ 干货系列 · tutorial-instructor 人格)... 5-12 分钟`
2. 5-12 分钟后回:`✓ 干货初稿就绪,已推预览 · 回 ok 进生图`
3. 文章 push 到 Discord,标头含 `📝 文章初稿就绪 · NNNN 字 · 🛠️ 干货系列`

也可以试其他触发词(都走 tutorial):
```
干货:Cursor 配置 SOP
方法论: 用 Claude 重构遗留代码
how to use mcp
手把手:30 分钟搭一个 RAG demo
如何 把 claude design 嵌进现有项目
```

对比 · 触发**热点**(走 hotspot prompt):
```
选题: 测试用热点主题
写一篇 测试热点
```
应该回 `💡 收到自定义 idea(🔥 热点系列)...`

**失败排查**
- bot 没回 → `tail -50 discord-bot/logs/bot.out.log`
- 触发词没识别(走了 brief 或 claude_fallback)→ 检查 bot.py:_classify_intent · 也可能 bot 没重启:`launchctl unload && load -w ~/Library/LaunchAgents/com.wewrite.discord.plist`
- claude 子进程超时(900s)→ 主题改简单点 · 看 `output/<最新文件>.md` 是否半成品

---

## 4. 抹道 fetch_changelog(命令行 · 30 秒每源)

**做什么**(先 dry-run · 看到内容再决定写库)
```bash
venv/bin/python3 scripts/fetch_changelog.py --source github-trending --limit 3 --dry-run
```

**期待**:打印 3 条
```
+ #<id> [github] GitHub 今日热门 AI 项目: owner/repo · ...
+ #<id> [github] ...
+ #<id> [github] ...
```

去掉 `--dry-run` 真写入:
```bash
venv/bin/python3 scripts/fetch_changelog.py --source github-trending --limit 3
```

然后到 Discord 验证:
```
今日 idea
```
**期待**:列表里出现刚才那 3 条 GitHub trending(category=tutorial · source=github)

其他源:
```bash
venv/bin/python3 scripts/fetch_changelog.py --source anthropic-blog --limit 3 --dry-run
venv/bin/python3 scripts/fetch_changelog.py --source anthropic-changelog --limit 3 --dry-run
venv/bin/python3 scripts/fetch_changelog.py --source all --limit 5 --dry-run
```

**失败排查**
- HTTP 报错:看 stderr 的 `[warn]` 行 · 单源失败不影响其他源
- 一条都没抓到:可能页面结构变了 · 看 `scripts/fetch_changelog.py` 对应 parser
- 抓到但去重全跳:idea_bank 里已存在同名 · `cat output/idea_bank.yaml | grep -i "<关键词>"` 验证

---

## 5. brief 集成 idea 库(命令行 + Discord · 2 分钟)

**做什么**(确保 idea 库里有 ≥ 1 条未用 idea · 否则只显示热点段)
```bash
venv/bin/python3 scripts/workflow/brief.py
```

**期待**:Discord 立刻收到推送(分两段)
```
🔥 今日热点 Top 3
1. ...(微博 / 百度 / 头条热搜)
2. ...
3. ...

📌 你的 idea 库 Top 3
4. (tutorial · #5) ...
5. (hotspot · #8) ...
6. (flexible · #12) ...

👉 回复 1-6 选一个 · 或 pass 今天跳过
```

回 idea 编号(4/5/6):
```
4
```
**期待**:走对应 category 的 prompt(tutorial idea 自动 --style tutorial),写完后 idea 库自动 `mark_used`(下次 brief 不再推荐这条)。

回热点编号(1/2/3):走 hotspot prompt,跟以前行为一致。

**失败排查**
- 不显示「📌 你的 idea 库」段:idea 库可能空了(全标 used) · `venv/bin/python3 scripts/workflow/idea.py list --all` 看
- 选了 idea idx 但 style 不对:看 `scripts/workflow/write.py:_auto_style_from_topic` 推断逻辑
- mark_used 没生效:看 write.py 末尾对应代码 + `output/idea_bank.yaml` 里那条的 `used` 字段

---

## 6. Screen mockup(只能在生图阶段验证 · 10 分钟)

**做什么**:跑完干货文章(第 3 节)后,bot push 预览 → 回 `ok` → 进生图阶段
```
ok
```

**期待**:5-15 分钟后 push 5 张图(cover.png + chart-1.png ~ chart-4.png)。
查看 `output/images/cover.png` · 视觉应该是:
- macOS 应用窗口风格(traffic-light + toolbar)/ 或
- iOS 手机 UI 风格(状态栏 + Dynamic Island)/ 或
- 终端窗口风格(深色 + 等宽字体)/ 或
- VSCode/Cursor 编辑器风格(file tree + 代码)

**失败排查**
- 生成的封面用了非 mockup 风格:AI 选 style 时没优先 mockup-* · 看 `output/<slug>-prompts.md` 里 cover 的 prompt 含哪个 style
- 看不到风格区别:`open output/images/cover.png` 视觉对比
- 想强制某个 mockup style:在主题里加暗示词(eg「教程: 用 cursor 写 ai · 截图风」会增加 mockup-code-editor 触发概率)

---

## 7. republish 端到端(验证 sanitize · 5 分钟)

state 必须 = `done`(已发布过一次)。

```
重新排版发布
```
或
```
重新排版发布到草稿箱
```

**期待**:
1. bot 回:`🔁 重新 sanitize + 推草稿箱(几十秒)...`
2. 完成后:`✓ 已重推草稿箱 · 带最新 sanitize(H1/cover-alt/author-card)`
3. 到 mp.weixin.qq.com → 草稿箱 → 找最新这条 → 编辑

草稿箱里**滚到最末尾**应看到:
- ✅ 智辰老师 author-card(渐变背景 · 表格布局横排)
- ✅ 嵌入的「宸的 AI 掘金笔记」mp 视觉卡(白底 · 头像 · 描述 · 右箭头)
- ✅ 标签 + footer
- ✅ **无重复 H1**(WeChat 标题栏不重复出现在文章顶部)
- ✅ 封面图下面**无「封面」二字**

**失败排查**
- bot 回的不是 `🔁 重新 sanitize` 那条 → 走了 claude fallback · 看 _classify_intent 是否识别
- 草稿没 author-card → 直接拉 API HTML 看(下面的故障排查 9.B):
- WeChat 草稿箱缓存问题 → 改用「编辑」入口(不是「预览」)

---

## 8. 一键端到端(冒烟 · 30 分钟内做完)

适合每次大改后跑一遍。按顺序:

1. 第 0 节环境检查 ✓
2. 第 1 节单元测试全绿 ✓
3. 第 2 节存 1 条 tutorial idea + 列 ✓
4. 第 3 节触发干货文章 → 等写完 → 看预览 ✓
5. 回 `ok` → 等生图 → 看 cover 是 mockup 风 ✓
6. 回 `ok` → 推草稿 → 看 sanitize 提示 ✓
7. 第 7 节看草稿箱 author-card 完整 ✓
8. 试 `重新排版发布` → 验证 republish ✓

每步过了 = 整套链路稳。

---

## 9. 故障排查速查

| 现象 | 看哪 | 怎么修 |
|---|---|---|
| bot 不响应 Discord | `tail -50 discord-bot/logs/bot.out.log` | `launchctl unload + load -w` |
| bot 触发词不识别 | `discord-bot/bot.py:_classify_intent` | 看正则匹配优先级 |
| 草稿箱没 author-card | 拉 API 直看 HTML(见 9.B) | 多半是没用最新 sanitize · 重启 bot 重 publish |
| idea 库丢失 | `ls -la output/idea_bank.yaml` | 误删?· 看 git 是否有 backup(yaml 不在 git 里) |
| changelog 抓不到 | `--dry-run` + `--source <单源>` 隔离 | 网页结构变 / 网络 / 触发反爬 |
| 干货 prompt 走成 hotspot | 看 `_auto_style_from_topic` 推断 | 标题加「教程」前缀强制 tutorial |
| brief 不推 idea 段 | `idea.py list` 看库有几条未用 | 没未用 idea · `idea.py add` 几条 |
| claude 子进程超时 | timeout=900 (15 分) | 主题改简单 / 单独跑 `write.py --idea ...` 看 stderr |
| WeChat 预览 vs 编辑器不一致 | 编辑器才是真渲染 | 别看预览链接 · 看后台编辑页 |

### 9.A bot intent 路由现状(8 种 action)

| Intent | 关键词触发 | 状态条件 |
|---|---|---|
| `brief` | 「brief」「今日热点」「今天写」「开始」「看看有什么写」「选题」(单独成词) | 任意 |
| `custom_idea` | 「写 XX」「选题: XX」「主题: XX」「话题: XX」 | 任意 |
| `tutorial_idea` | 「教程: XX」「干货: XX」「方法论: XX」「手把手: XX」「how to XX」「如何 XX」 | 任意 |
| `idea_save` | 「存 idea: XX」「记 idea: XX」「保存 idea: XX」 | 任意 |
| `idea_list` | 「我的 idea」「今日 idea」「idea 库」「有什么 idea」「idea list」 | 任意 |
| `idea_done` | 「idea N 用了」「标 idea N」「done idea N」 | 任意 |
| `idea_remove` | 「删 idea N」「rm idea N」 | 任意 |
| `write_idx` | 1-9 (单个数字) | state=briefed |
| `next`(确认词) | 「ok」「继续」「好」「行」「next」 | 任意 |
| `next`(wrote 推进语) | 「制作配图」「生图」「出图」「画图」「配图」「做图」「下一步」「可以了」「通过」 | state=wrote → images.py |
| `next`(imaged 推进语) | 「推草稿」「推送草稿箱」「发草稿」「发布草稿」「图片可以」「通过了」 | state=imaged → publish.py |
| `revise` | 「改 XX」「加段 XX」「重写」「去掉 XX」 | state=wrote |
| `revise_image` | 「重做 cover」「换 chart-3」 | state=imaged |
| `republish` | 「重新排版」「重新发布」「重发」「重排」 | state=done |
| `reset` | 「pass」「跳过」「放弃」「reset」 | 任意 |

### 9.B 直拉 WeChat 草稿 HTML(终极调试)

当 WeChat 渲染跟你期待不一致 · 不要相信预览 · **直接看草稿存的真 HTML**:
```bash
set -a; source secrets/keys.env; set +a
venv/bin/python3 -c "
import sys, os
sys.path.insert(0, 'toolkit')
from wechat_api import get_access_token
from publisher import get_draft

mid = '<贴最新 media_id>'  # 从 output/session.yaml 的 draft_media_id 取
token = get_access_token(os.environ['WECHAT_APPID'], os.environ['WECHAT_APPSECRET'])
html = get_draft(token, mid)
open('/tmp/draft.html', 'w').write(html)
print(f'HTML 总长 {len(html)}')
print(f'含「智辰老师」: {\"智辰老师\" in html}')
print(f'含「宸的 AI 掘金笔记」: {\"宸的 AI 掘金笔记\" in html}')
"
open /tmp/draft.html  # 浏览器看实际 HTML
```

### 9.C 直接命令行跑 publish(绕过 bot · 调试用)

```bash
set -a; source secrets/keys.env; set +a
venv/bin/python3 scripts/workflow/publish.py
```

或更底层(直接 cli.py · 仍走 sanitize):
```bash
venv/bin/python3 toolkit/cli.py publish output/<某 md> \
    --engine md2wx --theme focus-navy \
    --cover output/images/cover.png --title "..."
```

---

## 10. 出新文章 · 完整流程速查

```
你: 教程: <主题>             # 或:写 <主题> · 选题: <主题> · 1-9(brief 后选号)
bot: 🛠️ 收到干货 idea ...     # 5-12 分钟
bot: ✓ 文章初稿就绪,已推预览
你: ok                       # 进生图
bot: 🎨 进入生图阶段          # 5-15 分钟
bot: ✓ 图片就绪,已推 5 张给你审
你: ok                       # 推草稿(自动 sanitize)
bot: 🚀 推到微信草稿箱
bot: ✓ 推送完成,已推提示给你  # 含 media_id 和 mp.weixin.qq.com 编辑提示
```

后台手动一步:`mp.weixin.qq.com` → 草稿箱 → 编辑 → 在 author-card 上方插「公众号」widget(WeChat 平台限制 · 必须手插一次)→ 发表。

---

## 11. 跨仓关系速查

| 仓 | 路径 | 关系 |
|---|---|---|
| **wewrite**(本仓) | `/Users/mahaochen/wechatgzh/wewrite` | 主 skill · 微信公众号长文 |
| md2wx(fork) | `/Users/mahaochen/wechatgzh/md2wx` | 排版引擎 · 改 author_card 时同步 `skill/src/preprocessor.ts` |
| **xwrite** | `/Users/mahaochen/xwrite` | X 平台高频运营 · 已 vendor 干货系列(personas + tutorial-thread) |
| baoyu-infographic | `~/.agents/skills/baoyu-infographic/` | 视觉系统源 · vendor 到 `references/visuals/` |
| aipickgold.com | API endpoint | md2wx 服务端 |

要让 xwrite 跟 wewrite 干货系列后续更新:`scripts/sync-to-xwrite.sh`(下次改了干货系列就跑一下,生成 review 报告)。
