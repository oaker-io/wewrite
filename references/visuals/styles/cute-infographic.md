# cute-infographic · 萌系角色信息图风(参考极客杰尼范文)

> 案例文 / 概念解释类的另一种封面风(跟 case-realistic 拟真截图风互补)。
> 极客杰尼《养虾的虾塘管理系统》一篇 · 用萌系龙虾角色把 Agent 系统讲清楚 ·
> 87 转发 · 11 评论 · 涨粉效率比拟真截图还高一档(因为「易传播 · 不严肃」)。

## 适用场景

**用 cute-infographic** 当:
- 主题是一个**复杂系统 / 抽象概念** · 需要打比方讲清楚
- 主题是**用户角色多** · 需要拟人化 (eg「Agent」「调度器」「数据库」)
- 主题面向**新手 / 小白** · 严肃截图反而把人吓跑
- 想做「易传播 / 朋友圈转发型」内容

**不用** cute-infographic 当:
- 案例文「真实跑通」需要严肃可信感(用 case-realistic)
- 评测对比需要 UI 截图凭据(用 mockup-*)
- 数据快讯需要数字凸显(用 infographic-dense)

## 视觉关键词

```
插画风  · cartoon illustration / friendly mascot / hand-drawn quality
萌系    · cute / chibi / kawaii / round shapes
主体    · 1-3 个拟人化角色(动物 / 物品)· 表情夸张
布局    · 信息图风(标题 + 角色互动 + 流程箭头)
色板    · 暖色系(橙 / 黄 / 浅蓝 · 不要冷调)
线条    · 手绘感 · 略歪 · 不要工业 SVG 那种死板
```

## 5 个 layout 模板(参考极客杰尼范文)

### 1) 角色 + 痛点 4 宫格(开场图)

```
布局:2×2 宫格 · 每格一个角色 + 一个具体痛点
画风:同一萌系角色 N 个状态(开心 / 生气 / 累瘫 / 无奈)
文字:每格 1 句小标题 + 1 行说明

prompt 示例:
  cute cartoon infographic, 4-quadrant layout, same friendly mascot
  character (e.g. red lobster / shrimp / cat) showing 4 different
  expressions and situations, each quadrant has a small Chinese caption
  (10-15 chars), warm color palette (orange / yellow / soft blue),
  hand-drawn style, friendly and approachable, NOT corporate
```

参考极客杰尼:「养龙虾遇到的烦恼」 4 宫格 · 4 只龙虾 4 个表情 · 4 个痛点说明

### 2) 系统架构拟人图(Agent 类系统)

```
布局:中心控制台(像电脑屏) + 周围多个角色排队 / 互动
画风:中心是一个机械感角色 (eg 调度员 / 控制台机器人)
       周围是若干小角色排队领任务 / 提交结果
文字:每个角色头上一个小气泡 (1-3 字 · eg 「领任务」「打回」「卡住」)
箭头:虚线 / 实线 流程方向

prompt 示例:
  cute cartoon system architecture infographic, central control panel
  with friendly robot / scheduler character, surrounding small mascot
  characters queuing or interacting with the panel, each character has
  a small speech bubble (3-5 Chinese chars), flow arrows connecting
  them, hand-drawn whimsical style, warm color palette
```

参考极客杰尼:「Agent-Nexus = 虾塘管家系统」· 中心是控制台 · 周围 8 只龙虾排队领任务

### 3) 时间流程横排(SOP / 步骤教程)

```
布局:从左到右 5-7 个步骤 · 每步一个小角色 + 1 行说明
画风:同一角色不同动作(走路 / 思考 / 打字 / 打勾)
       步骤间用小箭头连接
文字:每步上方 1 个步骤标题 (eg 「Step 1: 立项」)
       下方 1 行说明 (1 句话)

prompt 示例:
  cute cartoon step-by-step horizontal flow infographic, 5-7 steps
  left-to-right, same friendly mascot in different action poses for
  each step (planning / writing / running / verifying / done), small
  arrows between steps, each step has Chinese title + 1 line caption,
  hand-drawn style, warm palette, friendly mood
```

参考极客杰尼:「龙虾干活五步走」· 横排 5 个步骤 · 5 只龙虾不同姿态

### 4) 「之前 vs 之后」对比图

```
布局:左右分屏 · 左边「混乱」 · 右边「有序」
画风:同一场景两种状态
       左边:角色四散 / 混乱 / 表情焦虑
       右边:角色排队 / 有序 / 表情开心
文字:左下「<之前状态>」 · 右下「<之后状态>」
       中间一个 「→」 或「VS」

prompt 示例:
  cute cartoon before/after comparison infographic, split-screen layout,
  LEFT side shows chaotic scene with characters scattered and worried
  expressions, RIGHT side shows organized scene with same characters
  lined up and happy expressions, central arrow or VS divider, Chinese
  captions below each side, hand-drawn warm palette
```

参考极客杰尼:「混乱的虾塘 vs 有序的虾塘」

### 5) 角色介绍卡(单角色全身图)

```
布局:中央 1 个大角色全身像 + 周围标签
画风:一个 60% 画布的萌系角色 · 表情饱满
       周围 4-6 个小标签指向角色不同部位(像漫画角色卡)
文字:角色名(大字)+ 4-6 个特征标签

prompt 示例:
  cute cartoon character profile card, 1:1 layout, central full-body
  mascot character (e.g. red lobster / robot / cat) taking 60% of canvas,
  4-6 small label tags pointing to different parts of the character
  with Chinese trait labels (e.g. "敢拼 · 抗压 · 坚持"), name plate at
  top, hand-drawn whimsical style, warm color palette
```

## 使用建议

- **每篇案例文最多 2 张 cute-infographic**(其余仍用 case-realistic 真实截图)
- **cover.png 用 cute-infographic** · cover-square.png 仍用「数字大字风」(thumb 要清)
- chart-1 用 「角色 + 痛点 4 宫格」铺开问题
- chart-2 用「系统架构拟人图」讲清楚方案
- chart-3 / chart-4 回到 case-realistic 拟真截图(给信任感凭据)

## 通用 negative prompt

```
photorealistic, photo, screenshot, UI mockup, corporate flat design,
3D render, isometric, technical schematic, dense data infographic,
small text overlays (萌系图字要大), realistic shadows
```

## 工程实现

`scripts/workflow/images.py` 加 `--style narrative` · 走 cute-infographic prompt。
auto-schedule.yaml 案例日 (周三) 主推可选:
```yaml
image_style: case-realistic    # 严肃可信(默认)
# 或
image_style: cute-infographic  # 萌系易传播(转发率更高)
```

切换:编辑 yaml 即可 · 第二天生效。
