# media-agent

公众号文章全流程 AI Skill —— 从热点抓取到草稿箱推送，一句话搞定。

适用于 [Claude Code](https://claude.ai/code) 的 skill 格式。安装后对 Claude 说「用 demo 的配置写一篇公众号文章」即可触发完整流程。

## 功能

| 步骤 | 能力 | 脚本/模块 |
|------|------|-----------|
| 热点抓取 | 微博 + 头条 + 百度实时热搜 | `scripts/fetch_hotspots.py` |
| SEO 评分 | 百度 + 360 搜索建议量化 | `scripts/seo_keywords.py` |
| 选题生成 | 10 选题 × 3 维度评分 | LLM + `references/topic-selection.md` |
| 框架生成 | 5 套差异化写作骨架 | LLM + `references/frameworks.md` |
| 文章写作 | 去 AI 痕迹 + 客户风格适配 | LLM + `references/writing-guide.md` |
| SEO 优化 | 标题 / 摘要 / 关键词 / 标签 | LLM + `references/seo-rules.md` |
| 视觉 AI | 封面 3 创意 + 内文 3-6 配图 | `toolkit/image_gen.py`（doubao / OpenAI） |
| 排版发布 | Markdown → 微信内联样式 HTML → 草稿箱 | `toolkit/cli.py` |
| 效果复盘 | 微信数据分析 API 回填阅读数据 | `scripts/fetch_stats.py` |
| Playbook 学习 | 从人工修改中提取风格规律 | `scripts/learn_edits.py` |

## 安装

### 作为 Claude Code Skill

```bash
# 方式 1：直接引用目录
# 在你的 Claude Code 设置中添加 skill 路径

# 方式 2：复制到 skills 目录
cp -r media-agent ~/.claude/skills/media-agent
```

### 安装 Python 依赖

```bash
cd media-agent
pip install -r requirements.txt
```

### 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入：

- **微信公众号** `appid` / `secret`（发布和数据统计需要）
- **图片生成 API key**（doubao-seedream 或 OpenAI DALL-E）

## 目录结构

```
media-agent/
├── SKILL.md              # Skill 主文件（Claude 读取并执行）
├── config.example.yaml   # 配置模板
├── requirements.txt      # Python 依赖
│
├── scripts/              # 数据采集脚本
│   ├── fetch_hotspots.py   # 多平台热点抓取
│   ├── seo_keywords.py     # SEO 关键词分析
│   ├── fetch_stats.py      # 微信文章数据回填
│   ├── build_playbook.py   # 从历史文章生成 Playbook
│   └── learn_edits.py      # 学习人工修改
│
├── toolkit/              # Markdown→微信 工具链
│   ├── cli.py              # CLI 入口（preview / publish / themes）
│   ├── converter.py        # Markdown→内联样式 HTML
│   ├── theme.py            # YAML 主题系统
│   ├── publisher.py        # 微信草稿箱 API
│   ├── wechat_api.py       # 微信 access_token / 图片上传
│   ├── image_gen.py        # AI 图片生成（多 provider）
│   └── themes/             # 4 套预置排版主题
│
├── references/           # Claude 按需读取的参考文档
│   ├── topic-selection.md   # 选题评估规则
│   ├── frameworks.md        # 5 种写作框架
│   ├── writing-guide.md     # 写作规范 + 去 AI 痕迹
│   ├── seo-rules.md         # 微信 SEO 规则
│   ├── visual-prompts.md    # 视觉 AI 提示词规范
│   ├── wechat-constraints.md # 微信平台技术限制
│   └── style-template.md   # 客户配置模板说明
│
├── clients/              # 客户配置（每个客户一个目录）
│   └── demo/               # 示例客户
│       ├── style.yaml        # 风格配置
│       └── history.yaml      # 发布历史
│
└── output/               # 生成的文章输出目录
```

## 客户配置

每个客户是 `clients/{name}/` 下的一个目录。核心配置文件是 `style.yaml`：

```yaml
name: "客户名称"
industry: "行业"
topics:
  - "方向1"
  - "方向2"
tone: "写作风格描述"
theme: "professional-clean"
```

详见 `references/style-template.md` 或复制 `clients/demo/style.yaml` 修改。

## 图片生成

支持两种 provider，通过 `config.yaml` 切换：

| Provider | 适用场景 | 配置 |
|----------|---------|------|
| `doubao` | 中文提示词效果好，国内访问快 | [火山引擎 Ark](https://console.volcengine.com/ark) API key |
| `openai` | DALL-E 3，国际通用 | OpenAI API key |

CLI 独立使用：

```bash
python3 toolkit/image_gen.py --prompt "描述" --output cover.png --size cover
python3 toolkit/image_gen.py --prompt "描述" --output img.png --provider openai
```

## 排版主题

| 主题 | 风格 |
|------|------|
| `professional-clean` | 专业简洁（默认） |
| `tech-modern` | 科技风（蓝紫渐变） |
| `warm-editorial` | 暖色编辑风 |
| `minimal` | 极简黑白 |

预览主题：`python3 toolkit/cli.py themes`

独立排版：`python3 toolkit/cli.py preview article.md --theme tech-modern`

## Toolkit 独立使用

即使不用 Claude Code，toolkit 也可以独立使用：

```bash
# 预览 Markdown → 微信 HTML
python3 toolkit/cli.py preview article.md --theme professional-clean

# 发布到微信草稿箱
python3 toolkit/cli.py publish article.md --cover cover.png --title "文章标题"

# 抓热点
python3 scripts/fetch_hotspots.py --limit 20

# SEO 分析
python3 scripts/seo_keywords.py --json "AI大模型" "科技股"
```

## License

MIT
