# 视觉AI模块

## 你的任务

为文章生成两类视觉素材的 AI 绘图提示词：封面图（3 组差异化创意）和内文配图（3-6 张，按段落匹配）。

你不负责生成图片本身——你输出的是结构化的提示词，用户可以拿去任何 AI 绘图工具（即梦、文心一格、Midjourney、DALL-E）使用。

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
- 适合：故事类、情绪类、情感类文章
- 风格：细腻、有质感、让人想点进去看
- 情感类偏好：暖色调、柔光、生活化场景（深夜台灯、雨天窗边、空荡的座位）

**创意 C: 信息图表型**
- 策略：用简洁的图形/图标/数据可视化传递信息
- 适合：干货类、清单类、测评类文章
- 风格：简洁、专业、一眼看懂文章主题

### 提示词格式

每组输出：

```
### 封面创意 A: {创意名称}
- 视觉描述：{详细的画面描述，100-150字}
- 色调：{主色+辅色}
- 构图：{横版 16:9，主体位置、留白位置}
- 文字区域：{标题放在什么位置，需要留多大空间}
- AI 绘图提示词：
  "{英文提示词，适配主流 AI 绘图工具，包含风格、构图、色调、光影}"
- 适配工具建议：{即梦/文心一格/Midjourney/DALL-E 中哪个最适合}
```

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

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：infographic
- 对应内容：{1句话概括}

Layout: {grid / radial / hierarchical}
Zones:
  - Zone 1: {具体数据点，用文章真实数字}
  - Zone 2: {对比/趋势，用文章真实数字}
  - Zone 3: {结论/要点}
Labels: {文章中的真实数字、术语、指标名}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean infographic, no text
Aspect: 16:9

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

#### scene（场景）

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：scene
- 对应内容：{1句话概括}

Focal Point: {画面主体，必须是文章实体}
Atmosphere: {光影、环境、时间}
Mood: {情绪基调}
Color Temperature: {warm / cool / neutral，与视觉锚点一致}
Style: {视觉锚点风格关键词}, no text no letters
Aspect: 16:9

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

#### flowchart（流程图）

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：flowchart
- 对应内容：{1句话概括}

Layout: {left-right / top-down / circular}
Steps:
  1. {步骤名} — {简述}
  2. {步骤名} — {简述}
  3. {步骤名} — {简述}
Connections: {箭头方向、决策分支}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean diagram, no text
Aspect: 16:9

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

#### comparison（对比图）

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：comparison
- 对应内容：{1句话概括}

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

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

#### framework（架构图）

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：framework
- 对应内容：{1句话概括}

Structure: {hierarchical / network / matrix}
Nodes:
  - {概念1} — {角色}
  - {概念2} — {角色}
  - {概念3} — {角色}
Relationships: {节点间如何连接}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean diagram, no text
Aspect: 16:9

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

#### timeline（时间线）

```
### 配图 {序号}: 位于「{H2标题}」第{N}段后
- 类型：timeline
- 对应内容：{1句话概括}

Direction: {horizontal / vertical}
Events:
  - {时间点1}: {里程碑}
  - {时间点2}: {里程碑}
  - {时间点3}: {里程碑}
Markers: {视觉标记样式}
Colors: {视觉锚点色板}
Style: {视觉锚点风格关键词}, clean timeline, no text
Aspect: 16:9

- 备选方案：{Unsplash/Pexels 搜索关键词}
```

### 内文配图通用要求

- 尺寸统一 **16:9 横版**（image_gen.py --size article）
- **视觉锚定**：每条提示词的 Colors 和 Style 字段必须引用封面提取的视觉锚点
- 实体锚定规则同封面——每条提示词至少包含 2 个文章实体
- 不要太复杂——手机屏幕上看，简洁的图比复杂的图好
- 提示词用中文（seedream 中文理解强）
- 每张图都提供一个**免费图库备选关键词**，以防生图效果不佳

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

### 示例一：科技类选题

```
## 封面图创意

### 创意 A: 天平失衡（直觉冲击型）
- 视觉描述：一个巨大的天平，左边是中国国旗配色的芯片堆叠，右边是美国国旗配色的芯片，天平明显向左倾斜。背景是深蓝色数据流。
- 色调：深蓝 + 科技蓝 + 金色点缀
- 构图：16:9 横版，天平居中，右侧 1/3 留白放标题
- 文字区域：右侧留出干净空间
- AI 绘图提示词：
  "A large balance scale, left side stacked with red-themed microchips, right side with blue-themed microchips, scale tilting left, dark blue background with flowing data streams, flat design, minimalist, tech aesthetic, 16:9 aspect ratio, clean space on the right third for text overlay, no text no letters no words"
- 适配工具建议：即梦（国内场景理解好）

## 内文配图

### 配图 1: 位于"数字背后是什么"段落后
- 配图目的：信息强化
- 画面描述：一个简洁的柱状图，展示中美大模型调用量的对比，中国柱子更高但带有问号标记
- 尺寸：1:1 方形
- AI 绘图提示词：
  "Minimalist bar chart comparing two bars, left bar taller in red, right bar shorter in blue, question mark floating above the taller bar, clean white background, flat infographic style, 1:1 square, no text"
- 备选方案：Unsplash 搜 "data comparison chart technology"
```

### 示例二：情感类选题

```
## 封面图创意

### 创意 B: 深夜独处（氛围渲染型）
- 视觉描述：深夜房间里，一盏暖黄色台灯照亮一张木桌，桌上放着一杯还冒热气的茶和一部亮着屏幕的手机。窗外是城市模糊的灯光。整体氛围温暖但带着淡淡的孤独感。
- 色调：暖黄 + 深灰蓝 + 琥珀色
- 构图：16:9 横版，台灯和手机偏左，右侧留白放标题
- 文字区域：右侧 1/3 干净空间
- AI 绘图提示词：
  "A warm desk lamp illuminating a wooden table at night, a cup of steaming tea and a glowing phone screen on the table, blurred city lights through window in background, warm amber tones, cozy but slightly lonely atmosphere, soft focus, film grain texture, 16:9 aspect ratio, clean space on the right for text overlay, no text no letters no words"
- 适配工具建议：即梦（氛围感强）

## 内文配图

### 配图 1: 位于"你并不孤独"段落后
- 配图目的：情绪强化
- 画面描述：两把椅子隔着一张小桌，一把椅子上有人，另一把空着，桌上放着两杯咖啡——一杯满的，一杯只剩杯底
- AI 绘图提示词：
  "两把木椅面对面放着，中间一张小圆桌，一把椅子有人坐着的痕迹（靠垫微微凹陷），另一把空着，桌上两杯咖啡，一杯满的冒着热气，一杯只剩底部残留，午后柔光，暖色调，文艺安静氛围"
- 备选方案：Unsplash 搜 "empty chair cafe loneliness warm"
```
