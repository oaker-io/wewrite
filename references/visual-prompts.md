# 视觉AI模块

## 你的任务

为文章生成两类视觉素材的 AI 绘图提示词：封面图（3 组差异化创意）和内文配图（3-6 张，按段落匹配）。

你不负责生成图片本身——你输出的是结构化的提示词文件 `output/{slug}-prompts.md`。用户主要走**路径 1**（ChatGPT Plus 网页粘贴）或**路径 2**（Gemini Advanced），API 配置好时也可走**路径 3**（自动调用 image_gen.py 批量生成）。

## 配图模式（必须为每张图选择一种）

| 模式 | 适用 | 一张图承载 | 模板在哪 |
|------|------|-----------|---------|
| **`decorative`**（装饰型） | 封面、氛围渲染段、故事型文章 | 1 个概念（单一隐喻/场景/曲线） | 本文件「二、内文配图」6 种旧模板 |
| **`infographic-dense`**（高密度型） | 数据段、对比段、清单段、避坑段、干货型文章 | 6-7 个独立模块，每个带小标题 + 具体数据 | 本文件「三、infographic-dense」新模板 + `references/visuals/layouts/` + `references/visuals/styles/` |

**配图模式选择规则**（按文章框架自动决定，详见 SKILL.md Step 6.1b）：

- **热点解读型 / 纯观点型**：封面 `decorative`，内文 ≥50% `infographic-dense`
- **痛点型 / 清单型 / 对比型 / 复盘型**：封面 `decorative`，内文**全部** `infographic-dense`
- **故事型 / 情绪型**：封面 `decorative`，内文 `decorative`（多用 scene 类型）

核心原则：**干货段必须上高密度图**。用户反馈显示，单概念装饰图（天平/曲线）在公众号阅读体验下信息量不足，读者会跳过。

## 品牌露出规则（硬约束)

封面副标题、图脚、页脚、署名等**任何用户可见的品牌文字**,必须从 `style.yaml` 读取:

- **`author`** 字段 → 公众号顶部作者名(比如:智辰)
- **`brand`** 字段 → 封面副标题 / chart 页脚 / 视觉品牌(比如:宸的 AI 掘金笔记)

**禁止**在 prompts.md、overlay.json、图片提示词里**硬编码** `WeWrite` / `wewrite` —— 这些是工具名,不是用户的公众号品牌。如果 style.yaml 里没 brand 字段 → 问用户要 → 不要用工具名兜底。

反例 → 正例:
- ❌ `「WeWrite · AI Coding 观察 · 2026-04-19」`(把工具名当品牌露出)
- ✅ `「{style.yaml brand 字段} · 2026-04-19」`

## 提示词文件（prompts.md）通用头部模板

每次生成 `{slug}-prompts.md`，**必须**在文件顶部使用下列模板（替换 `{...}` 占位符）：

```markdown
# 视觉提示词 · {文章标题}

**目标模型**：`gpt-image-1.5` / `nano-banana-2`（Gemini 3 Flash Image，均对中文理解强、中文渲染准）
**对应文章**：`{slug}.md`
**主题**：{主题名} · {cover_style 描述}

---

## 使用方式（路径 1 · ChatGPT Plus 网页，推荐）

1. 打开 chat.openai.com，对话里说「用 gpt-image-1.5 生成，比例 2.35:1（封面）或 16:9（内文），提示词如下」然后粘贴下方**中文提示词**
2. 下载生成的图片，**按下表命名**后放到 `output/images/`
3. 直接 `python3 toolkit/cli.py preview output/{slug}.md --theme {主题}` 看效果
4. 将来推送时 `python3 toolkit/cli.py publish output/{slug}.md` 会自动上传本地图到微信 CDN，无需手动处理

> **Gemini Advanced 用户（路径 2）**：同一份中文提示词可直接粘到 gemini.google.com 或 Google AI Studio。nano-banana-2 对中文理解和中文字渲染都非常准，不需要翻英文。

## 比例规范（严格遵守）

| 用途 | 比例 | 对应微信位置 |
|------|------|-------------|
| **封面图** `cover.png` | **2.35:1**（如 1080×459 / 1200×510） | 公众号头条主封面 |
| **内文配图** `chart-N.png` | **16:9**（如 1280×720） | 正文段落间配图 |
| 小封面（可选） | 1:1（如 600×600） | 次条封面 |

## 文件名对照表

| 位置 | 存为文件名 |
|------|-----------|
| 封面（3 组创意选 1 组生成） | `cover.png` |
| 内文配图 1 | `chart-1.png` |
| 内文配图 2 | `chart-2.png` |
| 内文配图 3 | `chart-3.png` |
| ...依此类推 | `chart-N.png` |

## 📑 快速复制索引 · 看这张表就够了

按顺序,每段独立开一个 ChatGPT 对话(避免串图)。每段**只需要复制一个代码块**,本文档有明显 `━━━ 开始复制 ━━━` / `━━━ 结束复制 ━━━` 分隔线。

| 序号 | 提示词段 | 比例 | 跳转 | 下载后存为 |
|----|---------|------|------|----------|
| 1 | 封面 · A/B/C 三选一(推荐 C) | 2.35:1 | §1 | `output/images/cover.png` |
| 2 | chart-1 · {H2 标题 1} | 16:9 | §2 | `output/images/chart-1.png` |
| 3 | chart-2 · {H2 标题 2} | 16:9 | §3 | `output/images/chart-2.png` |
| ... | chart-N · {H2 标题 N} | 16:9 | §N+1 | `output/images/chart-N.png` |

---
```

头部之后，继续输出「实体提取」「封面图（§1,3 组并列)」「视觉锚点」「内文配图(§2 ~ §N)」四个部分。**每段必须用 `## §N · 段名` 独立小节,代码块前后必须用 `<!-- ━━━ 📋 开始复制 ━━━ -->` / `<!-- ━━━ ✂️ 结束复制 ━━━ -->` HTML 注释分隔符包围**,让用户一眼就知道"哪段要粘给 ChatGPT"。

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

### 提示词格式(每组独立 §1A / §1B / §1C 小节)

每组按下列结构输出到 prompts.md 里 3 个独立小节。注意:代码块前后必须加 HTML 注释分隔符 `<!-- ━━━ 📋 开始复制 · 封面 X ━━━ -->` / `<!-- ━━━ ✂️ 结束复制 ━━━ -->`,用户就靠这个定位要复制的区域。

````markdown
## §1A · 封面创意 A: {创意名称}

- **存为**:`output/images/cover.png`(A/B/C 三组中选 1 组生成,统一存为 cover.png)
- **中文主标题**(必须,画面上要渲染出来):「**{10-16 字简练高点击率标题}**」
- 视觉描述:{详细的画面描述,100-150字}
- 色调:{主色+辅色}
- 构图:**2.35:1 横幅**(微信公众号主封面规格),主体位置 + 标题区位置
- 标题区:{标题放画面的哪个位置,字号约占画面高度的 25-40%}

**对 ChatGPT 说**:「请生成一张 **2.35:1** 横幅图片,1080×459 像素,用于微信公众号头条封面,提示词如下:」然后复制下方整段:

<!-- ━━━ 📋 开始复制 · 封面 A ━━━ -->

```
{中文提示词,适配 gpt-image-1.5 / nano-banana-2。必须显式包含:
- 画面比例:「2.35:1 横幅比例,适合微信公众号头条封面」
- 中文主标题文字:「画面左上/右侧/下方渲染中文大标题『{标题}』,字号粗黑醒目」
- 视觉主体:{具体画面描述,含 ≥2 个文章实体}
- 风格关键词:{如"扁平科技风"、"胶片写实"、"手绘水彩"等}
- 色调 + 光影
- 装饰避让:「主标题区保持干净背景,不放杂乱元素干扰文字」}
```

<!-- ━━━ ✂️ 结束复制 ━━━ -->

**⬇ 下载生成的图 → 存为** `output/images/cover.png`

- 适配工具建议:**gpt-image-1.5(中文大字渲染最准)** / nano-banana-2(氛围好)

> **Gemini Advanced 用户**:同一份中文提示词直接粘到 gemini.google.com

---

## §1B · 封面创意 B: {创意名称}

(同上结构,代码块用 `<!-- ━━━ 📋 开始复制 · 封面 B ━━━ -->` 分隔)

---

## §1C · 封面创意 C: {创意名称}(推荐)

(同上结构,代码块用 `<!-- ━━━ 📋 开始复制 · 封面 C ━━━ -->` 分隔)
````

### 中文主标题撰写要点（决定点击率的关键）

- **字数**：10-16 字,超过 18 字在 2.35:1 封面上会拥挤
- **句式**：
  - 疑问句最强(例:「Cursor 估值 500 亿,谁是真赢家?」)
  - 冲突句次之(例:「你以为 Cursor 赢了,其实早被反超」)
  - 数字+悬念最稳(例:「500 亿估值背后的 3 个真相」)
- **避免**:完整句号;与文章 H1 一字不差(封面应该是"钩子版"的 H1)
- **从文章 H1 压缩**:H1 通常 20-28 字,封面标题压到 10-16 字,保留最锋利的那部分
- **3 组创意的标题可以不同**:A 用疑问句、B 用冲突句、C 用数字句

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

- **封面**必须 `2.35:1 横幅比例`（公众号头条规格）
- **内文配图**保持 `16:9 横版比例`（正文段落间配图）
- **除了中文主标题文字**（封面必须）**和 infographic 模块内的数据标签**（信息图必须），其他地方加 `画面主体区不出现多余装饰文字`
- 色调与 style.yaml 的 cover_style 对齐
- 风格关键词要具体：不说"好看"，说"扁平化设计 + 柔和渐变 + 极简主义"

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）：
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）：
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）：
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）：
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）：
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

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

**中文提示词**（粘贴到 ChatGPT/Gemini 网页）:
```
{根据上方结构化模板生成的完整中文提示词}
```

> **Gemini Advanced 用户**：同一份中文提示词可直接粘到 gemini.google.com

- 备选方案：{Unsplash/Pexels 搜索关键词}
````

### 内文配图通用要求

- 尺寸统一 **16:9 横版**（image_gen.py --size article）
- **视觉锚定**：每条提示词的 Colors 和 Style 字段必须引用封面提取的视觉锚点
- 实体锚定规则同封面——每条提示词至少包含 2 个文章实体
- 不要太复杂——手机屏幕上看，简洁的图比复杂的图好
- **提示词语言**：**统一用中文**。gpt-image-1.5 / nano-banana-2 对中文理解和中文字渲染都足够好,中文提示词表达更精确,图中要渲染的中文数据点可以直接原样引用,不需要中英切换
- 每张图都提供一个**免费图库备选关键词**，以防生图效果不佳
- **命名约定**：每张配图的「存为」字段按顺序 `images/chart-1.png`、`images/chart-2.png`... 与文章 markdown 里的占位符一一对应

---

## 三、infographic-dense（高密度多模块信息图)

高密度型配图是一张图承载 6-7 个独立模块的信息图。**跟 decorative 完全不同**——它不是画一个概念,而是像一张"小报/仪表盘/干货卡"把文章的核心数据点都可视化。

### 资源位置

- Layout 菜单(21 种):`{skill_dir}/references/visuals/layouts/*.md`
- Style 菜单(20 种):`{skill_dir}/references/visuals/styles/*.md`
- 主提示词模板:`{skill_dir}/references/visuals/base-prompt.md`
- 结构化内容模板:`{skill_dir}/references/visuals/structured-content-template.md`
- 菜单概览和推荐搭配:`{skill_dir}/references/visuals/README.md`(先读它)

### 生成流程(每张 infographic-dense 图)

**Step 1: 选 Layout**

按文章内容类型挑 1 个(5 种最实用的先看):

| 文章内容 | 推荐 Layout |
|---------|------------|
| 多维度盘点/避坑/全面解析 | `dense-modules` |
| 多选项横向对比 | `comparison-matrix` 或 `binary-comparison` |
| 清单/榜单/标签云 | `bento-grid` |
| 数据复盘/多指标 | `dashboard` |
| 元素分类/赛道盘点 | `periodic-table` |

读对应的 `references/visuals/layouts/{layout}.md`,把其中的 Structure / Module Archetypes / Visual Elements 要点提取出来。

**Step 2: 选 Style**

按文章调性挑 1 个(5 种最实用):

| 文章调性 | 推荐 Style |
|---------|-----------|
| 科技/数据/研究(默认首选) | `pop-laboratory` |
| 商业/干货/清单 | `corporate-memphis` |
| 文艺/生活/随笔 | `morandi-journal` |
| 文化/趋势/反叛 | `retro-pop-grid` |
| 教程/Step by Step | `ikea-manual` |

读对应的 `references/visuals/styles/{style}.md`,提取 Color Palette / Typography / Texture 关键词。

**Step 3: 结构化内容(核心)**

按 `structured-content-template.md` 把本 H2 对应的内容拆成 **6-7 个 Section**,每个 Section 含 4 项:

- **Key Concept**:该模块核心论点,1 句话(≤12 字)
- **Content**(逐字从文章/素材提取,**禁止改写**):2-3 条数据点
- **Visual Element**:icon / mini-chart / callout / list / emoji 徽章
- **Text Labels**:精确的显示文字(含数字和术语)

**Step 4: 分别合成「底图 prompt」+「overlay.json」**(T2 默认档)

infographic-dense 默认走 T2——图像模型对长中文、小字、数据标签的渲染错误率极高,实测"放漫/放缓"、"数揭/数据"、"揄末/样本"等。所以:

- **底图 prompt**:让 AI 只画**无字底图**(背景/色块/图表形状/icon/模块框/粒子流/网格线)。负面提示词**必须显式拒绝所有文字**
- **overlay.json**:agent 把所有文字(模块小标题、数据点、来源、坐标标签)作为**叠字层清单**输出,Pillow 脚本自动叠上,**汉字 100% 精准**

流程图:
```
AI 出底图 chart-N-raw.png   (无字,纯视觉)
       ↓
agent 产 chart-N.overlay.json   (字层清单)
       ↓
python3 toolkit/overlay_text.py chart-N-raw.png chart-N.overlay.json
       ↓
chart-N.png   (汉字精准的成品图)
```

### 结构化模板(T2 双块输出 · 每张 chart 用 §N 独立小节 + 复制分隔符)

注意:**每张 chart 必须作为独立 `## §N · chart-{序号}` 小节**,底图 prompt 和 overlay.json 各自用 HTML 注释分隔符包围。文档架构和用户粘贴体验详见已完成示范 `output/2026-04-18-ai-coding-non-consensus-prompts.md`。

````markdown
## §{N+1} · chart-{序号} · {H2 标题}

⭐ **T2 两步法**:这一段先出"无字底图",下一步 §{N+2} 用脚本叠字。

- 类型:`infographic-dense`
- 档位:**T2**(底图 + Pillow 叠字)
- 底图存为:`output/images/chart-{序号}-raw.png`(无字,AI 出)
- 成图存为:`output/images/chart-{序号}.png`(叠字后,Pillow 自动出)
- overlay 配置:`output/images/chart-{序号}.overlay.json`
- Layout:`{layout 名,如 dense-modules}`
- Style:`{style 名,如 pop-laboratory}`
- 对应内容:{1 句话概括本张图回答什么核心问题}

**模块结构**(6-7 个 Section,从文章真实素材提取,用于生成 overlay.json):

#### Section 1: {模块小标题 6-10 字}
- Key Concept: {1 句话核心论点}
- Content(逐字从文章/素材提取,禁止改写):
  - {数据点 1,含来源}
  - {数据点 2}
  - {数据点 3}
- Visual Element: {icon / mini-chart / callout / 色块}
- 后期叠字的 Text Labels: {"精确文字 1", "精确文字 2", "精确文字 3"}

#### Section 2 ~ 7: ...

**视觉规格**:
- 色板:{主/辅/强调 hex,对齐封面锚点}
- Aspect:16:9(横版 · 公众号正文宽)
- 模块坐标:MOD-01、MOD-02... 或强分隔线区分

---

**第一步 · 出无字底图**

**对 ChatGPT 说**:「请生成一张 **16:9** 横版、**1280×720 像素**的纯视觉底图。**画面上不能出现任何文字、数字、字母**,只要视觉架构,提示词如下:」

<!-- ━━━ 📋 开始复制 · chart-{序号} 底图 ━━━ -->

```
请生成一张 **完全无文字** 的信息图底图,用于公众号正文配图(16:9 横版,1280×720)。

画面架构:采用 {layout} 布局,{style} 视觉风格。
- 背景:{背景色 hex,如深蓝 #0F172A}
- 模块 6-7 个,{排布方式如 2×3 网格}
- 每个模块是一个**圆角矩形色块**(不同颜色区分):
  - 模块 1(左上):{颜色 A}色块,里面留出空白给后期叠字。画上 {icon 类型,如"建筑楼宇 icon"}
  - 模块 2(上中):{颜色 B}色块,画上 {mini donut / mini bar chart 形状,但数字留空不画}
  - 模块 3(右上):{颜色 C}色块,画上 {icon}
  - 模块 4(左下):{颜色 D}色块,画上 {形状}
  - 模块 5(中下):{颜色 E}色块,画上 {形状}
  - 模块 6(右下,警示色):鲜艳{警告色}色块,画上感叹号 icon

视觉风格细节(从 styles/{style}.md 提取):
- {色板/排版/纹理关键词}

**负面提示词(关键!)**:
  no text, no letters, no labels, no Chinese characters, no numbers in the image,
  no watermark, no English words, no typography anywhere,
  pure graphics/shapes/colors/icons only
```

<!-- ━━━ ✂️ 结束复制 ━━━ -->

**⬇ 下载 → 存为** `output/images/chart-{序号}-raw.png`(注意后缀 `-raw`)

**检查要点**:下载前确认画面上**没有任何文字/数字/字母**。若 AI 偷画了字,对它说「请重画,画面上不要出现任何文字」。

---

**第二步 · overlay.json(Pillow 叠字清单)**

```json
{
  "size": [1280, 720],
  "layers": [
    {
      "text": "{模块 1 小标题}",
      "x": 213, "y": 100, "anchor": "mm",
      "weight": "Bold", "size": 32, "color": "#2D2926"
    },
    {
      "text": "{数据点 1.1}",
      "x": 213, "y": 180, "anchor": "mm",
      "weight": "Heavy", "size": 48, "color": "#06B6D4"
    },
    {
      "text": "{数据点 1.2}",
      "x": 213, "y": 230, "anchor": "mm",
      "weight": "Regular", "size": 20, "color": "#6B7F5F"
    },
    ...(每个模块 3-5 层)
  ]
}
```

**overlay 坐标参考**(1280×720 的 2×3 网格):
- 模块 1(左上):中心 (213, 180) · 模块 2(上中):(640, 180) · 模块 3(右上):(1067, 180)
- 模块 4(左下):(213, 540) · 模块 5(中下):(640, 540) · 模块 6(右下):(1067, 540)
- 每模块内部:小标题 y - 80,主数据居中,说明 y + 50

**⬇ 保存 overlay.json 到** `output/images/chart-{序号}.overlay.json`

---

## §{N+2} · chart-{序号} · 本地跑脚本叠中文字

底图下载好后,在终端里复制这一行执行:

<!-- ━━━ 📋 开始复制 · 终端命令 chart-{序号} ━━━ -->

```bash
cd /Users/mahaochen/wechatgzh/wewrite && python3 toolkit/overlay_text.py output/images/chart-{序号}-raw.png output/images/chart-{序号}.overlay.json
```

<!-- ━━━ ✂️ 结束复制 ━━━ -->

脚本会自动产出 `output/images/chart-{序号}.png`,汉字 100% 精准。

> **Gemini Advanced 用户**:底图 prompt 同样适用 gemini.google.com

> **baoyu-infographic 二次加工(可选)**:想一键搞定不走 T2 分离流程,可 `/baoyu-infographic` 走官方合成。判定详见 `{skill_dir}/references/visuals/when-to-use-baoyu.md`

- 备选图库关键词:Unsplash "{检索词}"
````

### 高密度图的硬标准

1. **6 个 Section 是下限,7 个是推荐**,少于 6 个不算高密度
2. **每个 Section 都必须有具体数据点**(数字/品牌名/百分比/专有名词),禁止"显著提升""广泛应用"这种空话
3. **Content 逐字提取**,不加工、不总结——保留文章/素材的原始表达
4. **中文提示词必须显式列出"画面上必须原样渲染的中文文字"清单**——这是 gpt-image-1.5 / nano-banana-2 准确渲染中文标题和数据点的关键
5. **Layout × Style 组合必须匹配文章调性**(参考 `visuals/README.md` 推荐搭配表)
6. **比例**:内文配图 `16:9`(正文宽);**封面专属** `2.35:1`(公众号头条规格)

---

## 四、辅助功能

### 提示词修改

如果用户说"封面创意 A 我喜欢方向但是想要更暖的色调"，只修改对应创意的提示词，其他不变。

### 创意切换

如果用户说"封面我想要更多选择"，在 A/B/C 三种策略的基础上，为用户偏好的策略再出 2 个变体（比如"直觉冲击型的变体 1 和变体 2"）。

### 配图场景调整

如果用户说"第 3 张配图位置不对"或"这段不需要图"，按用户要求增删调整。

### 模式切换

如果用户说"这张图换成高密度信息图"或"加干货",把该配图的类型从 decorative 换到 infographic-dense,按「三、infographic-dense」流程重写。

---

## 输出示例

**完整参考**:`output/2026-04-18-ai-coding-non-consensus-prompts.md`——这份按最新架构(§N 独立小节 + 复制分隔符 + 跳转索引)写完,可照此样板生成新 prompts.md。

### 核心骨架(必须遵守)

每份 prompts.md 必须按下列顺序输出:

```
# 视觉提示词 · {文章标题}
(元信息:模型/对应文章/主题)
---

## 📑 快速复制索引        ← 跳转索引表,序号 / 段名 / 比例 / 存储路径
(按 §1 §2 §3 ... 列出全部可复制段)

---

## §1 · 封面 · 推荐 C     ← 3 组里选最推荐的那组放前面
(开场白 + 分隔符代码块 + ⬇ 下载存为 cover.png)

## §1 备选 · 天平失衡      ← 可折叠 <details> 放 A/B 备选
## §1 备选 · 深夜屏幕

---

## §2 · chart-1 · {H2 1}  ← 每张 chart 独立 §N 小节
(T1 直出 or T2 两步法)

## §3 · chart-2 · {H2 2}
...

## §N · chart-M · {H2 M}

---

## §N+1 · (T2 用户)终端跑脚本叠字   ← 集中给 overlay 命令

## §N+2 · 预览成品                   ← preview 命令

---

## 附录 · 遇到问题怎么办             ← 常见 FAQ 表
## 附录(折叠)· 设计理念               ← <details>,不干扰主流程
```

### 关键要求(硬约束)

1. **每个可复制代码块必须前后包围 HTML 注释分隔符**:
   ```
   <!-- ━━━ 📋 开始复制 · {段名} ━━━ -->
   ```(代码块)```
   <!-- ━━━ ✂️ 结束复制 ━━━ -->
   ```
2. **每段代码块前必须有一行开场白**,格式:「**对 ChatGPT 说**:「请生成 XXX 像素比例 YYY 提示词如下:」」
3. **每段代码块后必须有一行下载指令**:「**⬇ 下载 → 存为** `output/images/xxx.png`」
4. **比例显式标注**:封面 2.35:1,内文 16:9(每次说清楚)
5. **T2 图的 overlay.json 必须实际写入** `output/images/chart-{序号}.overlay.json`(不是只放在 prompts.md 代码块里),方便用户直接跑 `overlay_text.py`
6. **跳转索引表在开头**,让用户看一眼就知道"我要做哪几段"
