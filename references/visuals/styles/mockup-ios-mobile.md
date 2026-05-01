# mockup-ios-mobile · iOS 手机 UI 截图风

iPhone 屏幕真实截图美学:状态栏 + Dynamic Island + 安全区 + Home Indicator。适合让读者立刻识别"这是手机 app"。

## 视觉关键词

- iPhone status bar (顶部) · 时间 9:41 居左 · 信号 + WiFi + 电池居右
- Dynamic Island (iPhone 14 Pro+ 风格) · 顶部居中黑色胶囊 · 或 Notch (老款)
- Safe area insets · 内容不顶到边缘 · 上下留白
- Home Indicator (底部居中黑色横条 · 134×5px)
- Rounded screen corners (radius ~50px) · 屏幕本身大圆角
- iOS 17/18 style UI · 大标题 (Large Title) · 卡片式列表 · SF Pro 字体
- Tab bar (底部 · 可选) · 5 个 SF Symbol 图标
- Pill-shaped buttons · 16-20px 圆角
- Native iOS gestures hinted (swipe / long-press indicators)
- 整机外框可选 (Phone bezel) · 也可只画屏幕内

## 适用场景

- 移动端 app 教程 / iOS App 评测
- 微信 / 小红书 / 抖音类 mobile 体验描述
- 配 chart-2 / chart-3 展示具体功能交互
- 新功能 release 配图(如「ChatGPT iOS 新增 X 功能」)

## 配色建议

- 浅色:背景 #F2F2F7 (iOS systemGroupedBackground) · 卡片 #FFFFFF · 文字 #000 / 次 #8E8E93 · 强调 #007AFF
- 深色:背景 #000 · 卡片 #1C1C1E · 文字 #FFF · 强调 #0A84FF
- 状态栏 / Home indicator:浅色模式黑色 · 深色模式白色

## 避免

- 不要 Android Material Design(浮动按钮、汉堡菜单)
- 不要拟物化(iOS 7 之后已扁平)
- 不要忘记 Home Indicator 和 Dynamic Island — 这俩是辨识度最高的元素
- 不要画过窄过长(比例错了一眼假) · iPhone 比例约 19.5:9

## 示例 prompt 片段

> A photorealistic iPhone 15 Pro screenshot mockup, vertical 19.5:9 aspect ratio, top status bar with 9:41 time on left and signal/wifi/battery icons on right, Dynamic Island black pill at top center, safe area insets, screen corner radius 50px, iOS 17 design language with Large Title typography in SF Pro, card-based list UI, light gray background #F2F2F7 with white #FFFFFF cards, blue accent #007AFF, bottom Home Indicator (black horizontal bar 134×5px), optional bottom tab bar with SF Symbols, content showing [CONTENT], native iOS aesthetic, no Android elements
