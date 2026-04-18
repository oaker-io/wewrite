# WeWrite 视觉资源 · Layout × Style

用于 `infographic-dense` 模式下的**高密度多模块信息图**生成。给 agent 在 Step 6 组装提示词时参考。

## 结构

- `layouts/*.md`(21 种)— **信息架构**:模块怎么排布
- `styles/*.md`(20 种)— **视觉美学**:怎么画才好看
- `base-prompt.md` — 合成提示词的主模板(`{{LAYOUT}}` × `{{STYLE}}` × `{{CONTENT}}`)
- `structured-content-template.md` — 把文章内容拆成 "Key Concept / Content / Visual / Text Labels" 的方法
- `analysis-framework.md` — 内容分析框架

一张图 = 1 个 layout × 1 个 style。例:`dense-modules × pop-laboratory` = 6 模块科技感蓝图。

## 致谢

本目录下的 **layout 和 style 资源来自 [baoyu-infographic](https://github.com/JimLiu/baoyu-skills) by [@baoyu(刘宝玉)](https://github.com/JimLiu)**,WeWrite 完整 vendor 了 21 layout + 20 style 作为视觉决策菜单。每个文件顶部保留原作归属注释。

感谢宝玉老师的开源分享。原项目包含完整的 SKILL.md 和 TypeScript 图像生成调用,是公众号视觉工作流最好的参考。如果原作者希望本项目调整使用方式,欢迎发 issue。

## WeWrite 的使用方式

1. SKILL.md Step 6.1b 根据文章类型推荐 layout + style 搭配(推荐组合见下方菜单)
2. Step 6.4 读取对应 `layouts/{name}.md` 和 `styles/{name}.md`,把其中的结构规则 + 视觉关键词填进 `infographic-dense` 模板
3. 输出到 `output/{slug}-prompts.md`,用户按路径 1/2/3 生图

---

## Layout 完整菜单(21 种)

按**信息架构类型**分组:

| 组 | Layout | 说明 | WeWrite 优先度 |
|----|--------|------|---------------|
| **高密度** | `dense-modules` | 6-7 模块,多维度盘点 · 避坑大全 | ★★★★★ |
| | `bento-grid` | 不规则便当格,标签云感 | ★★★★ |
| | `comparison-matrix` | 横向对比表 | ★★★★★ |
| | `dashboard` | KPI + 辅助小卡 | ★★★★ |
| | `periodic-table` | 元素周期表式归类 | ★★★ |
| **流程** | `linear-progression` | 线性步骤 | ★★★ |
| | `circular-flow` | 循环流程 | ★★ |
| | `funnel` | 漏斗/转化 | ★★★ |
| | `winding-roadmap` | 蜿蜒路线图 | ★★ |
| | `bridge` | A→B 桥接 | ★★ |
| **层级** | `hierarchical-layers` | 分层堆叠 | ★★★ |
| | `structural-breakdown` | 结构分解 | ★★ |
| | `tree-branching` | 树状分支 | ★★ |
| | `hub-spoke` | 中心放射 | ★★★ |
| **对比** | `binary-comparison` | 二元对比 | ★★★ |
| | `venn-diagram` | 文氏图 | ★★ |
| **隐喻** | `iceberg` | 冰山(表象/深层) | ★★★ |
| | `isometric-map` | 等距地图 | ★★ |
| | `jigsaw` | 拼图 | ★★ |
| | `story-mountain` | 故事山(起伏) | ★★★ |
| | `comic-strip` | 连环漫画 | ★★ |

## Style 完整菜单(20 种)

按**调性**分组:

| 组 | Style | 说明 | WeWrite 优先度 |
|----|-------|------|---------------|
| **科技/专业** | `pop-laboratory` | 蓝图网格 + 坐标标签(默认首选) | ★★★★★ |
| | `technical-schematic` | 工程原理图 | ★★★★ |
| | `ui-wireframe` | UI 线框 | ★★★ |
| | `cyberpunk-neon` | 赛博霓虹 | ★★★ |
| | `corporate-memphis` | 孟菲斯商业扁平 | ★★★★ |
| **文艺** | `morandi-journal` | 莫兰迪 + 手绘日记 | ★★★★ |
| | `aged-academia` | 复古学术 | ★★★ |
| | `storybook-watercolor` | 绘本水彩 | ★★★ |
| | `chalkboard` | 黑板粉笔 | ★★ |
| **活泼** | `retro-pop-grid` | 70s 波普 | ★★★★ |
| | `bold-graphic` | 大胆平面 | ★★★ |
| | `kawaii` | 可爱风 | ★★★ |
| | `claymation` | 粘土 | ★★ |
| | `pixel-art` | 像素艺术 | ★★ |
| **实用** | `ikea-manual` | 宜家说明书简笔 | ★★★★ |
| | `knolling` | 物品俯拍平铺 | ★★★ |
| | `lego-brick` | 乐高积木 | ★★ |
| | `origami` | 折纸 | ★★ |
| | `craft-handmade` | 手工质感 | ★★ |
| | `subway-map` | 地铁图 | ★★★ |

## 推荐搭配(WeWrite 场景)

| 文章类型 | Layout | Style | 备注 |
|---------|--------|-------|------|
| 科技/AI 分析 | `dense-modules` / `dashboard` | `pop-laboratory` | 数据感强 |
| 工具评测/对比 | `comparison-matrix` / `binary-comparison` | `corporate-memphis` / `ui-wireframe` | 清晰专业 |
| 产品盘点/榜单 | `bento-grid` / `periodic-table` | `retro-pop-grid` / `corporate-memphis` | 信息丰富 |
| 深度观点/趋势 | `iceberg` / `story-mountain` | `aged-academia` / `morandi-journal` | 有层次 |
| 教程/Step by Step | `linear-progression` / `hub-spoke` | `ikea-manual` / `chalkboard` | 清楚易懂 |
| 情感/生活 | `circular-flow` / `jigsaw` | `storybook-watercolor` / `kawaii` | 温暖 |

Agent 可以自由尝试其他组合,但一旦选定就必须填完整 Layout 模块结构 + Style 视觉关键词到 prompt 里。
