# case-realistic · 案例文章拟真截图套件

**目的**:让读者第一眼相信「这是真实跑通的产品截图,不是 AI 画的 PPT」。
案例类(周三选题)涨粉的命门 — 信任 = 关注 + 加私域。

## 核心原则

1. **真实截图美学,不是插画美学**
   - photorealistic UI screenshot · sharp pixels · subtle imperfections
   - **避免**:艺术化滤镜 / 渐变光晕 / 卡通风格 / hand-drawn 笔触
2. **数字越具体越可信**
   - 用 `$12,847` 不要 `$12,000` · 用 `4,891 users` 不要 `5,000 users`
   - markdown 里就要写出来,prompt 直接抓占位符里的数字
3. **场景片段化 · 不全景**
   - 截一个 dashboard 局部 / 一段 terminal 输出 / 一条 Stripe 通知
   - 全景 dashboard 反而像 demo · 局部更像「随手截的真实工作流」
4. **信任三件套(每篇至少出现 2 件)**
   - 真实数字(指标/收入/用户数)
   - 真实时间戳(`2 hours ago` / `Today 14:32`)
   - 真实平台水印(macOS 顶栏 / iOS 状态栏 / Stripe logo)

---

## 5 张图配置(image_gen.py 调用)

### cover.png · 真实产品 UI 截图(macOS / iOS / 浏览器三选一)

**Layout**:`mockup-macos-app` 或 `mockup-ios-mobile` 或 浏览器 tab 截图
**Prompt 关键词**:

> ultra-realistic screenshot of [product name] interface, actual product UI, photorealistic 1x retina pixels, no artistic stylization, no painterly effects, looks like a real screen capture taken with macOS Screenshot tool, top-left traffic-light buttons (red #FF5F57 yellow #FEBC2E green #28C840), SF Pro typography, real timestamps visible, real numerical data, subtle window shadow, white space breathing room — DO NOT add illustrations, DO NOT add cartoon characters, DO NOT add decorative gradients

**中文承载**(2.35:1 封面格式):
- 主标题 10-16 字(从 H1 压缩 · 数字保留)
- 副标:「宸的 AI 掘金笔记」
- 真实截图占 60-70% 面积 · 文字叠在留白处

### chart-1.png · 真实数据图(analytics dashboard 风)

**Layout**:`dashboard` 或 `linear-progression`(数字大字突出)
**Prompt 关键词**:

> looks like a real analytics dashboard screenshot from Stripe / Mixpanel / Vercel / Linear / Notion, photorealistic UI, real specific numbers (not round), example: "Revenue $12,847.23" "Active Users 4,891" "MRR Growth +47.3%", subtle gradient charts (line / bar / sparkline), small UI details like timestamp "Updated 2 min ago" / data range selector, light mode preferred (looks more like screenshot), shadows and pixel-level UI accuracy, NO infographic flat illustration style

**强制**:数字必须从文章 markdown 抽出真实出现的数字 · auto_review.py 检查。

### chart-2.png · 功效对比图(before / after split-screen)

**Layout**:左右分屏 · 上下对比 · 或 timeline 30 天曲线
**Prompt 关键词**:

> split-screen before/after comparison, real metrics visible on both sides, example layout: LEFT "Before · Day 0" with metrics like "Daily users: 320 · Revenue: $48 · Bug count: 23" RIGHT "After · Day 30" with "Daily users: 4,891 · Revenue: $12,847 · Bug count: 2", looks like a Notion screenshot or Twitter screenshot, monochrome screenshot aesthetic with one accent color (green for after / red for before), NO illustration NO cartoon

**或者** 30 天增长曲线变体:

> realistic line chart screenshot showing 30-day growth curve, x-axis labeled with real dates (Apr 1, Apr 8, Apr 15, ...), y-axis with specific numbers, dramatic upward curve, looks like a screenshot from Vercel Analytics or Plausible dashboard, white background, single brand-color line

### chart-3.png · 真实操作截图(terminal / IDE / browser DevTools)

**Layout**:`mockup-terminal` 或 `mockup-code-editor` 或 浏览器开发者工具
**Prompt 关键词**:

> actual terminal session screenshot, real shell prompt "user@MacBook-Pro ~/project %", real command output with timestamps, git log entries with real hashes "a3f2c91 fix: race condition in payment webhook · 2 hours ago", monospace font (SF Mono / JetBrains Mono / Menlo), dark terminal theme #1E1E1E background, syntax highlighting matches the language being shown (TypeScript blue keywords / Python orange functions), DO NOT add cute icons, DO NOT add illustrations, looks like a real screenshot taken with cmd+shift+4

**或** VS Code / Cursor 截图变体:

> screenshot of VS Code editor with file tree on left, code editor in center, real TypeScript / Python code visible with syntax highlighting, breadcrumb showing real file path "src/api/checkout.ts", git diff gutter marks (green for added lines, red for removed), bottom status bar with branch name and line count, looks like a real screenshot

### chart-4.png · 真实结果证明(成功凭证截图)

**5 选 1 模板**(根据案例类型选):

A) **Stripe 收款通知**:
> realistic Stripe email notification screenshot or Stripe dashboard payment row, showing "Payment succeeded · $97.00 · 3 minutes ago · cus_xxx · pm_card_visa", clean white email/dashboard background, Stripe purple accent #635BFF, real email format with header "from: notifications@stripe.com"

B) **GitHub Stars 增长**:
> GitHub repository page screenshot showing star count "4,827 stars" + recent activity timeline + "trending today" badge, photorealistic screenshot of github.com layout, no illustration

C) **Twitter/X 互动证明**:
> Twitter post screenshot showing engagement metrics "12.4K views · 387 likes · 142 retweets · 28 replies", real timestamp "3:42 PM · Apr 22, 2026", clean white background X.com layout, real avatar circle

D) **WeChat 用户反馈截图**:
> realistic WeChat (微信) chat screenshot, green message bubbles on right (user's reply), white bubbles on left (other), Chinese text saying real-sounding feedback like "卧槽这个真好用,我下午就用上了 +1", iOS or macOS WeChat layout, status bar visible

E) **数据后台截图**(产品自带后台):
> realistic SaaS admin dashboard screenshot showing "30-day signups: 4,891 · conversion: 8.7% · MRR: $12,847", clean monochrome design with one brand accent, looks like Linear / Notion / Vercel admin

**默认 prefer A (Stripe)** · 因为读者最眼馋。

---

## 通用 negative prompt(所有 5 张共用)

附加到每张图的 negative_prompt(若 image_gen.py 支持):

> illustration, cartoon, painting, stylized art, watercolor, pencil sketch, 3d render, isometric, low-poly, abstract, decorative gradient, neon glow, halation, lens flare, motion blur, soft focus, dreamy aesthetic, hand-drawn, sketch lines, doodles, mascots, characters, skeuomorphism, glassmorphism over the top, excessive shadows

---

## 适用场景与不适用

**适用**(case_study category 默认走这个):
- 「我用 X 30 天做到 Y」类
- 「Z 功能真实测试结果」
- 「读者跟我反馈的成功案例」
- 「Cursor + Claude Code 实战 N 步」

**不适用**(走 mockup / infographic 即可):
- 纯方法论 / 理论分析
- 工具横向对比(走 ui-wireframe / mockup-* 多窗对比)
- 热点解读 / 观点文(走 infographic-dense 数据图)

---

## 人眼通过标准

**给一个不熟 AI 配图的朋友看 5 张图,问:**
1. 这是真实的截图吗?(目标:他答 yes 或迟疑)
2. 数字是真的吗?(目标:他点头说「这数字看起来挺合理的」)
3. 你觉得这产品跑通了吗?(目标:他答 yes)

3 个 yes = 通过 · 任一犹豫 = 重生这张图(调 prompt)。
