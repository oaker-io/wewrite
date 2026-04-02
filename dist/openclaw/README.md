# WeWrite

公众号文章全流程 AI Skill —— 从热点抓取到草稿箱推送，一句话搞定。

兼容 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 和 [OpenClaw](https://github.com/anthropics/openclaw) 的 skill 格式。安装后说「写一篇公众号文章」即可触发完整流程。

## 它能做什么

```
"写一篇公众号文章"
  → 抓热点 → 选题评分 → 框架选择 → 素材采集 → 内容增强
  → 写作（真实信息锚定 + 风格注入 + 编辑锚点）
  → SEO优化 → AI配图 → 微信排版 → 推送草稿箱
```

首次使用时会引导你设置公众号风格，之后每次只需一句话。生成的文章带有 2-3 个编辑锚点——花 3-5 分钟加入你自己的话，文章就会从"AI 初稿"变成"你的作品"。

## 核心能力

| 能力 | 说明 | 实现 |
|------|------|------|
| 热点抓取 | 微博 + 头条 + 百度实时热搜 | `scripts/fetch_hotspots.py` |
| SEO 评分 | 百度 + 360 搜索量化评分 | `scripts/seo_keywords.py` |
| 选题生成 | 10 选题 × 3 维度评分 + 历史去重 | `references/topic-selection.md` |
| 素材采集 | WebSearch 真实数据/引述/案例 | SKILL.md Step 3.2 |
| 框架生成 | 7 套写作骨架（痛点/故事/清单/对比/热点解读/纯观点/复盘） | `references/frameworks.md` |
| 内容增强 | 按框架类型自动匹配：角度发现/密度强化/细节锚定/真实体感 | `references/content-enhance.md` |
| 文章写作 | 真实信息锚定 + 风格注入 + 编辑锚点 | `references/writing-guide.md` |
| SEO 优化 | 标题策略 / 摘要 / 关键词 / 标签 | `references/seo-rules.md` |
| 视觉 AI | 封面 3 创意 + 内文 3-6 配图 | `toolkit/image_gen.py` |
| 排版发布 | 16+ 主题 + 微信兼容修复 + 暗黑模式 | `toolkit/cli.py` |
| 效果复盘 | 微信数据分析 API 回填阅读数据 | `references/effect-review.md` |
| 范文风格库 | SICO 式 few-shot：从你的文章提取风格指纹，写作时注入 | `scripts/extract_exemplar.py` |
| 风格飞轮 | 学习你的修改，越用越像你 | `references/learn-edits.md` |
| 排版学习 | 从任意公众号文章 URL 提取排版主题 | `scripts/learn_theme.py` |

## 写作人格

像选排版主题一样选写作风格。在 `style.yaml` 里一行配置：

```yaml
writing_persona: "midnight-friend"
```

| 人格 | 适合 | 风格特点 |
|------|------|---------|
| `midnight-friend` | 个人号/自媒体 | 极度口语化、高自我怀疑、每段第一人称 |
| `warm-editor` | 生活/文化/情感 | 温暖叙事、故事嵌套数据、柔和情绪弧 |
| `industry-observer` | 行业媒体/分析 | 中性分析、数据先行、稳中带刺 |
| `sharp-journalist` | 新闻/评论 | 犀利简洁、数据驱动、强观点 |
| `cold-analyst` | 财经/投研 | 冷静克制、逻辑链条、风险意识强 |

每个人格定义了语气浓度、数据呈现方式、情绪弧线、不确定性表达模板等参数。详见 `personas/` 目录。

## 内容质量

WeWrite 的目标不是"骗过 AI 检测"，而是**写出值得读的文章**。核心机制：

1. **内容增强**：根据框架类型自动执行不同策略——热点文找反直觉角度、干货文强化信息密度、故事文锚定真实细节、对比文注入真实用户体感
2. **素材采集**：自动 WebSearch 真实数据/引述/案例，锚定在文章中（不编造）
3. **范文风格库**：导入你已发布的文章，写作时自动注入你的风格指纹（句长节奏、情绪表达、转折方式）
4. **编辑锚点**：在 2-3 个关键位置标记"在这里加一句你自己的话"
5. **学习飞轮**：每次你编辑后说"学习我的修改"，下次初稿更接近你的风格
6. **文章自检**：说"检查一下"，查看生成档案（用了什么框架/人格/策略）+ 质量检查（具体到哪句话该怎么改）

## 排版引擎

### 16 个主题

```bash
# 浏览器内预览所有主题（并排对比 + 一键复制）
python3 toolkit/cli.py gallery

# 列出主题名称
python3 toolkit/cli.py themes
```

| 类别 | 主题 |
|------|------|
| 通用 | `professional-clean`（默认）、`minimal`、`newspaper` |
| 科技 | `tech-modern`、`bytedance`、`github` |
| 文艺 | `warm-editorial`、`sspai`、`ink`、`elegant-rose` |
| 商务 | `bold-navy`、`minimal-gold`、`bold-green` |
| 风格 | `bauhaus`、`focus-red`、`midnight` |

所有主题均支持微信暗黑模式。

### 微信兼容性自动修复

| 问题 | 自动修复 |
|------|---------|
| 外链被屏蔽 | 转为上标编号脚注 + 文末参考链接 |
| 中英混排无间距 | CJK-Latin 自动加空格 |
| 加粗标点渲染异常 | 标点移到 `</strong>` 外 |
| 原生列表不稳定 | `<ul>/<ol>` 转样式化 `<section>` |
| 暗黑模式颜色反转 | 注入 `data-darkmode-*` 属性 |
| `<style>` 被剥离 | 所有 CSS 内联注入 |

### 容器语法

````markdown
:::dialogue
你好，请问这个功能怎么用？
> 很简单，直接在 Markdown 里写就行。
:::

:::timeline
**2024 Q1** 立项启动
**2024 Q3** MVP 上线
:::

:::callout tip
提示框，支持 tip / warning / info / danger。
:::

:::quote
好的排版不是让读者注意到设计，而是让读者忘记设计。
:::
````

## 安装

**Claude Code**：

```bash
git clone --depth 1 https://github.com/oaker-io/wewrite.git ~/.claude/skills/wewrite
cd ~/.claude/skills/wewrite && pip install -r requirements.txt
```

**OpenClaw**：

```bash
git clone --depth 1 https://github.com/oaker-io/wewrite.git ~/.openclaw/skills/wewrite
cd ~/.openclaw/skills/wewrite && pip install -r requirements.txt
```

安装后 skill 会在每次运行时自动检查新版本。有更新时说"更新"即可升级。

### 配置（可选）

```bash
cp config.example.yaml config.yaml
```

填入微信公众号 `appid`/`secret`（推送需要）和图片 API key（生图需要）。不配也能用——自动降级为本地 HTML + 输出图片提示词。

## 快速开始

```
你：写一篇公众号文章
你：写一篇关于 AI Agent 的公众号文章
你：交互模式，写一篇关于效率工具的推文
你：帮我润色一下刚才那篇
你：学习我的修改                  → 飞轮学习
你：看看有什么主题                → 主题画廊
你：换成 sspai 主题               → 切换主题
你：看看文章数据怎么样            → 效果复盘
你：做一个小绿书                  → 图片帖（横滑轮播）
你：检查一下                        → 生成报告 + 质量自检
你：导入范文                        → 建立风格库
你：查看范文库                      → 查看已导入的范文
你：学习排版                        → 从公众号文章提取排版主题
```

## 目录结构

```
wewrite/
├── SKILL.md                  # 主管道（Step 1-8）
├── config.example.yaml       # API 配置模板
├── style.example.yaml        # 风格配置模板
├── writing-config.example.yaml # 写作参数模板
├── requirements.txt
│
├── dist/openclaw/            # OpenClaw 兼容版（CI 自动构建）
│
├── scripts/                  # 数据采集 + 诊断 + 构建
│   ├── fetch_hotspots.py       # 多平台热点抓取
│   ├── seo_keywords.py         # SEO 关键词分析
│   ├── fetch_stats.py          # 微信文章数据回填
│   ├── build_playbook.py       # 从历史文章生成 Playbook
│   ├── learn_edits.py          # 学习人工修改
│   ├── humanness_score.py      # 文章质量打分（11 项检测，供自检和 Step 5 使用）
│   ├── extract_exemplar.py      # 范文风格提取（SICO 式 few-shot 建库）
│   ├── learn_theme.py           # 从公众号文章 URL 提取排版主题
│   ├── diagnose.py             # 配置完备度检查
│   └── build_openclaw.py       # SKILL.md → OpenClaw 格式转换
│
├── toolkit/                  # Markdown → 微信工具链
│   ├── cli.py                  # CLI（preview / publish / gallery / themes / image-post / learn-theme）
│   ├── converter.py            # Markdown → 内联样式 HTML + 微信兼容修复
│   ├── theme.py                # YAML 主题引擎
│   ├── publisher.py            # 微信草稿箱 API + 小绿书图片帖
│   ├── wechat_api.py           # access_token / 图片上传
│   ├── image_gen.py            # AI 图片生成（doubao / OpenAI / Gemini）
│   └── themes/                 # 16+ 排版主题（含暗黑模式，可从文章学习新增）
│
├── personas/                 # 5 套写作人格预设（含朱雀实测数据）
│
├── references/               # Agent 按需加载
│   ├── writing-guide.md        # 写作规范 + 质量检查规则
│   ├── frameworks.md           # 7 种写作框架（痛点/故事/清单/对比/热点解读/纯观点/复盘）
│   ├── content-enhance.md     # 内容增强策略（角度发现/密度强化/细节锚定/真实体感）
│   ├── topic-selection.md      # 选题评估规则
│   ├── seo-rules.md            # 微信 SEO 规则
│   ├── visual-prompts.md       # 视觉 AI 提示词规范
│   ├── wechat-constraints.md   # 微信平台限制 + 自动修复
│   ├── style-template.md       # 风格配置字段 + 16 主题列表
│   ├── exemplar-seeds.yaml     # 通用人类写作模式种子（无范文库时的 fallback）
│   ├── exemplars/              # 用户范文风格库（自动生成，不入 git）
│   ├── onboard.md              # 首次设置流程
│   ├── learn-edits.md          # 学习飞轮流程
│   └── effect-review.md        # 效果复盘流程
│
├── output/                   # 生成的文章
├── corpus/                   # 历史语料（可选）
└── lessons/                  # 修改记录（自动生成）
```

运行时自动生成（不入 git）：`style.yaml`、`history.yaml`、`playbook.md`、`writing-config.yaml`、`references/exemplars/*.md`

## 工作流程

```
Step 1  环境检查 + 加载风格（不存在则 Onboard）
  ↓
Step 2  热点抓取 → 历史去重 + SEO → 选题
  ↓
Step 3  框架选择 → 素材采集（WebSearch 真实数据）→ 内容增强（按框架类型匹配策略）
  ↓
Step 4  维度随机化 → 范文风格注入 → 写作（内容增强约束 + 真实素材锚定 + 编辑锚点）→ 快速自检
  ↓
Step 5  SEO 优化 → 质量验证
  ↓
Step 6  视觉 AI（封面 + 内文配图）
  ↓
Step 7  预检 + 排版 + 发布（16 主题 + 微信兼容修复）
  ↓
Step 8  写入历史 → 回复用户（含编辑建议 + 飞轮提示）
```

默认全自动。说"交互模式"可在选题/框架/配图处暂停确认。

## Toolkit 独立使用

```bash
# Markdown → 微信 HTML
python3 toolkit/cli.py preview article.md --theme sspai

# 主题画廊
python3 toolkit/cli.py gallery

# 发布草稿箱
python3 toolkit/cli.py publish article.md --cover cover.png --title "标题"

# 小绿书/图片帖（横滑轮播，3:4 比例，最多 20 张）
python3 toolkit/cli.py image-post photo1.jpg photo2.jpg photo3.jpg -t "周末探店" -c "在望京发现的宝藏咖啡馆"

# 抓热点
python3 scripts/fetch_hotspots.py --limit 20

# SEO 分析
python3 scripts/seo_keywords.py --json "AI大模型" "科技股"

# 范文风格库
python3 scripts/extract_exemplar.py article.md              # 导入范文
python3 scripts/extract_exemplar.py *.md -s "你的公众号"     # 批量导入
python3 scripts/extract_exemplar.py --list                   # 查看范文库

# 文章质量检查
python3 scripts/humanness_score.py article.md --verbose

# 从公众号文章学习排版主题
python3 scripts/learn_theme.py https://mp.weixin.qq.com/s/xxxx --name my-style

# AI 图片生成
python3 toolkit/image_gen.py --prompt "描述" --output cover.png
python3 toolkit/image_gen.py --prompt "描述" --output cover.png --provider gemini
python3 toolkit/image_gen.py --prompt "描述" --output cover.png --model doubao-seedream-5-0-260128
```

## License

MIT
