# WeWrite Sub-Agent 团队

WeWrite 6 个专门子 agent · 每个负责一个具体环节 · 主线程(Claude / 你)在协作时可以
delegate 给它们,避免一把抓。

## 6 个 agent

| Agent | 职责 | 何时调 |
|---|---|---|
| `topic-curator` | 选题守门 · 6 大主题判定 | 每次 idea 入候选前 / 用户提新选题 |
| `hook-writer` | 5 个开篇钩子候选 | 文章开写前 · 或要换钩子时 |
| `kol-pattern-analyst` | 单篇 KOL 文章深度拆解 | 看到值得学的 KOL 文 · 想抽其招式 |
| `review-critic` | 发布前最后一关(7 维度) | publish 前 · 或问"这篇能发吗" |
| `revise-editor` | 外科改稿(动几段不重写) | 用户说"改 X" "加段 Y" "重写钩子" |
| `visual-art-director` | 视觉决策(layout / style / prompt) | images.py 跑前 / 重做某张图前 |

## 触发链路(典型一篇文章)

```
1. 选题:auto_pick.py 出候选 → topic-curator 判 6 大主题命中 / reject
2. 钩子:写文前 → hook-writer 出 5 候选 → 选 1
3. 写文:write.py 跑 claude -p · prompt 已含「6 大主题 + 头部 KOL 对标」
4. 配图:images.py 跑前 → visual-art-director 决定 layout + prompt
5. 自审:auto_review.py 跑机械维度 → review-critic 跑 LLM 7 维度
6. 改稿:不达标 → revise-editor 外科手术(只改命中维度的段)
7. 发布:publish.py 推草稿
```

## 如何 spawn

主线程通过 `Agent` 工具 spawn:

```
Agent(
  description="判选题",
  subagent_type="topic-curator",
  prompt="topic_title='Cursor 估值 100 亿背后' · topic_summary='...' · weekday=4"
)
```

或在跟用户对话时,我(Claude 主线程)自动判断要不要 delegate。

## 跟 personas/ 的区别

- `personas/*.yaml`:**写作风格人设**(midnight-friend / shortform-writer / tutorial-instructor 等)·
  给 `claude -p writing` 子进程当语言风格 · 不是 Claude Code sub-agent
- `.claude/agents/*.md`:**Claude Code sub-agent**(本目录)· 主线程协作时 spawn ·
  做某个具体决策(选题判定 / 钩子候选 / 自审)

两者并行 · 不冲突。

## KOL pattern 数据流

`kol-pattern-analyst`(深度) + `scripts/analyze_kol.py`(浅度自动)互补:
- `analyze_kol.py`:每天 03:30 跑 · 浅度抽 metadata 4 层 → `output/kol_patterns.yaml`
- `kol-pattern-analyst`:用户/我手动 spawn · 对 1 篇 KOL 文做深度拆解(为啥这种写法有效)·
  产出更适合学的「招式拆」

`hook-writer` 读 patterns.yaml 拿头部 5 钩子做形式参考 · `topic-curator` 也读 6 大主题 + 当天 weekday。

## 维护

- 改 6 大主题 → 同步改 `topic-curator.md` + `review-critic.md` + `CLAUDE.md` 主题段 + `_TOPIC_SCOPE_RULES`(write.py)
- 加新 agent → 这里加一行 + 写到 `.claude/agents/<name>.md` · frontmatter 必须含 name/description/tools
