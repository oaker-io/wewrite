# 干货 / 教程 / 方法论 系列写作框架库(微信公众号长文版)

> 与 `frameworks.md`(热点观察 / 非共识解读)互补 —— 这份专门给**干货系列**用。
> 由 `write.py --style tutorial` 调用,bot 触发词:「教程: XX / 干货: XX / 方法论: XX / how to XX / 如何 XX / 手把手 XX」。
>
> **跨平台对应**(单向 vendor + 平台转化):
> - 本文(wewrite)= 微信公众号长文版 · T1-T5 · 2500-4500 字
> - `~/xwrite/references/frameworks/tutorial-thread.md` = X thread 版 · T1-T5(命名一致 · 转化 thread 节奏)
> - `~/xwrite/personas/tutorial-instructor.yaml` = X 平台 persona · 从本仓 `personas/tutorial-instructor.yaml` 适配
>
> 大主题建议**先公众号后 X thread**,引流互通(详见 xwrite 那边末尾「跟 wewrite 长文版的连接」)。

## 干货 vs 热点 · 一图看懂区别

| 维度 | 热点系列(hotspot) | **干货系列(tutorial)** |
|------|------------------|----------------------|
| 选题来源 | 微博/百度/今日头条热搜 + AI 白名单 | 用户手动 idea / changelog / 文档抓取 / 经验沉淀 |
| 目的 | 解读现象 · 给出非共识观察 | **教会读者具体怎么做** |
| 标题 | "豆包变豆脚了" / "字节的 ToC 算不过来的账" | "Claude Design 9 个官方文档没说的细节" / "手把手用 Cursor 接管你的代码库" |
| 字数 | 1800-2500 | **2500-4500**(教程通常需要更长结构) |
| 段落感 | 短句节奏 · 留白多 · 有情绪 | **结构感强 · 步骤明确 · 可复制** |
| 配图 layout | dense-modules / dashboard / story-mountain(信息密度型) | **linear-progression / comparison-matrix / hierarchical-layers / funnel / tree-branching**(操作流程型) |
| persona | midnight-friend / industry-observer / sharp-journalist | **tutorial-instructor**(老师式) |
| 文末 IP 卡 | 一致(智辰老师 + mp_brand 嵌入卡) | 一致 |
| 时效性 | 高(热搜 24h 内必发) | 低(教程长尾价值,可慢工出细活) |

---

## 5 套干货框架(选其一)

### 框架 T1: 步骤教程型(默认 · 80% 干货文用这个)

适合:**怎么用 / 怎么做 / 怎么配置 / 怎么实现** 类。

```
结构:
1. 开头(痛点 + 承诺)· 200-300 字
   - 第一句直接说「你想做的事」(不绕)
   - 第二段:为什么常见教程都没说清楚 / 为什么你之前试了没成
   - 末段:本文你能学到的具体清单(3-5 条 bullet)

2. 前置准备(H2)· 100-200 字
   - 需要装什么 / 需要会什么 / 需要哪些账号或 key
   - 列得**完整**(读者跟着走不卡壳)

3. 核心步骤 1-N(N 个 H2 · 每个 300-500 字)
   - 每步配一张 `chart-X` 配图(优先 `linear-progression` 或 mockup)
   - 步骤格式:【目标】→【操作】→【验证】→【常见坑】
   - 代码/命令/截图描述 inline
   - 结尾一句话总结这步「关键判断点」

4. 进阶玩法(H2 · 可选)· 300-500 字
   - 同样的方法可以用在哪些类似场景
   - 高手会怎么用(放 1-2 个高级技巧 · 不展开)

5. 避坑清单(H2)· 200-400 字
   - 5-8 条「我踩过的坑」(具体到错误信息 / 报错截图描述)
   - 每条:【现象】+【原因】+【解决】

6. 结尾(行动 + IP 引流)· 100 字
   - 「你现在可以立即试一下 X」
   - aipickgold + 私域引流(用 sanitize 兜底)
```

**配图推荐**:封面 + 4 张 chart
- `cover.png` — 用 `bento-grid` 或 `dashboard` 给出本文 4-5 个核心要点速览
- `chart-1.png` — `linear-progression`(整体流程图)
- `chart-2.png` — `comparison-matrix`(本方法 vs 常规方法对比)
- `chart-3.png` — UI mockup 或 `dense-modules`(关键步骤截图描述)
- `chart-4.png` — `funnel` 或 `tree-branching`(避坑决策树)

---

### 框架 T2: 工具评测型

适合:**新工具上手 / 横向对比 / N 选 1 决策** 类。

```
结构:
1. 开头(为什么写)· 150-250 字
   - 这个工具/产品/服务最近在哪看到的(锚点)
   - 我用它做什么,用了多久(可信度)
   - 本文谁该读、谁不用读(筛选读者)

2. 它解决什么问题(H2)· 200-400 字
   - 一句话定位
   - 跟同类产品的本质差异(不是 feature list · 是定位差异)

3. 实测 N 个核心场景(N 个 H3 · 每个 300 字)
   - 场景描述 → 操作过程 → 结果(配截图描述)
   - 评分:推荐度 ★★★★☆ / 学习成本 ★★☆☆☆ / 替代方案

4. 跟主流方案对比(H2)· 400-600 字
   - 一张 `comparison-matrix` 表
   - 5-8 个维度横向对比(价格/功能/学习成本/适用场景/生态)
   - 给出「在 X 场景选 A · 在 Y 场景选 B」的明确建议

5. 我的最终判断(H2)· 200-300 字
   - 谁该立即用 / 谁该等等 / 谁不要用
   - 带一个个人经验式的判断(避免「都挺好」)

6. 结尾(IP 引流)
```

**配图推荐**:
- `cover.png` — 工具 logo / mockup + 评分卡
- `chart-1.png` — `comparison-matrix`(横向对比表)
- `chart-2.png` — `dashboard`(评分四维)
- `chart-3.png` — `tree-branching`(谁该用决策树)

---

### 框架 T3: 方法论沉淀型

适合:**经验总结 / 心法 / 框架抽象** 类。

```
结构:
1. 开头(故事钩子)· 200 字
   - 一个具体的失败/成功故事
   - 引出本文要讲的那个方法论

2. 提出 N 个原则(N 个 H2 · 每个 250-400 字)
   - 原则 1:【一句话核心】 + 为什么 + 一个反例(不这样会怎样) + 一个正例
   - 原则 2-N:同上结构

3. 怎么落地(H2)· 300-500 字
   - 把上面 N 个原则编成一个 checklist 或 SOP
   - 给出第一步今晚就能做的具体动作

4. 边界条件(H2)· 200-300 字
   - 这套方法在什么场景**不适用**(防止读者教条)
   - 适用边界 + 反例

5. 结尾(IP 引流)
```

**配图推荐**:
- `cover.png` — 方法论核心图(`hub-spoke` 或 `hierarchical-layers`)
- `chart-1.png` — `hub-spoke`(N 原则一图看)
- `chart-2.png` — `linear-progression`(SOP checklist)
- `chart-3.png` — `binary-comparison`(适用 vs 不适用边界)

---

### 框架 T4: 知识科普型

适合:**讲清一个概念 / 一个技术 / 一个原理** 类。

```
结构:
1. 开头(类比切入)· 200 字
   - 用一个生活类比让读者瞬间懂大概(eg.「Transformer 就像同传译员」)
   - 提示本文不会太硬

2. 它到底是什么(H2)· 300-500 字
   - 一句话定义(不超过 30 字)
   - 三层递进:外行版 / 入门版 / 工程师版
   - 配图:`isometric-map` 或 `iceberg`(冰山下的复杂度)

3. 它怎么工作(H2)· 400-600 字
   - 拆 3-5 个组件,每个一两句讲清
   - 用 `circular-flow` 或 `linear-progression` 串起来

4. 它为什么火 / 为什么重要(H2)· 200-400 字
   - 解决了什么以前解决不了的问题
   - 不是「它好」是「它独有」

5. 学习路径(H2)· 200 字
   - 入门 → 中级 → 高级 三档资源(每档 2-3 个具体链接/书)

6. 结尾(IP 引流)
```

**配图推荐**:
- `chart-1.png` — `iceberg`(表面 vs 底层)
- `chart-2.png` — `circular-flow`(运行机制)
- `chart-3.png` — `linear-progression`(学习路径)

---

### 框架 T5: 避坑清单型

适合:**「N 个最常见错误」/「我用 X 个月学到的 N 件事」** 类。

```
结构:
1. 开头(身份 + 资格)· 150 字
   - 我做这件事多久 / 踩了多少坑(可信度)
   - 本文给谁读

2. N 个坑(N 个 H2 · 每个 200-300 字 · N 推荐 5-9)
   - 坑 X:【现象描述】+【为什么会犯】+【正确做法】
   - 每个坑都有「具体场景」+「具体后果」

3. 总结(H2)· 200 字
   - 把 N 个坑归成 2-3 个底层规律
   - 给出一个「避坑速查表」

4. 结尾(IP 引流)
```

**配图推荐**:
- `cover.png` — `bento-grid` 速览 N 坑
- `chart-1.png` — `dense-modules`(N 个坑 + 解决一图看)
- `chart-2.png` — `funnel`(坑出现的频率排序)

---

## 干货系列 layout 优先度排行(给 AI 选图时参考)

按**适配教程场景**的优先度:

| Layout | 干货系列适用度 | 典型用法 |
|--------|--------------|---------|
| `linear-progression` | ★★★★★ | 步骤流程 / SOP / 学习路径 |
| `comparison-matrix` | ★★★★★ | 工具横评 / 方案对比 / before-after |
| `hierarchical-layers` | ★★★★★ | 知识体系 / 前置依赖 / 三层递进 |
| `funnel` | ★★★★ | 筛选决策 / 优先级排序 |
| `tree-branching` | ★★★★ | 选择决策树 / 条件分支 |
| `circular-flow` | ★★★★ | 反馈循环 / 工作机制 |
| `bento-grid` | ★★★★ | 教程目录速览 / N 个要点速览 |
| `iceberg` | ★★★ | 表象 vs 底层 / 知识层次 |
| `hub-spoke` | ★★★ | 中心方法论 + 周边支撑 |
| `dense-modules` | ★★★ | 避坑大全 / 多维盘点 |
| `dashboard` | ★★★ | 工具评分 / 多维评估 |
| `binary-comparison` | ★★ | 二选一决策 |
| 其他(comic-strip / story-mountain 等) | ★ | 教程通常不用 |

---

## 干货系列封面规则

封面**主标题就是文章标题**,不要副标题缩写。
- 推荐 layout:`bento-grid`(N 个要点速览)/ `dashboard`(评分卡)/ `comparison-matrix`(对比表)
- 推荐 style:`ikea-manual`(说明书风格 · 教程感强)/ `chalkboard`(黑板风 · 教学感)/ `corporate-memphis`(简洁专业)
- 避免 style:`kawaii` / `claymation` / `cyberpunk-neon`(干货系列要严肃感)

---

## 与 sanitize 的协作

`toolkit/sanitize.py` 的四件套(去 H1 / 清 cover alt / 兜底 author-card / 补 mp_brand)
对干货系列同样生效。文末的智辰老师介绍卡和热点系列**完全一致**(IP 不分系列)。
