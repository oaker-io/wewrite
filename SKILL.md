---
name: wewrite
description: |
  微信公众号内容全流程助手：热点抓取 → 选题 → 框架 → 内容增强 → 写作 → SEO → 视觉AI → 排版推送草稿箱。
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

**进度追踪**：主管道启动时，用 TaskCreate 为 8 个 Step 创建任务。每开始一个 Step 标记 in_progress，完成后标记 completed。用户可随时看到当前进度。

**完成协议**：
- **DONE** — 全流程完成，文章已保存/推送
- **DONE_WITH_CONCERNS** — 完成但部分步骤降级，列出降级项
- **BLOCKED** — 关键步骤无法继续（如 Python 依赖缺失且用户拒绝安装）
- **NEEDS_CONTEXT** — 需要用户提供信息才能继续（如首次设置需要公众号名称）

**路径约定**：本文档中 `{skill_dir}` 指本 SKILL.md 所在的目录（即 WeWrite 的根目录）。

**Onboard 例外**：Onboard 是交互式的（需要问用户问题），不受"全自动"约束。Onboard 完成后回到全自动管道。

**辅助功能**（按需加载，不在主管道内）：
- 用户说"重新设置风格" → `读取: {skill_dir}/references/onboard.md`
- 用户说"学习我的修改" → `读取: {skill_dir}/references/learn-edits.md`。支持两种来源：
  - **本地修改**（默认）：用户在 `output/` 的 markdown 文件中修改
  - **微信草稿箱同步**：`python3 {skill_dir}/scripts/learn_edits.py --from-wechat`，自动从草稿箱拉回最新内容，与本地原文做纯文本 diff
- 用户说"学习排版"/"学排版" → `python3 {skill_dir}/scripts/learn_theme.py <url> --name <name>`，用户需提供一个公众号文章 URL 和主题名称。提取完成后提示用户设置 `style.yaml` 的 `theme` 字段。
- 用户说"学习这篇文章"/"导入范文" + URL → `python3 {skill_dir}/scripts/fetch_article.py <url> -o /tmp/article.md && python3 {skill_dir}/scripts/extract_exemplar.py /tmp/article.md -s <账号名>`，从公众号文章 URL 提取正文并导入范文库。支持三级降级（requests → Playwright → 手动 HTML）。
- 用户说"看看文章数据" → `读取: {skill_dir}/references/effect-review.md`
- 用户说"检查一下"/"自检"/"这篇文章怎么样" → 对最近一篇生成的文章（或用户指定的文章）执行自检，输出生成报告：

  **第一部分：生成档案**（告诉用户这篇文章是怎么来的）
  1. 读取 `history.yaml` 最近一条记录，提取：
     - 使用的框架类型 + 写作人格
     - 激活的维度随机化组合
     - 素材采集来源（WebSearch 还是降级到 LLM）
     - 内容增强策略（角度发现/密度强化/细节锚定/真实体感）
     - 范文风格库是否命中（用了哪几篇 exemplar，还是 fallback 到种子）
     - playbook 中生效的规则条数
  2. 如果 history.yaml 无记录或用户指定了外部文章 → 跳过此部分，提示"这篇文章不是 WeWrite 生成的，只做质量检查"

  **第二部分：质量检查**（告诉用户哪里还能改）
  1. `python3 {skill_dir}/scripts/humanness_score.py {article_path} --json`
  2. Agent 解读 JSON 中每项得分，翻译为用户可操作的建议，格式：
     - 每条建议定位到具体段落或句子（"第 3 段连续 4 句长度接近"）
     - 给出具体改法（"建议把第 3 句拆成两个短句"、"这里可以加一句你自己的感受"）
     - 按影响度排序，最多 5 条
  3. 如果所有项得分都不错 → "这篇文章质量不错，建议在编辑锚点处加入你的个人内容就可以发了。"

  **输出格式**：自然语言报告，不输出 JSON 或分数（用户不需要看数字）
- 用户说"更新"/"更新 WeWrite"/"升级" → 在 `{skill_dir}` 执行 `git pull origin main`，完成后告知版本变化

---

## 主管道（Step 1-8）

主管道启动时，创建以下 8 个任务用于进度追踪：

```
TaskCreate: "Step 1: 环境 + 配置"
TaskCreate: "Step 2: 选题"
TaskCreate: "Step 3: 框架 + 素材"
TaskCreate: "Step 4: 写作"
TaskCreate: "Step 5: SEO + 验证"
TaskCreate: "Step 6: 视觉 AI"
TaskCreate: "Step 7: 排版 + 发布"
TaskCreate: "Step 8: 收尾"
```

每开始一个 Step → TaskUpdate status=in_progress。完成 → TaskUpdate status=completed。

---

### Step 1: 环境 + 配置

**1.1 环境检查**（静默通过或引导修复）：

```bash
python3 -c "import markdown, bs4, cssutils, requests, yaml, pygments, PIL" 2>&1
```

| 检查项 | 通过 | 不通过 |
|--------|------|--------|
| `config.yaml` 存在 | 静默 | 引导创建，或设 `skip_publish = true` |
| Python 依赖 | 静默 | 提供 `pip install -r requirements.txt` |
| `wechat.appid` + `secret` | 静默 | 设 `skip_publish = true` |
| `image.api_key` 或 `image.providers` 至少一项有效 | 静默 | 设 `skip_image_gen = true` |
| `references/exemplars/index.yaml` | 静默 | 提示："范文库为空。如果你有已发布的文章（markdown），可以说**'导入范文'**建立风格库，写出来的文章会更像你。没有也不影响使用。" |

**1.2 版本检查**（静默通过或提醒）：

```bash
cd {skill_dir} && git fetch origin main --quiet 2>/dev/null
```

比对本地 `{skill_dir}/VERSION` 与远程 `git show origin/main:VERSION`：
- 相同 → 静默通过
- 不同 → 提示用户："WeWrite 有新版本可用（当前 X → 最新 Y），说「更新」即可升级。"**不阻断流程**，继续 1.3
- git 不可用（无 .git 目录或 fetch 失败）→ 静默跳过

**1.3 加载风格**：

```
检查: {skill_dir}/style.yaml
```

- 存在 → 提取 `name`、`topics`、`tone`、`voice`、`blacklist`、`theme`、`cover_style`、`author`、`content_style`
- 不存在 → `读取: {skill_dir}/references/onboard.md`，完成后回到 Step 1

如果用户直接给了选题 → 跳到 Step 3（仍需框架选择和素材采集，不可跳过）。

---

### Step 2: 选题

**2.1 热点抓取**：

```bash
python3 {skill_dir}/scripts/fetch_hotspots.py --limit 30
```

**降级**：脚本报错 → WebSearch "今日热点 {topics第一个垂类}"

**2.2 历史分析 + SEO**：

```
读取: {skill_dir}/history.yaml（不存在则跳过）
```

```bash
python3 {skill_dir}/scripts/seo_keywords.py --json {关键词}
```

历史分析（有 stats 数据时）：
- 统计哪种 `framework` 的文章表现最好（阅读量/分享率）→ 推荐框架时加权
- 统计哪种 `enhance_strategy` 的文章表现最好 → 增强策略选择时参考
- 近 7 天已写的关键词降分（去重）

**降级**：SEO 脚本报错 → LLM 判断；history 无 stats → 跳过效果分析，仅做去重

**2.3 生成选题**：

```
读取: {skill_dir}/references/topic-selection.md
```

生成 **10 个选题**，其中：
- **7-8 个热点选题**：基于 2.1 的热点，按 topic-selection.md 规则评分
- **2-3 个常青选题**：不依赖热点，从用户的 `topics` 领域生成长尾内容（教程/方法论/经验总结/工具推荐），标注为"常青"。适合 content_style 为干货型/测评型的用户

每个选题含标题、评分、点击率潜力、SEO 友好度、推荐框架。

- 自动模式 → 选最高分
- 交互模式 → 展示全部，等用户选

---

### Step 3: 框架 + 素材

**3.1 框架选择**：

```
读取: {skill_dir}/references/frameworks.md
```

7 套框架（痛点/故事/清单/对比/热点解读/纯观点/复盘），自动选推荐指数最高的。

**3.2 素材采集 + 内容增强**（合并执行，共用搜索结果）：

```
读取: {skill_dir}/references/content-enhance.md
```

根据 3.1 选定的框架类型，一次搜索同时完成素材采集和内容增强：

| 框架 | 搜索策略 | 从结果中提取 |
|------|---------|-------------|
| 热点解读 / 纯观点 | `"{关键词} site:mp.weixin.qq.com OR site:36kr.com"` + `"{关键词} 观点 OR 评论"` | 真实素材（数据/引述）**+** 已有文章的主流观点（供角度发现） |
| 痛点 / 清单 | `"{关键词} 教程 OR 工具 OR 实操"` + `"{关键词} 数据 报告"` | 真实素材 **+** 具体工具名/步骤/参数（供密度强化） |
| 故事 / 复盘 | `"{人物/事件} 采访 OR 专访 OR 细节"` + `"{关键词} 数据 报告"` | 真实素材 **+** 时间锚/数字锚/对话锚/感官锚（供细节锚定） |
| 对比 | `"{方案A} vs {方案B} 评测 OR 体验"` + `"{方案A OR 方案B} 踩坑 OR 缺点 site:v2ex.com OR site:zhihu.com"` | 真实素材 **+** 真实用户评价和踩坑信息（供真实体感） |

每次搜索 2 轮，从结果中**同时**提取：
1. **素材**：5-8 条真实素材（具名来源 + 具体数据/引述/案例）。**禁止编造**。
2. **增强材料**：按 content-enhance.md 对应策略的要求提取（角度/密度要点/细节/用户声音）。
3. **模块化素材（为 Step 6 高密度信息图预备）**：素材除了写作用，还会直接灌进 `infographic-dense` 配图作为模块内容。搜索时有意识地保留**可成模块**的材料：
   - 带具体数字的数据点（数字越多越好）
   - 品牌名/产品名/工具名清单
   - 时间节点序列（适合 timeline/linear-progression 模块）
   - 优缺点 / 对比维度 / 踩坑点 / 清单条目（适合 dense-modules、comparison-matrix 模块）
   - Top N 排名（适合 dashboard、bento-grid）

两者并入框架大纲，一起传入 Step 4 写作 + Step 6 视觉生成。

**降级**：WebSearch 不可用 → 用 LLM 训练数据中可验证的公开信息。但需告知用户："素材采集未能使用 WebSearch，建议在编辑锚点处多加入你自己的内容。"密度强化不依赖搜索，始终执行。

---

### Step 4: 写作

```
读取: {skill_dir}/references/writing-guide.md
读取: {skill_dir}/playbook.md（如果存在，按 confidence 分级执行）
读取: {skill_dir}/history.yaml（最近 3 篇的 dimensions + closing_type 字段）
读取: {skill_dir}/references/exemplars/index.yaml（如果存在）
```

**4.1 维度随机化**：

从以下维度池随机激活 2-3 个维度，让每篇文章的表达方式不同。如果 history.yaml 有最近 3 篇的 `dimensions` 字段，避免使用相同组合。

| 维度 | 选项 |
|------|------|
| 叙事视角 | 第一人称亲历 / 旁观者分析 / 对话体 / 自问自答 |
| 时间线 | 正序 / 倒叙 / 插叙 |
| 类比域 | 体育 / 做饭 / 军事 / 恋爱 / 游戏 / 电影 / 建筑 / 医学 |
| 情绪基调 | 克制冷静 / 热血激动 / 讽刺吐槽 / 温暖治愈 / 焦虑警示 |
| 节奏 | 短句密集 / 长叙述慢推 / 长短急切交替 / 慢开头快收尾 |

**4.2 加载写作人格**：

```
读取: {skill_dir}/personas/{style.yaml 的 writing_persona 字段}.yaml
如果 style.yaml 没有 writing_persona 字段 → 默认 midnight-friend
```

人格文件定义了：语气浓度、数据呈现方式、情绪弧线、段落节奏、不确定性表达模板等。作为写作的硬性约束执行。

**优先级**：playbook.md（confidence ≥ 5 的规则）> persona > 范文风格 > writing-guide.md。writing-guide 是底线（基础写作规范），范文提供风格示范（句长节奏、情绪表达方式），persona 在此基础上特化风格参数（语气浓度、数据呈现），playbook 中高置信度规则是用户个性化的最终覆盖。playbook 中 confidence < 5 的规则作为软性参考。

**4.3 范文风格注入**（有 `references/exemplars/index.yaml` 时执行）：

从 index.yaml 筛选 category 匹配当前框架类型的范文，取 top 3。读取对应 .md 文件的片段内容。

在写作 prompt 中注入：

> 以下是该公众号风格的真实段落示例，模仿其句长节奏、情绪强度和口语化程度：
>
> 【开头风格】
> {exemplar_1 的开头钩子段}
>
> 【情绪段风格】
> {exemplar_2 的情绪高峰段}
>
> 【转折风格】
> {exemplar_2 或 exemplar_3 的转折/自纠段（如有）}
>
> 【收尾风格】
> {exemplar_3 的收尾段}

Category 映射规则：

| 框架类型 | exemplar category |
|----------|-------------------|
| 痛点型 | tech-opinion |
| 故事型 / 复盘型 | story-emotional |
| 清单型 / 对比型 | list-practical |
| 热点解读型 / 纯观点型 | hot-take |
| 其他 | general |

如果匹配到的范文不足 3 篇，用 general category 补足。

**Fallback（范文库为空时）**：读取 `{skill_dir}/references/exemplar-seeds.yaml`，从每个段落类型中随机选 1 个注入 prompt。种子段落只示范人类写作的结构模式（句长方差、情绪锐度、自我纠正、非总结式收尾），不携带特定风格。注入时使用：

> 以下是人类写作的结构模式示例，注意模仿其句长节奏和情绪表达方式（不要模仿具体内容或风格）：
>
> 【开头模式】{seeds.opening_hooks 随机 1 个}
>
> 【情绪段模式】{seeds.emotional_peaks 随机 1 个}
>
> 【转折模式】{seeds.transitions 随机 1 个}
>
> 【收尾模式】{seeds.closings 随机 1 个}

建库命令：`python3 {skill_dir}/scripts/extract_exemplar.py article.md`

**4.4 写文章**：
- H1 标题（20-28 字） + H2 结构，1500-2500 字
- **素材 + 增强约束**：Step 3.2 的素材和增强材料分散嵌入各 H2 段落。增强策略的核心输出（角度/密度要点/细节/用户声音）必须贯穿全文，不只装饰性出现一次
- **写作人格**：按 4.2 加载的人格参数写作（数据呈现方式、个人声音浓度、不确定性表达等）
- **收尾方式**：persona 的 `closing_tendency` 仅作为倾向参考。根据文章内容和情绪弧线自行判断最自然的收尾方式。如果 history.yaml 中最近 3 篇有 `closing_type` 字段，避免使用相同的收尾类型
- **写作规范**：writing-guide.md 中的基础规则（禁用词、句长方差、词汇混用等）在初稿阶段生效
- 2-3 个编辑锚点：`<!-- ✏️ 编辑建议：在这里加一句你自己的经历/看法 -->`
- 可选容器语法：`:::dialogue`、`:::timeline`、`:::callout`、`:::quote`
- **图片占位符**（必须）：预埋本地图片引用，方便用户用路径 1（ChatGPT 网页）生成图后直接渲染和推送：
  - H1 标题下一行插入封面占位符：`![封面](images/cover.png)`
  - 内文配图位置按 Step 6 的规划逐个插入：`![](images/chart-1.png)`、`![](images/chart-2.png)` ...
  - 命名**必须**与 `{slug}-prompts.md` 里的「存为」字段完全一致
  - 占位符在 preview 时若文件不存在会显示破图标（提示用户去生成）；在 publish 时 `cli.py` 的 `upload_image` 会自动找到本地文件并上传到微信 CDN

保存到 `{skill_dir}/output/{date}-{slug}.md`

**4.5 快速自检**（写完后立即执行，减少 Step 5 重写概率）：

对初稿做 5 项快速扫描，**当场修复**，不留到 Step 5：

**写作层面**：
1. **禁用词扫描**：检查 writing-guide.md 2.1 的禁用词列表，命中的直接替换
2. **句长方差**：是否有连续 3 句以上长度接近的段落，有则拆句或加短句

**内容层面**：
3. **开头钩子**：前 3 句是否制造了悬念/冲突/好奇心？如果是平铺直叙的背景介绍，重写开头
4. **增强贯穿**：增强策略的核心输出是否只出现在一段？如果是，在其他 H2 中补充
5. **金句检查**：全文是否有至少 1 句可独立截图转发的句子？如果没有，在情绪高点处补一句

LLM 自行完成，不需要调用脚本。

---

### Step 5: SEO + 验证

```
读取: {skill_dir}/references/seo-rules.md
```

**5.1 SEO**：3 个备选标题 + 摘要（≤40 字）+ 5 标签 + 关键词密度优化

**5.2 质量验证**（两个维度，每项逐一检查）：

**A. 写作质量**（writing-guide.md 基础规则）：

| 检查项 | 标准 | 规则 |
|--------|------|------|
| 句长方差 | 最短与最长句相差 ≥ 30 字 | 1.1 |
| 词汇温度 | 任意 500 字 ≥ 3 种温度 | 1.2 |
| 段落节奏 | 无连续 2 个相近长度段落 | 1.3 |
| 情绪极性 | 负面情绪 ≥ 2 处，无平铺直叙 | 1.4 |
| 禁用词 | 命中数 = 0 | 2.1 |
| 真实锚定 | 每个 H2 ≥ 1 条真实素材，零编造 | 3.1 |
| 具体性 | 每 500 字 ≥ 2 处具体细节 | 3.2 |

**B. 内容质量**（基于 Step 3.2 的增强策略检查）：

| 检查项 | 标准 | 适用框架 |
|--------|------|---------|
| 增强贯穿 | 增强策略的核心输出（角度/密度/细节/体感）在全文可见，不只出现在一段 | 所有 |
| 开头钩子 | 前 3 句能制造悬念、冲突或好奇心（不是背景铺垫） | 所有 |
| 金句密度 | 至少 1 处可独立截图转发的句子 | 所有 |
| 操作密度 | 每个 H2 有可操作要点（工具/步骤/参数） | 痛点/清单 |
| 角度锐度 | 核心观点能引发同意或反对，不是"两面都有道理" | 热点解读/纯观点 |
| 场景感 | 至少 2 处有时间/地点/对话等画面细节 | 故事/复盘 |
| 真实声音 | 至少 1 处引用真实用户评价或体验 | 对比 |

不通过 → **定向修复**：只替换不达标的具体句子/段落，不动已通过的部分。每轮最多改 3 处，改完立即重新检查该项。2 轮仍不过 → 标注跳过，继续下一项。

**5.3 脚本辅助验证**（补充 5.2 的逐项检查）：

Agent 在 5.2 检查过程中同步完成综合评估（各 H2 之间的语气差异度、信息密度的高低交替、段落间的节奏变化、整体阅读流畅度），产出 0-1 分数。

```bash
python3 {skill_dir}/scripts/humanness_score.py {article_path} --json --tier3 {agent_tier3_score}
```

解读 JSON 中 `composite_score`（0=质量高, 100=问题多）：
- < 30 → 通过，继续 Step 6
- 30-50 → 查看 `param_scores` 中最低分的 1-2 项，只修复对应的具体句子（不重写整段），改完重新打分。1 轮即可
- \> 50 → 取 `param_scores` 最低的 2-3 项，逐项定向修复（每项只改最相关的 1-2 处），最多 2 轮。仍 > 50 则标记 DONE_WITH_CONCERNS 继续

---

### Step 6: 视觉 AI

```
读取: {skill_dir}/references/visual-prompts.md
```

**硬规则**：无论 `skip_image_gen` 是否为 true，都必须执行 6.1–6.4 的**提示词生成**并写入 `output/{slug}-prompts.md`。`skip_image_gen=true` 只跳过实际 image_gen.py 调用。数量固定（封面 3 组 + 内文 3-6 张按字数），不随模型变化。

**提示词语言**：**统一用中文**(不论 provider)。理由:
- 当前主力模型 gpt-image-1.5 / nano-banana-2(Gemini 3 Flash Image)对中文的理解和中文字渲染都足够好
- 中文提示词表达更精确,画面中要渲染的中文数据点可原样引用
- 国内模型(doubao/jimeng/dashscope)原本就需要中文
- 避免中英切换带来的术语翻译损耗

**比例规格**(严格遵守,见 visual-prompts.md 头部的比例规范表):
- **封面** `cover.png`:**2.35:1**(微信公众号头条主封面规格)
- **内文配图** `chart-N.png`:**16:9**(正文段落间配图)

**6.0 准备目录**（必须第一步执行）：

```bash
mkdir -p {skill_dir}/output/images
```

**6.1 实体提取**：从终稿中提取 3-5 个**具体实体**（人物、产品名、场景、数据点、行业术语）。后续所有提示词必须包含至少 2 个实体。

**6.1b 配图模式与档位选择**(两条正交维度):

**维度 1 · 配图模式**:按文章框架决定 `decorative` / `infographic-dense` 组合:

| 框架 | 封面 | 内文配图模式分布 | 备注 |
|------|------|-----------------|------|
| 热点解读 / 纯观点 | `decorative` | ≥50% `infographic-dense` | 有数据段/对比段时优先高密度 |
| 痛点 / 清单 / 对比 / 复盘 | `decorative` | **100% `infographic-dense`** | 干货类文章读者明确期待高密度 |
| 故事 / 情绪 | `decorative` | `decorative`(多用 scene 类型) | 场景感优先,数据为辅 |

**判定个别配图该用哪个模式的细则**:
- 段落含具体数据点 ≥3 个 → `infographic-dense`
- 段落是对比/清单/盘点 → `infographic-dense`
- 段落是氛围渲染/情感过渡 → `decorative`
- 段落只有结论/金句 → `decorative`

**维度 2 · T0/T1/T2 档位**(文字渲染策略 · 两条腿走路):

图像模型(gpt-image-1.5 / nano-banana-2)对长中文、小字、中英混排的渲染**错误率高**(实测"放漫/放缓"、"数揭/数据"、"揄末/样本"等)。三档处理:

| 档 | AI 画什么 | Pillow 叠什么 | 用例 |
|---|---------|-------------|------|
| **T0** | 无文字(纯视觉) | 无 | 氛围场景、故事型配图、背景插画 |
| **T1** | ≤16 字大标题(占画面高 ≥20%,独立干净区) | 无(AI 直出,容忍小瑕疵) | 封面主标题 |
| **T2** | **完全无字底图**(背景/色块/图表形状/icon/模块框) | **所有文字**(标题/数据/小字/来源/坐标) | **`infographic-dense` 默认档** |

**档位与模式的正交组合建议**:

| 模式 × 档位 | 用法 |
|------------|------|
| `decorative` × T0 | 氛围场景图 |
| `decorative` × T1 | 封面主标题(默认) |
| `decorative` × T2 | 封面 T1 失败的降级 / 需要多个精准文字标签的概念图 |
| `infographic-dense` × T2 | **默认**,干货数据图都走这里 |

**两条腿走路回退规则**:
- 先走 T1 出封面,如果用户反馈"错字了"/"标题乱了" → **命令**「封面走 T2 重做」→ agent 重新输出该封面为 T2(无字底图 + overlay.json + 调 toolkit/overlay_text.py)
- 同理 chart-N 错字太多 → 用户说「chart-N 走 T2 重做」→ agent 重新输出该图为 T2
- **infographic-dense 默认直接 T2**,跳过 T1 尝试(实测 AI 直出必错)

**6.2 封面生成**:生成封面 3 组创意提示词(按 visual-prompts.md 的 A/B/C 三种策略,均为 `decorative`)写入 `output/{slug}-prompts.md`。**封面硬规则**:
- **比例** `2.35:1`(微信公众号头条主封面,如 1080×459)
- **档位默认 T1**:AI 直接渲染 10-16 字中文主标题(从文章 H1 压缩出"钩子版"),字号占画面高 ≥20%,放在画面独立干净区(其他区域禁止出现多余文字/英文标签/小字)
- **3 组创意的标题可以不同**(A 用疑问句、B 用冲突句、C 用数字句等),以覆盖不同点击诱饵类型
- **T1 失败降级 T2**:如果 AI 产出主标题有错字,用户说「封面走 T2 重做」→ 重新输出为 T2(无字底图 + overlay.json + Pillow 叠字),100% 汉字精准

如果 `skip_image_gen != true`,选最佳 1 组调用 image_gen.py 生成。

**6.3 封面验证**：
- **交互模式**：展示封面，问用户"封面效果如何？"。用户 OK → 继续；不满意 → 调整提示词重新生成。
- **全自动模式**：agent 自检——提示词中的实体是否在画面描述中可识别？如果提示词过于泛化（仅含"科技感""未来感"等抽象词，无具体实体），换一组提示词重试 1 次。

**6.3b 风格锚定**：封面确认后，提取视觉锚点（色板 hex、风格关键词、画面调性），后续所有内文配图的提示词必须引用这组锚点，保证全文视觉一致。

**6.4 内文配图**:分析文章结构,为每个需要配图的段落按 6.1b 选模式 + 档位:
- **`decorative` 图(T0/T1)**:从 visual-prompts.md 的 6 种旧模板中选(infographic/scene/flowchart/comparison/framework/timeline),1 张图 1 个概念。文字极少时走 T0,有大标题走 T1
- **`infographic-dense` 图(T2 默认)**:走 visual-prompts.md 第三节的 4 步流程(选 Layout → 选 Style → 结构化内容 → 分别合成「底图 prompts」和「overlay.json」两块输出),1 张图塞 6-7 个模块;先读 `{skill_dir}/references/visuals/README.md` 挑 layout/style 搭配

生成 3-6 张配图提示词写入 `output/{slug}-prompts.md`,每张 infographic-dense 图额外产出 `output/images/chart-N.overlay.json`。如果 `skip_image_gen != true`,批量调用 image_gen.py 出底图,然后自动跑 overlay_text.py 合成终图。

**6.5 T2 叠字自动化**(Pillow 后期排字):

每张 infographic-dense 图的产出链:
```
AI 出底图:chart-N-raw.png   ←(无任何文字,仅视觉)
   ↓
overlay.json:               ←(agent 按文章内容生成字层清单)
  { "size": [1280, 720],
    "layers": [
      {"text": "付费 AI Coding 工具 Top 4",
       "x": 640, "y": 100, "anchor": "mm",
       "weight": "Bold", "size": 56, "color": "#2D2926",
       "bg": "#DCAC5E"},
      ... 6-30 层
    ]
  }
   ↓
python3 {skill_dir}/toolkit/overlay_text.py \
    output/images/chart-N-raw.png \
    output/images/chart-N.overlay.json
   ↓
chart-N.png  ←(汉字 100% 精准)
```

**overlay.json schema**:
- 根级:`size` [w, h] 可选 · `layers` 列表
- 每个 layer:`text`(必填)· `x`、`y`(必填,像素坐标)· `anchor`(默认 `mm`)· `weight`(Regular/Medium/Semibold/Bold/Heavy)· `size`(px)· `color`(#RRGGBB 或 #RRGGBBAA)· `stroke_color`、`stroke_width` 可选 · `bg`(背景色,画圆角矩形)· `bg_padding` · `line_spacing` · `max_width`(自动换行)· `rotation`(度)· `opacity`

**skip_image_gen 行为**:
- `skip_image_gen=true` → 不调 image_gen.py、不调 overlay_text.py
- 但 **overlay.json 必须始终写到 `output/images/chart-N.overlay.json`**,用户拿到底图后可以手动跑 overlay_text.py

**6.6 什么时候调用外部 baoyu-infographic**(判定详见 `{skill_dir}/references/visuals/when-to-use-baoyu.md`):

默认 WeWrite 自己生成的 `infographic-dense` 提示词够用(批产公众号正文配图的场景下)。**仅当以下任一条件满足时建议调用 `/baoyu-infographic`**:

| 触发条件 | 为什么 |
|---------|--------|
| 小红书 3:4 独立图文(一篇 = 6-7 张分 P 图) | baoyu 专为此优化,有完整分 P 工作流 |
| 用户手动说「这张图给我做得更精」「单独打磨这张」 | baoyu 的 analysis-framework 精度更高 |
| 复杂多维度数据(需要 12+ 元素,超过 WeWrite 推荐的 6-7) | baoyu 能处理周期表/生态图这种大信息量 |
| 用户关键词:「高密度信息大图」「小红书风格」「单图打磨」 | 关键词匹配 |

**不触发的场景**(WeWrite 自产就够):
- 公众号文章正文批量配图(一次 4-6 张需要视觉协调)
- 一周批产多篇文章
- 时间紧迫

**调用方式**(满足触发条件时):
1. 把该张图的 Section 结构(6-7 个模块内容)保存到临时 md 文件
2. `/baoyu-infographic <临时文件> --layout <layout> --style <style> --aspect 16:9 --lang zh`
3. 用返回的精细化 prompt 替换或补充 WeWrite 原输出的版本

**降级**：image_gen.py 支持多 provider 自动 fallback（按 config.yaml 中 providers 列表顺序尝试）。全部失败 → 输出提示词 + 备选图库关键词，继续。**提示词文件始终保留**，即使图片生成失败或被跳过。

---

### Step 7: 排版 + 发布

**7.1 Metadata 预检**（发布前必须通过）：

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| H1 标题 | 存在且 5-64 字节 | 自动修正或提示用户 |
| 摘要 | 存在且 ≤ 120 UTF-8 字节 | converter 自动生成 |
| 封面图 | 推送模式下需要 | 无封面则警告，仍可推送（微信会显示默认封面） |
| 正文字数 | ≥ 200 字 | 警告"内容过短，微信可能不收录" |
| 图片数量 | ≤ 10 张 | 超出则移除末尾多余图片 |

预检全部通过后才进入排版。

**7.2 排版 + 发布**：

**如果 `skip_publish = true`** → 直接走 preview。

```
读取: {skill_dir}/references/wechat-constraints.md
```

Converter 自动处理：CJK 加空格、加粗标点外移、列表转 section、外链转脚注、暗黑模式、容器语法。

```bash
# 发布
python3 {skill_dir}/toolkit/cli.py publish {markdown} --cover {cover} --theme {theme} --title "{title}" --digest "{digest}"

# 降级：本地预览
python3 {skill_dir}/toolkit/cli.py preview {markdown} --theme {theme} --no-open -o {output}.html
```

---

### Step 8: 收尾

**8.1 写入历史**（推送成功或降级都要写，文件不存在则创建）：

```yaml
# → {skill_dir}/history.yaml
- date: "{日期}"
  title: "{标题}"
  topic_source: "热点抓取"  # 或 "用户指定"
  topic_keywords: ["{词1}", "{词2}"]
  output_file: "{output 文件路径}"  # e.g. output/2026-03-31-zhangxue-slow-accumulation.md
  framework: "{框架}"
  enhance_strategy: "{增强策略}"  # angle_discovery/density_boost/detail_anchoring/real_feel
  word_count: {字数}
  media_id: "{id}"  # 降级时 null
  writing_persona: "{人格名}"
  dimensions:
    - "{维度}: {选项}"
  closing_type: "{收尾类型}"  # trailing_off/unanswered/scene_revert/abrupt_stop/anti_conclusion/image
  composite_score: {Step 5.3 的 composite_score}  # 0=质量高, 100=问题多
  writing_config_snapshot:  # 本次使用的关键参数（从 writing-config.yaml 提取）
    sentence_variance: {值}
    paragraph_rhythm: "{值}"
    emotional_arc: "{值}"
    word_temperature_bias: "{值}"
    broken_sentence_rate: {值}
    tangent_frequency: "{值}"
    style_drift: {值}
    negative_emotion_floor: {值}
  stats: null
```

**8.2 回复用户**：

- 最终标题 + 2 备选 + 摘要 + 5 标签 + media_id
- 编辑建议："文章有 2-3 个编辑锚点，建议加入你自己的话。你可以在本地 markdown 里改，也可以直接在微信草稿箱改——改完后说**'学习我的修改'**，WeWrite 都能学到你的风格。"
- **图片下一步**（标准回复模板，按此输出）：

  ```
  📸 图片生成（路径 1 · ChatGPT 网页，推荐）

  1. 提示词文件：output/{slug}-prompts.md
  2. 打开 chat.openai.com，把**封面创意 C**的英文提示词粘过去生成，下载后存为
     output/images/cover.png
  3. 依次把 N 张内文配图的英文提示词也粘过去生成，按 prompts.md 里标注的
     `存为` 字段命名（chart-1.png / chart-2.png / ...），放到 output/images/
  4. 存完立即预览：
     python3 toolkit/cli.py preview output/{slug}.md --theme {theme}
  5. 将来推送时 cli.py publish 会自动上传这些本地图到微信 CDN，无需手动处理

  如果想走路径 2（Gemini Advanced），同一份英文提示词直接粘到 gemini.google.com
  ```

**8.3 后续操作**：

| 用户说 | 动作 |
|--------|------|
| 润色/缩写/扩写/换语气 | 编辑文章 |
| 封面换暖色调 | 重新生图 |
| 用框架 B 重写 | 回到 Step 4 |
| 换一个选题 | 回到 Step 2.3 |
| 看看有什么主题 | `python3 {skill_dir}/toolkit/cli.py gallery` |
| 换成 XX 主题 | 重新渲染 |
| 看看文章数据 | `读取: {skill_dir}/references/effect-review.md` |
| 学习我的修改 | `读取: {skill_dir}/references/learn-edits.md`。支持本地 markdown 修改和微信草稿箱同步（`--from-wechat`） |
| 学习排版 / 学排版 | `python3 {skill_dir}/scripts/learn_theme.py <url> --name <name>` |
| 做一个小绿书/图片帖 | `python3 {skill_dir}/toolkit/cli.py image-post img1.jpg img2.jpg -t "标题"` |
| 检查一下 / 自检 / 这篇文章怎么样 | 生成报告（生成档案 + 质量检查，见辅助功能） |
| 导入范文 / 建范文库 | `python3 {skill_dir}/scripts/extract_exemplar.py article.md` |
| 查看范文库 | `python3 {skill_dir}/scripts/extract_exemplar.py --list` |

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
| 范文库为空 | Fallback 到 exemplar-seeds.yaml（通用模式） |
| 去 AI 验证 | 2 轮定向修复不过则跳过该项 |
| 生图失败 | 输出提示词 |
| 推送失败 | 本地 HTML |
| 历史写入 | 警告不阻断 |
| 效果数据 | 告知等 24h |
| Playbook 不存在 | 用 writing-guide.md |
