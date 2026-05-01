# mockup-code-editor · VSCode/Cursor 代码编辑器截图风

VSCode / Cursor / Zed 风格代码编辑器截图美学:左侧文件树 + 中间代码 + 右侧 outline/AI chat。适合一眼认出"这是真实写代码场景"。

## 视觉关键词

- Three-panel layout: 左 file tree (240px) · 中 editor (主区) · 右 outline 或 AI chat panel (320px · 可选)
- Activity bar 最左侧 (48px) · 垂直图标(文件 / 搜索 / git / extension / settings)
- File tree · 树形展开 · 文件夹图标 · 当前文件高亮(蓝色背景)
- Editor area · monospace 代码 · 行号灰色 · 当前行浅高亮
- Syntax highlighting · 关键字紫/蓝 · 字符串绿 · 注释灰斜体 · 函数名黄
- Tab bar 顶部 · 多个文件 tab · 当前 tab 下划线 · 改动有圆点未保存标记
- Right panel 可选:Cursor/Copilot AI chat (对话气泡 + 代码 diff) · 或 outline 树
- Bottom status bar · git branch · errors/warnings · cursor position · language mode
- Minimap (右侧细窄缩略图 · 可选)
- 整体深色为主 · 体现专业开发氛围

## 适用场景

- AI Coding 教程(Cursor / Claude Code / Copilot 实战)
- 代码示例展示 / refactor before-after
- IDE 配置 / 插件推荐 / 主题截图
- T1 步骤教程展示具体代码 · T2 工具评测(IDE 对比)

## 配色建议

- VSCode Dark+:背景 #1E1E1E · 侧边 #252526 · activity bar #333333 · 选中 #094771 · 关键字 #569CD6 · 字符串 #CE9178 · 注释 #6A9955 · 函数 #DCDCAA
- Cursor / One Dark Pro:背景 #282C34 · 关键字 #C678DD · 字符串 #98C379 · 函数 #61AFEF · 注释 #5C6370 (italic)
- 浅色版(Light+ / GitHub Light):背景 #FFFFFF · 关键字 #0000FF · 字符串 #A31515 · 注释 #008000

## 避免

- 不要画成简单的代码块 — 必须有 IDE chrome (file tree + tab bar + status bar)
- 不要漏行号 / activity bar — 这俩是 VSCode 辨识度最高的元素
- 不要等比字体写代码 — 必须 monospace
- 不要把所有面板塞满 — 留白让重点突出(eg 只画 file tree + editor 也行)

## 示例 prompt 片段

> A photorealistic VSCode / Cursor code editor screenshot, three-panel layout: leftmost activity bar (48px wide with vertical icons), file tree sidebar (240px, dark #252526, folder tree with current file highlighted blue #094771), main editor area showing [CODE] with monospace JetBrains Mono font, syntax highlighting (purple keywords #C678DD, green strings #98C379, italic gray comments #5C6370, yellow functions #DCDCAA), gray line numbers, top tab bar with multiple file tabs (current one underlined), bottom status bar showing git branch and language mode, optional right panel showing Cursor AI chat with diff suggestion, dark background #1E1E1E, professional developer IDE aesthetic, retina-sharp pixels
