---
name: wewrite
description: |
  微信公众号内容全流程助手：热点抓取 → 选题 → 框架 → 写作 → SEO/去AI痕迹 → 视觉AI → 排版推送草稿箱。
  触发关键词：公众号、推文、微信文章、微信推文、草稿箱、微信排版、选题、热搜、
  热点抓取、封面图、配图、写公众号、写一篇、主题画廊、排版主题、容器语法。
  也覆盖：markdown 转微信格式、学习用户改稿风格、文章数据复盘、风格设置、
  主题预览/切换、:::dialogue/:::timeline/:::callout 容器语法。
  不应被通用的"写文章"、blog、邮件、PPT、抖音/短视频、网站 SEO 触发——
  需要有公众号/微信等明确上下文。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - WebSearch
  - WebFetch
---

# WeWrite — 公众号文章全流程

## 行为声明

**角色**：用户的公众号内容编辑 Agent。

**模式**：
- **默认全自动**——一口气跑完 Step 1-8，不中途停下。只在出错时停。
- **交互模式**——用户说"交互模式"/"我要自己选"时，在选题/框架/配图处暂停。

**降级原则**：每一步都有降级方案。Step 1 检测到的降级标记（`skip_publish`、`skip_image_gen`）在后续 Step 自动生效，不重复报错。

**完成协议**：
- **DONE** — 全流程完成，文章已保存/推送
- **DONE_WITH_CONCERNS** — 完成但部分步骤降级，列出降级项
- **BLOCKED** — 关键步骤无法继续（如 Python 依赖缺失且用户拒绝安装）
- **NEEDS_CONTEXT** — 需要用户提供信息才能继续（如首次设置需要公众号名称）

**路径约定**：本文档中 `{skill_dir}` 指本 SKILL.md 所在的目录（即 WeWrite 的根目录）。

**Onboard 例外**：Onboard 是交互式的（需要问用户问题），不受"全自动"约束。Onboard 完成后回到全自动管道。

**辅助功能**（按需加载，不在主管道内）：
- 用户说"重新设置风格" → `读取: {skill_dir}/references/onboard.md`
- 用户说"学习我的修改" → `读取: {skill_dir}/references/learn-edits.md`
- 用户说"看看文章数据" → `读取: {skill_dir}/references/effect-review.md`

---

## 主管道（Step 1-8）

### Step 1: 环境 + 配置

**1a. 环境检查**（静默通过或引导修复）：

```bash
python3 -c "import markdown, bs4, cssutils, requests, yaml, pygments, PIL" 2>&1
```

| 检查项 | 通过 | 不通过 |
|--------|------|--------|
| `config.yaml` 存在 | 静默 | 引导创建，或设 `skip_publish = true` |
| Python 依赖 | 静默 | 提供 `pip install -r requirements.txt` |
| `wechat.appid` + `secret` | 静默 | 设 `skip_publish = true` |
| `image.api_key` | 静默 | 设 `skip_image_gen = true` |

**1b. 加载风格**：

```
检查: {skill_dir}/style.yaml
```

- 存在 → 提取 `name`、`topics`、`tone`、`voice`、`blacklist`、`theme`、`cover_style`、`author`、`content_style`
- 不存在 → `读取: {skill_dir}/references/onboard.md`，完成后回到 Step 1

如果用户直接给了选题 → 跳到 Step 3（仍需框架选择和素材采集，不可跳过）。

---

### Step 2: 选题

**2a. 热点抓取**：

```bash
python3 {skill_dir}/scripts/fetch_hotspots.py --limit 30
```

**降级**：脚本报错 → WebSearch "今日热点 {topics第一个垂类}"

**2b. 历史去重 + SEO**：

```
读取: {skill_dir}/history.yaml（不存在则跳过）
```

```bash
python3 {skill_dir}/scripts/seo_keywords.py --json {关键词}
```

**降级**：SEO 脚本报错 → LLM 判断

**2c. 生成 10 个选题**：

```
读取: {skill_dir}/references/topic-selection.md
```

每个选题含标题、评分、点击率潜力、SEO 友好度、推荐框架。近 7 天已写的关键词降分。

- 自动模式 → 选最高分
- 交互模式 → 展示 10 个，等用户选

---

### Step 3: 框架 + 素材

**3a. 框架选择**：

```
读取: {skill_dir}/references/frameworks.md
```

5 套框架（痛点/故事/清单/对比/热点解读），自动选推荐指数最高的。

**3b. 素材采集（关键——决定能否通过 AI 检测）**：

纯 LLM 生成的内容无论技巧多好，底层 token 分布仍是 AI 的。通过检测的文章都建立在真实外部信息源之上。

```
WebSearch: "{选题关键词} site:36kr.com OR site:mp.weixin.qq.com OR site:zhihu.com"
WebSearch: "{选题关键词} 数据 报告 2025 2026"
```

采集 5-8 条真实素材（具名来源 + 具体数据/引述/案例）。**禁止编造**。

**降级**：WebSearch 无结果或不可用 → 用 LLM 训练数据中可验证的公开信息。但需告知用户："素材采集未能使用 WebSearch，文章的 AI 检测通过率会降低。建议在编辑锚点处多加入你自己的内容。"

---

### Step 4: 写作

```
读取: {skill_dir}/references/writing-guide.md
读取: {skill_dir}/playbook.md（如果存在，逐条执行，优先于 writing-guide）
读取: {skill_dir}/history.yaml（最近 3 篇的 dimensions 字段）
```

**4a. 维度随机化**：从 writing-guide.md 第 7 层维度池随机激活 2-3 个维度，对比历史去重。

**4b. 加载写作人格**：

```
读取: {skill_dir}/personas/{style.yaml 的 writing_persona 字段}.yaml
如果 style.yaml 没有 writing_persona 字段 → 默认 midnight-friend
```

人格文件定义了：语气浓度、数据呈现方式、情绪弧线、段落节奏、不确定性表达模板等。作为 Step 4c 的硬性约束执行。

**优先级**：playbook.md > persona > writing-guide.md。writing-guide 是底线（禁用词等），persona 在此基础上特化风格参数，playbook 是用户个性化的最终覆盖。

**4c. 写文章**：
- H1 标题（20-28 字） + H2 结构，1500-2500 字
- 真实素材锚定：Step 3b 的素材分散嵌入各 H2 段落
- **写作人格**：按 4b 加载的人格参数写作（数据呈现方式、个人声音浓度、不确定性表达等）
- 7 层去 AI 痕迹规则在初稿阶段全部生效
- 2-3 个编辑锚点：`<!-- ✏️ 编辑建议：在这里加一句你自己的经历/看法 -->`
- 可选容器语法：`:::dialogue`、`:::timeline`、`:::callout`、`:::quote`

保存到 `{skill_dir}/output/{date}-{slug}.md`

---

### Step 5: SEO + 验证

```
读取: {skill_dir}/references/seo-rules.md
```

**5a. SEO**：3 个备选标题 + 摘要（≤54 字）+ 5 标签 + 关键词密度优化

**5b. 去 AI 逐层验证**（writing-guide.md 自检清单，每项必须通过）：

| # | 检查项 | 标准 |
|---|--------|------|
| 0 | 真实信息锚定 | 每个 H2 至少 1 条真实素材，零编造 |
| 1 | 禁用词 | 命中数 = 0 |
| 2 | 词汇温度 | 冷/温/热/野 ≥ 3 种 |
| 3 | 破句 | ≥ 3 处 |
| 4 | 信息密度 | 高密度段后跟低密度段 |
| 5 | 连贯性打破 | ≥ 1 处跑题再拉回 |
| 6 | 情绪弧线 | ≥ 1 高点 + ≥ 1 犹豫 |
| 7 | 维度贯穿 | 激活维度全文可见 |
| 8 | 段落节奏 | 无连续 2 个相近长度段落 |

不通过 → 定向重写该段落。3 次仍不过 → 标注跳过。

---

### Step 6: 视觉 AI

**如果 `skip_image_gen = true`** → 只执行 6a。

```
读取: {skill_dir}/references/visual-prompts.md
```

**6a.** 分析文章结构，生成封面 3 组创意 + 内文 3-6 张配图提示词。

**6b.** 调用 image_gen.py 生成图片，替换 Markdown 占位符。

**降级**：生图失败 → 输出提示词，继续。

---

### Step 7: 预检 + 排版 + 发布

**7a. Metadata 预检**（发布前必须通过）：

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| H1 标题 | 存在且 5-64 字节 | 自动修正或提示用户 |
| 摘要 | 存在且 ≤ 120 UTF-8 字节 | converter 自动生成 |
| 封面图 | 推送模式下需要 | 无封面则警告，仍可推送（微信会显示默认封面） |
| 正文字数 | ≥ 200 字 | 警告"内容过短，微信可能不收录" |
| 图片数量 | ≤ 10 张 | 超出则移除末尾多余图片 |

预检全部通过后才进入排版。

**7b. 排版 + 发布**：

**如果 `skip_publish = true`** → 直接走 preview。

```
读取: {skill_dir}/references/wechat-constraints.md
```

Converter 自动处理：CJK 加空格、加粗标点外移、列表转 section、外链转脚注、暗黑模式、容器语法。

```bash
# 发布
python3 {skill_dir}/toolkit/cli.py publish {markdown} --cover {cover} --theme {theme} --title "{title}"

# 降级：本地预览
python3 {skill_dir}/toolkit/cli.py preview {markdown} --theme {theme} --no-open -o {output}.html
```

---

### Step 8: 收尾

**8a. 写入历史**（推送成功或降级都要写，文件不存在则创建）：

```yaml
# → {skill_dir}/history.yaml
- date: "{日期}"
  title: "{标题}"
  topic_source: "热点抓取"  # 或 "用户指定"
  topic_keywords: ["{词1}", "{词2}"]
  framework: "{框架}"
  word_count: {字数}
  media_id: "{id}"  # 降级时 null
  writing_persona: "{人格名}"
  dimensions:
    - "{维度}: {选项}"
  stats: null
```

**8b. 回复用户**：

- 最终标题 + 2 备选 + 摘要 + 5 标签 + media_id
- 编辑建议："文章有 2-3 个编辑锚点，建议花 3-5 分钟加入你自己的话，效果更好。"
- 飞轮提示："编辑完成后说**'学习我的修改'**，下次初稿会更接近你的风格。"

**8c. 后续操作**：

| 用户说 | 动作 |
|--------|------|
| 润色/缩写/扩写/换语气 | 编辑文章 |
| 封面换暖色调 | 重新生图 |
| 用框架 B 重写 | 回到 Step 4 |
| 换一个选题 | 回到 Step 2c |
| 看看有什么主题 | `python3 {skill_dir}/toolkit/cli.py gallery` |
| 换成 XX 主题 | 重新渲染 |
| 看看文章数据 | `读取: {skill_dir}/references/effect-review.md` |
| 学习我的修改 | `读取: {skill_dir}/references/learn-edits.md` |
| 做一个小绿书/图片帖 | `python3 {skill_dir}/toolkit/cli.py image-post img1.jpg img2.jpg -t "标题"` |

---

## 错误处理

| 步骤 | 降级 |
|------|------|
| 环境检查 | 逐项引导，设降级标记 |
| 热点抓取 | WebSearch 替代 |
| 选题为空 | 请用户手动给选题 |
| SEO 脚本 | LLM 判断 |
| 素材采集（WebSearch） | LLM 训练数据中可验证的公开信息 |
| 维度随机化 | history 空时跳过去重 |
| Persona 文件不存在 | 回退到 midnight-friend（默认） |
| 去 AI 验证 | 3 次重写不过则跳过该项 |
| 生图失败 | 输出提示词 |
| 推送失败 | 本地 HTML |
| 历史写入 | 警告不阻断 |
| 效果数据 | 告知等 24h |
| Playbook 不存在 | 用 writing-guide.md |
