# 视觉AI模块

## 你的任务

为文章生成两类视觉素材的 AI 绘图提示词：封面图（3 组差异化创意）和内文配图（3-6 张，按段落匹配）。

你不负责生成图片本身——你输出的是结构化的提示词文件 `output/{slug}-prompts.md`。用户主要走**路径 1**（ChatGPT Plus 网页粘贴）或**路径 2**（Gemini Advanced），API 配置好时也可走**路径 3**（自动调用 image_gen.py 批量生成）。

## 提示词文件（prompts.md）通用头部模板

每次生成 `{slug}-prompts.md`，**必须**在文件顶部使用下列模板（替换 `{...}` 占位符）：

```markdown
# 视觉提示词 · {文章标题}

**目标模型**：`gpt-image-1`（或用户 config.yaml 指定的模型）
**对应文章**：`{slug}.md`
**主题**：{主题名} · {cover_style 描述}

---

## 使用方式（路径 1 · ChatGPT Plus 网页，推荐）

1. 打开 chat.openai.com，对话里说「用 gpt-image-1 生成，16:9，提示词如下」然后粘贴下方任一组英文提示词
2. 下载生成的图片，**按下表命名**后放到 `output/images/`
3. 直接 `python3 toolkit/cli.py preview output/{slug}.md --theme {主题}` 看效果
4. 将来推送时 `python3 toolkit/cli.py publish output/{slug}.md` 会自动上传本地图到微信 CDN，无需手动处理

> **Gemini Advanced 用户（路径 2）**：同一份英文提示词可直接粘到 gemini.google.com 或 Google AI Studio，Imagen 4 英文表现强

## 文件名对照表

| 位置 | 存为文件名 |
|------|-----------|
| 封面（3 组创意选 1 组生成） | `cover.png` |
| 内文配图 1 | `chart-1.png` |
| 内文配图 2 | `chart-2.png` |
| 内文配图 3 | `chart-3.png` |
| ...依此类推 | `chart-N.png` |

---
```

头部之后，继续输出「实体提取」「封面图（3 组）」「视觉锚点」「内文配图（N 张）」四个部分。

---

## 一、封面图（3 组创意）

### 生成规则

每组创意走不同的视觉策略，确保差异化：

**创意 A: 直觉冲击型**
- 策略：用一个视觉隐喻直接表达文章核心观点
- 适合：热点类、观点类文章
- 风格：大胆、对比强烈、第一眼抓眼球

**创意 B: 氛围渲染型**
- 策略：营造一种情绪或场景氛围，引发好奇
- 适合：故事类、情绪类文章
- 风格：细腻、有质感、让人想点进去看

**创意 C: 信息图表型**
- 策略：用简洁的图形/图标/数据可视化传递信息
- 适合：干货类、清单类、测评类文章
- 风格：简洁、专业、一眼看懂文章主题

### 提示词格式

每组输出：

````markdown
### 封面创意 A: {创意名称}
- **存为**：`images/cover.png`（只需要从 A/B/C 三组中选 1 组生成，统一存为 cover.png）
- 视觉描述：{详细的画面描述，100-150字}
- 色调：{主色+辅色}
- 构图：{横版 16:9，主体位置、留白位置}
- 文字区域：{标题放在什么位置，需要留多大空间}

**英文提示词**（粘贴到 ChatGPT/Gemini）：

```
{英文提示词，适配 gpt-image-1 / Imagen 4，包含风格、构图、色调、光影，显式加 "16:9 horizontal composition, no text no letters no words, clean space for title overlay"}
```

- 适配工具建议：{gpt-image-1（文字渲染强）/ Imagen 4（氛围表现好）/ Midjourney / DALL-E 3}

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com
````

### 实体锚定（必须）

生成提示词之前，先从文章中提取 3-5 个**具体实体**：

- 人物/角色（"短剧导演"、"AI 工程师"）
- 产品/技术（"Sora"、"数字人"、"大模型"）
- 场景（"拍摄片场"、"手机竖屏播放"、"服务器机房"）
- 数据/趋势（"成本曲线下降"、"90% 亏损率"）

**硬规则**：
- 每条提示词必须包含至少 2 个文章实体
- 禁止用"科技感"、"未来感"、"商务感"、"数据背景"等泛化词**替代**具体内容——这些词可以作为风格修饰，但不能作为画面主体
- 自检方法：如果一个没读过文章的人看到这条提示词，能猜出文章大概在讲什么吗？不能 → 重写

**反例** → **正例**：
- ❌ "蓝色科技背景，数据流动，未来感" → ✅ "AI 生成的短剧角色走出手机屏幕，背景是废弃的真人拍摄片场，蓝色冷光"
- ❌ "商务办公场景，专业氛围" → ✅ "一个仓库货架上堆满退货包裹，旁边屏幕显示飙升的退货率曲线"

### 提示词撰写要点

- 始终指定 `16:9 aspect ratio, horizontal composition`
- 避免生成文字（AI 绘图工具生成的文字通常是乱码）
- 指定 `no text, no letters, no words` 防止出现乱码文字
- 为标题留出干净的空间：`clean space on the left/right/bottom for text overlay`
- 色调与客户 style.yaml 的 cover_style 对齐
- 风格关键词要具体：不说"好看"，说"flat design, soft gradient, minimalist"

---

## 风格锚定

封面确认后，**立即提取视觉锚点**，后续所有内文配图必须复用：

```
视觉锚点：
- 色板：{封面的主色 hex + 辅色 hex，如 #2563EB + #F97316}
- 风格关键词：{封面的风格描述，如 "flat illustration, minimalist, bold outlines"}
- 画面调性：{冷调/暖调/中性}
```

**规则**：
- 每条内文配图提示词的末尾，必须附加视觉锚点中的色板和风格关键词
- 如果封面是暖调，内文配图不能突然切换为冷调科技风（反之亦然）
- 视觉锚点在整篇文章的所有配图中保持一致

---

## 二、内文配图（3-6 张）

### 分析流程

写作完成后（Step 5 终稿），按以下步骤分析配图位置：

**第一步：提取结构**
- 列出所有 H2 标题及其下属段落
- 统计每个论点段落的字数和核心内容

**第二步：逐个论点判断**

对每个 H2 论点，判断是否需要配图：

| 需要配图（优先级高→低） | 不需要配图 |
|-------------------------|-----------|
| 有具体数据/统计 → 信息图强化 | 纯观点论述、篇幅短（<200字） |
| 有场景描写 → 画面还原 | 已经有引用块或代码块（视觉已丰富） |
| 转折/高潮处 → 视觉冲击 | 紧接着另一张配图（间距不足300字） |
| 长段落后（>400字无图） → 节奏调节 | 结尾 CTA 段落 |

**第三步：确定图片类型**

根据段落内容，为每张配图选择最匹配的类型：

| 类型 | 适用内容 | 核心构图 |
|------|---------|---------|
| infographic | 数据、统计、指标对比 | 区域分块 + 标签标注 |
| scene | 叙事场景、情绪渲染、人物故事 | 焦点主体 + 氛围光影 |
| flowchart | 流程、步骤、工作流 | 步骤节点 + 连接箭头 |
| comparison | 两个方案/观点对比 | 左右分栏 + 分隔线 |
| framework | 概念模型、架构关系 | 层级节点 + 关系连线 |
| timeline | 时间线、发展历程 | 时间轴 + 里程碑标记 |

**第四步：确定位置**
- 配图插入在对应段落**之后**（不是之前）
- 具体到"H2 XX 下的第 N 段之后"

**约束规则**：
- 总数 3-6 张（1500字→3张，2000字→4张，2500字→5-6张）
- 相邻两张配图之间至少间隔 300 字
- 不要在文章第一段之前放配图
- 不要在结尾 CTA 段落放配图

### 结构化提示词模板

根据图片类型，使用对应的结构化模板生成提示词。**禁止自由文本描述**——所有提示词必须填写模板的每个字段。

#### infographic（信息图）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：infographic
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Layout: {grid / radial / hierarchical}
Zones:
  - Zone 1: {具体数据点，用文章真实数字}
  - Zone 2: {对比/趋势，用文章真实数字}
  - Zone 3: {结论/要点}
Labels: {文章中的真实数字、术语、指标名}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean infographic, no text
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

#### scene（场景）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：scene
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Focal Point: {画面主体，必须是文章实体}
Atmosphere: {光影、环境、时间}
Mood: {情绪基调}
Color Temperature: {warm / cool / neutral，与视觉锚点一致}
Style: {视觉锚点风格关键词}, no text no letters
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

#### flowchart（流程图）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：flowchart
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Layout: {left-right / top-down / circular}
Steps:
  1. {步骤名} — {简述}
  2. {步骤名} — {简述}
  3. {步骤名} — {简述}
Connections: {箭头方向、决策分支}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean diagram, no text
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

#### comparison（对比图）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：comparison
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Left Side — {选项A名称}:
  - {要点1}
  - {要点2}
Right Side — {选项B名称}:
  - {要点1}
  - {要点2}
Divider: {分隔线样式}
Colors: {视觉锚点色板，左右各用一个主色}
Style: {视觉锚点风格关键词}, split layout, no text
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

#### framework（架构图）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：framework
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Structure: {hierarchical / network / matrix}
Nodes:
  - {概念1} — {角色}
  - {概念2} — {角色}
  - {概念3} — {角色}
Relationships: {节点间如何连接}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean diagram, no text
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

#### timeline（时间线）

````markdown
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：timeline
- **存为**：`images/chart-{序号}.png`
- 对应内容：{1句话概括}

**结构化模板**：
```
Direction: {horizontal / vertical}
Events:
  - {时间点1}: {里程碑}
  - {时间点2}: {里程碑}
  - {时间点3}: {里程碑}
Markers: {视觉标记样式}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean timeline, no text
Aspect: 16:9
```

**英文提示词**(粘贴到 ChatGPT/Gemini):
```
{根据上方结构化模板生成的完整英文提示词}
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

### 内文配图通用要求

- 尺寸统一 **16:9 横版**（image_gen.py --size article）
- **视觉锚定**：每条提示词的 Colors 和 Style 字段必须引用封面提取的视觉锚点
- 实体锚定规则同封面——每条提示词至少包含 2 个文章实体
- 不要太复杂——手机屏幕上看，简洁的图比复杂的图好
- **提示词语言**：按 `config.yaml` 的 provider 自动切换（见 SKILL.md Step 6 映射表）；路径 1 默认走 openai/gemini → 英文提示词
- 每张图都提供一个**免费图库备选关键词**，以防生图效果不佳
- **命名约定**：每张配图的「存为」字段按顺序 `images/chart-1.png`、`images/chart-2.png`... 与文章 markdown 里的占位符一一对应

---

## 三、辅助功能

### 提示词修改

如果用户说"封面创意 A 我喜欢方向但是想要更暖的色调"，只修改对应创意的提示词，其他不变。

### 创意切换

如果用户说"封面我想要更多选择"，在 A/B/C 三种策略的基础上，为用户偏好的策略再出 2 个变体（比如"直觉冲击型的变体 1 和变体 2"）。

### 配图场景调整

如果用户说"第 3 张配图位置不对"或"这段不需要图"，按用户要求增删调整。

---

## 输出示例

完整 prompts.md 文件结构应如下（**头部模板必须完整复用本文档开头的「提示词文件通用头部模板」**）：

````markdown
# 视觉提示词 · 深夜看完 Cursor 的 500 亿估值...

**目标模型**：`gpt-image-1`
**对应文章**：`2026-04-18-ai-coding-non-consensus.md`
**主题**：professional-clean · 简洁科技感 · 蓝色调 · 扁平化

---

## 使用方式（路径 1 · ChatGPT Plus 网页，推荐）

（省略，按头部模板原样输出）

## 文件名对照表

| 位置 | 存为文件名 |
|------|-----------|
| 封面（A/B/C 选 1） | `cover.png` |
| 内文配图 1 | `chart-1.png` |
| 内文配图 2 | `chart-2.png` |
| 内文配图 3 | `chart-3.png` |
| 内文配图 4 | `chart-4.png` |

---

## 实体提取
- Cursor / Claude Code / GitHub Copilot
- Anthropic / OpenAI
- $20B / $25B / 42% / 18% / 70%

## 封面图（3 组创意）

### 创意 A: 天平失衡（直觉冲击型）
- **存为**：`images/cover.png`（A/B/C 三选一生成，统一存为 cover.png）
- 视觉描述：天平左托盘放 "Cursor $20B"，右托盘放 "Claude Code $25B"，向右倾斜。
- 色调：深蓝 #0F172A + 青色 #06B6D4 + 暖金 #F59E0B
- 构图：16:9 横版，天平居中，下方 25% 留白
- 文字区域：下方水平长条

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
A large minimalist balance scale in a dark navy environment (#0F172A). Left pan holds a glowing cyan plaque labeled "Cursor $20B ARR"; right pan holds a brighter plaque labeled "Claude Code $25B ARR", scale tilts right. Flat minimalist tech aesthetic, 16:9 horizontal composition, clean empty space at bottom 25% for title overlay, no decorative text.
```

- 适配工具建议：gpt-image-1（文字渲染强）/ Imagen 4

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

## 视觉锚点
色板 #0F172A + #06B6D4 + #F59E0B，风格 "flat design, minimalist infographic"

## 内文配图（4 张）

### 配图 1: 位于「Cursor 是真的在飞」段后
- 类型：timeline
- **存为**：`images/chart-1.png`
- 对应内容：Cursor ARR 从 Nov 2025 到 Q2 2026 的里程碑

**结构化模板**：
```
Direction: horizontal left-to-right
Events:
  - "Nov 2025": $10B ARR
  - "Feb 2026": $20B ARR
  - "Q2 2026": $50B valuation
Colors: navy #0F172A + cyan #06B6D4 + amber #F59E0B
Style: flat minimalist infographic, no text
Aspect: 16:9
```

**英文提示词**（粘贴到 ChatGPT/Gemini）：
```
A clean horizontal timeline on dark navy background (#0F172A). Three glowing milestone markers in cyan labeled "Nov 2025 · $10B ARR", "Feb 2026 · $20B ARR", "Q2 2026 · $50B valuation". Flat minimalist, 16:9.
```

> **Gemini Advanced 用户**：同一份英文提示词可直接粘到 gemini.google.com

- 备选方案：Unsplash "startup growth timeline"
````
