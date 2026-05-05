# 学习人工修改（核心飞轮）

这是 WeWrite 最重要的长期价值。每次用户编辑文章后让系统学习，下一次的初稿就会更接近用户的风格，需要的编辑量越来越少。

**飞轮效应**：初稿需要改 30% → 学习 5 次后只需改 15% → 学习 20 次后只需改 5%

**触发**：用户说"我改了，学习一下"、"学习我的修改"

## 1. 获取 draft 和 final

- **draft**：`output/` 下最新的 .md 文件（按修改时间排序，用 `ls -t output/*.md | head -1`）
- **final**：用户提供修改后的版本。主动引导用户："请把你改好的文章全文粘贴给我，或者告诉我文件路径。如果你是在微信后台编辑器里改的，可以全选复制后直接粘贴到这里。"

## 2. 运行 diff 分析

```bash
python {skill_dir}/scripts/learn_edits.py --draft {draft_path} --final {final_path}
```

## 3. 分析并记录 pattern

读取脚本输出的 diff 数据和 INSTRUCTIONS FOR AGENT，对每个有意义的修改写入 pattern。

**每个 pattern 必须包含**：
- `type`：`word_sub` / `para_delete` / `para_add` / `structure` / `title` / `tone` / `expression`
- `key`：短唯一标识（英文，如 `avoid_jiangzhen`、`shorter_paragraphs`、`more_negative_emotion`）
- `description`：这次修改是什么（如"把'讲真'替换为'坦白说'"）
- `rule`：可执行的写作指令（**必须是祈使句，不是描述句**）

**key 的复用**：如果这次的修改和之前某个 lesson 里的 pattern 是同一种偏好（比如又一次把段落改短了），使用**相同的 key**。这样 `--summarize` 时 occurrences 会累加，confidence 自动提升。

编辑 lesson YAML 文件中的 `patterns` 列表，写入分析结果。

## 4. Playbook 更新

每积累 5 次 lessons，触发 playbook 更新：

```bash
python3 {skill_dir}/scripts/learn_edits.py --summarize --json
```

读取 JSON 输出，按以下规则更新 `{skill_dir}/playbook.md`：

### playbook.md 格式

playbook.md 是 YAML 格式，每条规则带 confidence 和元数据：

```yaml
# WeWrite Playbook — 从用户编辑中学习的写作规则
# 由 Agent 自动维护，不要手动编辑
# confidence ≥ 5 的规则在 Step 4 写作时作为硬性约束执行
# confidence < 5 的规则作为软性参考

rules:
  - key: "shorter_paragraphs"
    type: "expression"
    rule: "段落不超过 80 字，长段必须在 3 句内换行"
    confidence: 7.0
    occurrences: 4
    last_seen: "2026-03-28"

  - key: "avoid_jiangzhen"
    type: "word_sub"
    rule: "不要使用'讲真'，用'坦白说'代替"
    confidence: 5.0
    occurrences: 2
    last_seen: "2026-03-30"
```

### 更新规则

1. **新增**：summarize 中出现了 playbook 里没有的 key → 直接添加
2. **更新**：summarize 中的 confidence/occurrences/rule 比 playbook 里的新 → 用新值覆盖
3. **保留**：playbook 中有但 summarize 中没有的规则 → 保留不动（可能是早期学到的，仍然有效）
4. **衰减淘汰**：confidence < 2 的规则 → 删除（太旧或不再相关）

## 5. Step 4 如何使用 playbook

Step 4 写作时读取 playbook.md：

- **confidence ≥ 5 的规则**：作为硬性约束执行（和 persona 同级）
- **confidence 3-5 的规则**：作为软性参考（倾向遵循但不强制）
- **confidence < 3 的规则**：忽略（可能已过时）

这确保：
- 用户反复确认的偏好（高 confidence）被严格执行
- 只出现过一次的偏好（低 confidence）不会过度影响
- 用户风格变化时，旧规则自然衰减退出
