# cover-square · 1:1 看一看 thumb 小图

**用途**:微信「看一看」/ 订阅号首页 / 公众号 feed 右侧 thumb 缩略位 显示的小图。
当前 cover.png 是 2.35:1(宽屏)· 在右侧 80×80 thumb 位会**自动裁剪**导致关键文字糊掉。
**解决**:多生 1 张 1:1 (1080×1080) 用作 thumb_media_id。

> 短文(副推位)**只用 cover-square** · 不需要 cover.png(短文不显示大封面)。
> 长文(主推)**两张都生** · cover.png 用于内文首图 + cover-square.png 用作 thumb。

## 🚨 强制 T2 workflow(2026-04-25 修)

**LLM 直接生中文大字不可控** · 实测字漏 / 字小 / 被复杂背景压住 · 在 mp 列表 80×80 缩略时
关键文字看不清 · 转化率受影响。

**所有 cover-square.png 必须走 T2(raw + overlay)流程** · 跟 `chart-N.png` 同套路:

```
1. LLM 生 cover-square-raw.png      · 只生「无字纯背景」(纯色 / 简单纹理 / 单图标)· 不写任何文字
2. LLM 生 cover-square.overlay.json · Pillow 文字层 spec(主标 8-10 字居中 + 底部 brand 小字)
3. images.py 跑 toolkit/overlay_text.py    · raw + overlay → cover-square.png(像素级控字大小+位置)
```

**overlay.json 必填字段**(主标必须落在中央 60% 区域 · 防 80×80 裁切时漏):
```json
{
  "size": [1080, 1080],
  "layers": [
    {"text": "<主标 8-10 字>", "x": 540, "y": 540, "anchor": "mm",
     "weight": "Heavy", "size": 160, "color": "<深色>"},
    {"text": "宸的 AI 掘金笔记", "x": 540, "y": 980, "anchor": "mm",
     "weight": "Regular", "size": 32, "color": "#888888"}
  ]
}
```

**为啥 size: 160?**:1080 / 8 字 = 135px,留点余量到 160 · 80×80 缩略时仍占 12px(可读)。

## 视觉规则(LLM 只管 raw 背景)

```
画布尺寸  · 1080 × 1080 (1:1)
LLM 任务  · 生纯背景(深蓝 / 浅灰白 / 暖色 / 白底 / 撞色对比 等 5 套之一)· **零文字**
Pillow 任务 · 主标 8-10 字 · 字号 140-180px · 居中
            副标 「宸的 AI 掘金笔记」 · 字号 28-36px · 底部居中
            版权 「智辰 · 2026」 · 字号 16-20px · 右下角(可选)
```

### 跟 cover.png (2.35:1) 的差异表

| 维度 | cover.png (2.35:1) | cover-square.png (1:1) |
|---|---|---|
| 尺寸 | 2150×915 (推荐) | 1080×1080 |
| 主标字数 | 10-16 字 | **8-10 字**(极致压缩) |
| 主标字号 | 60-80pt | **120-180pt**(更大 · 因为画布小但要看清) |
| 副标位置 | 右下角 | 底部居中 |
| 留白 | 横向铺开 · 适合长标题 | 上下垂直留白 · 中央大字 |
| 视觉风格 | 跟正文协调 | 高对比 · 适合 80×80 缩略 |

## 5 套 cover-square 风格(对应主推 5 类)

### 1) 干货 / 教程类(周一 / 周二)

```
布局:深色背景 + 白色超大字
背景:#1A2332 (深蓝) · 或 #0F0F0F (近黑)
文字:白色 / 主色加粗
辅助:角落 1 个小图标(齿轮 / 工具 / 步骤数)

prompt 关键词:
  bold typography poster, 1:1 square, dark navy background #1A2332,
  large white Chinese title (8-10 characters), centered composition,
  minimalist single accent icon corner, ultra-clean, no clutter,
  designed for 80x80 thumbnail readability
```

示例标题压缩:
- 「Claude Code 完整 SOP」→「Claude Code 全 SOP」(7 字)
- 「N 分钟用 X 做到 Y」→「N 分钟做完 Y」(6-8 字)

### 2) 案例 / 复盘类(周三 ★)

```
布局:数字大字 + 时间戳 + 真实截图风
背景:浅灰白 #F5F5F7 (像 macOS 截图)
主体:大数字 +「Day 30」/「+$12,847」
辅助:左上角时间戳 / 右下角小图标

prompt 关键词:
  realistic dashboard screenshot aesthetic, 1:1 square, light background,
  giant central number/metric (e.g. "$12,847" or "Day 30"), small Chinese
  caption above the number (4-6 chars), tiny timestamp top-left,
  photorealistic UI elements, NO illustrations
```

示例标题压缩:
- 「30 天 Cursor 复盘 · 完整账单」→「Day 30 · $12,847」(数字优先)
- 「我用 X 一周搞了 $N」→「7 天 · $N 实战」

### 3) 工具评测 / 对比类(周四)

```
布局:左右对比 · VS 大字
背景:对半分屏 (左浅右深 / 或两个产品色)
主体:左 「工具 A」+ 中间「VS」+ 右「工具 B」
辅助:底部一句结论(7-10 字)

prompt 关键词:
  split-screen comparison poster, 1:1 square, two halves with contrast,
  giant "VS" in center, two product names left and right (3-5 chars each),
  minimal accent colors, bold sans-serif Chinese typography
```

示例标题压缩:
- 「Cursor vs Windsurf 实测」→「Cursor VS Windsurf」
- 「Claude 4.7 vs GPT-5 N 测」→「4.7 VS 5 · N 测」

### 4) 热点解读类(周五)

```
布局:话题大字 + 红点强调
背景:对比强烈(白底黑字 + 1 处红色)
主体:核心话题 6-8 字
辅助:右下「智辰解读」/ 「非共识」标签

prompt 关键词:
  punchy editorial cover, 1:1 square, white background, giant bold black
  Chinese title (6-8 chars), one strategic red accent dot or small banner
  "非共识" stamp, newspaper editorial aesthetic, high contrast
```

### 5) 轻量分享 / 合集类(周六 / 周日)

```
布局:数字 + 文字 (eg「5 个工具」「10 条收获」)
背景:暖色 (浅黄 / 浅粉) · 跟严肃干货拉开距离
主体:大数字 + 单位
辅助:小图标点缀(工具图 / 礼物 / 列表)

prompt 关键词:
  friendly listicle cover, 1:1 square, warm background (cream / light pink),
  giant number prominent (e.g. "5"), unit text below ("个工具" / "条收获"),
  one cute small icon, casual Chinese typography, approachable mood
```

## 通用 negative prompt(所有 1:1 cover 共用)

```
ANY text or numbers (Pillow 后处理 · LLM 不写字 · 写了也会被覆盖),
illustration, cartoon, painting, watercolor, abstract, decorative gradient,
neon glow, lens flare, hand-drawn, sketch, doodles, mascot characters,
small text overlays, dense info graphic (1:1 太小放不下), busy composition,
multi-column layout (1:1 不适合多列)
```

**关键:LLM 写中文字 = 漏字 · 全部交 Pillow** · 见上方「强制 T2 workflow」段。

## 80×80 thumbnail readability 自检

设计完后**必须做这一步**:把图片缩到 80×80 px 看 — 关键信息(主数字 / 主标题前 4 字)还能不能看清?
看不清 → 字加大 / 删次要元素。

## 工程实现

`scripts/workflow/images.py` 跑配图时:
- 主推:生 `cover.png` (2.35:1) + `cover-square.png` (1:1)
- 短文(副推):**只生** `cover-square.png` · 不生 `cover.png`
- 案例(周三):cover.png 走 `case-realistic.md` 的真实 UI 截图美学;
            cover-square.png 走本文「2) 案例 / 复盘类」(数字大字)
