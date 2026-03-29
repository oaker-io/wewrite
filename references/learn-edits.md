# 学习人工修改（核心飞轮）

这是 WeWrite 最重要的长期价值。每次用户编辑文章后让系统学习，下一次的初稿就会更接近用户的风格，需要的编辑量越来越少。

**飞轮效应**：初稿需要改 30% → 学习 5 次后只需改 15% → 学习 20 次后只需改 5%

**触发**：用户说"我改了，学习一下"、"学习我的修改"

## 1. 获取 draft 和 final

- **draft**：`output/` 下最新的 .md 文件（按修改时间排序，`ls -t output/*.md | head -1`）
- **final**：用户提供修改后的版本。主动引导用户："请把你改好的文章全文粘贴给我，或者告诉我文件路径。如果你是在微信后台编辑器里改的，可以全选复制后直接粘贴到这里。"

## 2. 运行 diff 分析

```bash
python3 {skill_dir}/scripts/learn_edits.py --draft {draft_path} --final {final_path}
```

## 3. 分析并记录

读取脚本输出的 diff 数据，对每个有意义的修改分类：

- **用词替换**：AI 用了"讲真"，人工改成"坦白说"
- **段落删除**：人工觉得某段多余
- **段落新增**：人工补充了 AI 没写的内容
- **结构调整**：H2 顺序或分段方式的变化
- **标题修改**：标题风格偏好
- **语气调整**：整体语气的偏移方向

将分类结果写入 `lessons/` 下的 diff YAML 文件的 edits 和 patterns 字段。

## 4. 自动触发 Playbook 更新

每积累 5 次 lessons，自动触发 playbook 更新：

```bash
python3 {skill_dir}/scripts/learn_edits.py --summarize
```

脚本输出所有 lessons 的汇总数据。**Agent 必须执行以下步骤完成闭环**：

1. 读取 summarize 输出，找出反复出现的 pattern（≥2 次）
2. 读取当前 `{skill_dir}/playbook.md`（如果不存在则从零创建）
3. **将 pattern 转化为可执行的写作规则**写入 playbook.md：
   - 不要写"用户偏好简短段落"（描述性，不可执行）
   - 要写"段落不超过 80 字，长段必须在 3 句内换行"（指令性，可执行）
   - 每条规则必须是写作时能直接遵循的具体指令
4. 保存 playbook.md

**验证闭环**：playbook.md 更新后，下次写作时"Playbook 优先"规则会自动加载新 pattern，初稿会反映用户偏好。
