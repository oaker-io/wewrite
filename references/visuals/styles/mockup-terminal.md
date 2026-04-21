# mockup-terminal · 终端窗口截图风

iTerm2 / Warp / Ghostty 风格的终端模拟器截图美学:深色背景 + 等宽字体 + 命令高亮 + 提示符 `$`。适合一眼认出"这是真实命令行操作"。

## 视觉关键词

- Terminal window with traffic-light buttons top-left (macOS-style) · 或 tab bar (Warp 风格)
- Dark background · 默认 #1E1E1E 或 deep navy #0D1117
- Monospace font · JetBrains Mono / Fira Code / SF Mono · ligature 启用
- Prompt line: `$ ` 或 `➜ ~/project ` 或 `user@mac:~$ ` · 颜色高亮
- 命令本体 · 白色或浅色
- Output 区 · 多行文本 · 包含 ANSI color (红 error / 绿 success / 黄 warning / 蓝 info)
- Syntax highlighting on commands (flag 高亮 · 字符串引号高亮)
- Cursor block (▊) 闪烁感 · 静态画面也可画一个
- Optional: tab bar at top (multiple sessions) · status bar at bottom (git branch / time)
- Window padding 16-20px · 内容不贴边

## 适用场景

- DevOps / CLI 工具教程(git / docker / kubectl / brew)
- shell 脚本 / dotfiles / 终端配置类
- AI CLI(Claude Code / aider / cursor-agent)操作演示
- T1 步骤教程的 chart-2/3(展示具体命令)

## 配色建议

- One Dark:背景 #282C34 · prompt 绿 #98C379 · 命令白 #ABB2BF · error 红 #E06C75 · string 黄 #E5C07B
- Dracula:背景 #282A36 · prompt 紫 #BD93F9 · 命令白 #F8F8F2 · error 红 #FF5555 · string 黄 #F1FA8C
- Solarized Dark:背景 #002B36 · prompt cyan #2AA198 · 命令 #93A1A1 · 强调 yellow #B58900

## 避免

- 不要等比例字体(Helvetica / Arial)— 终端必须 monospace
- 不要太花哨 ANSI(全屏彩虹色不真实)· 真实命令行只在关键处着色
- 不要画 GUI 按钮 — 终端的精髓是纯文本
- 不要忘记 prompt 起手符 — 没 `$` / `➜` 一眼假

## 示例 prompt 片段

> A photorealistic terminal emulator screenshot in iTerm2 / Warp style, dark background #1E1E1E, traffic-light buttons top-left, JetBrains Mono monospace typography with ligatures, multiple prompt lines starting with green `➜ ~/project` followed by white commands like `[COMMAND]`, syntax-highlighted output below (green success, red errors, yellow warnings), 16px window padding, optional bottom status bar showing git branch, blinking cursor block, One Dark color theme, authentic developer aesthetic, no GUI buttons, pure text terminal feel
