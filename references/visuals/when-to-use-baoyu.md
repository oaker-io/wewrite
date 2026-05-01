# 什么时候调用 baoyu-infographic vs WeWrite 自产

WeWrite 本身(SKILL.md Step 6 + `infographic-dense` 模板)已经能产"高密度信息图"的中文提示词。外部 `/baoyu-infographic` skill 是**加强版工具**,不是替代品。两者定位不同,按场景选择。

## 一张表说清楚

| 维度 | WeWrite 自产 `infographic-dense` | 调用 `/baoyu-infographic` |
|------|----------------------------------|---------------------------|
| **什么时候产** | 写文章的 Step 6,批量一次出完 | 独立一张图,单独精打 |
| **输出** | 提示词文件(prompts.md),用户自己贴到 ChatGPT/Gemini | 内置调用 baoyu-image-gen,直接出图 |
| **优化深度** | LLM 顺手合成,信息密度够用 | analysis-framework 内容分析 + 智能 layout×style 推荐 + 多轮打磨 |
| **耗时** | 秒级(LLM 同步) | 几十秒到几分钟(多轮处理) |
| **视觉连贯性** | 4-6 张同文章视觉协调(同色板、同风格) | 单张独立优化,兄弟图之间不保证一致 |
| **用户干预** | 零(自动跑完 8 步管道) | 手动触发,每张图单独命令 |
| **适用输出** | 公众号正文配图(16:9) | 小红书分 P(3:4)、独立干货大图 |

## 判定流程图

```
用户要生成图
    │
    ├─ 正在跑 WeWrite 8 步管道? ──── 是 ──→ WeWrite 自产(默认)
    │                                        │
    │                                        └─ 除非用户中途说"这张图特别重要给我做精"
    │                                            → 跳到 baoyu 分支
    │
    └─ 单独一张/单篇小红书/精打图? ──→ baoyu
                                          │
                                          └─ 关键词触发:
                                             - "小红书风格"
                                             - "独立干货图"
                                             - "单图打磨"
                                             - "高密度信息大图"
```

## 触发 baoyu 的 4 种具体场景

### 场景 1:小红书 3:4 分 P 图文

用户说"帮我写一篇小红书笔记"或给了 3:4 竖版需求 → 立刻用 baoyu,**不走 WeWrite**。

参考:`/Users/mahaochen/.openclaw/workspace/xhs-images/cat-care-guide/` 就是这个工作流产物,6 张分 P 图风格统一、信息丰富,正是 baoyu 的擅长项。

```bash
/baoyu-infographic path/to/content.md --aspect 3:4 --lang zh
```

### 场景 2:公众号里的"封面级"重要图

WeWrite 生成完 4-6 张内文配图后,用户挑其中 1 张说"这张我要做成海报级,单独精打" → 把该图的模块结构喂给 baoyu 二次加工:

```bash
# 把 chart-3 的 Section 结构抽出来存到临时文件
cat > /tmp/chart-3-modules.md <<EOF
# 企业采购 AI 数据
## Section 1: 首次采购胜率
- Anthropic 70% · OpenAI 30%(Ramp)
...
EOF

# 让 baoyu 精打
/baoyu-infographic /tmp/chart-3-modules.md --layout dense-modules --style pop-laboratory --aspect 16:9 --lang zh
```

### 场景 3:信息量超过 6-7 模块

比如你要做"2026 AI 编程工具全景图"——20+ 工具分类归置 → 超过 WeWrite `dense-modules` 的 6-7 模块上限 → 上 baoyu 的 `periodic-table` 或 `bento-grid`:

```bash
/baoyu-infographic ai-coding-landscape.md --layout periodic-table --style morandi-journal --aspect 16:9 --lang zh
```

### 场景 4:用户关键词主动触发

这些词出现时,**默认跳到 baoyu**:

- "小红书风格"、"小红书图"、"3:4 竖版"
- "高密度信息大图"、"high-density-info"(baoyu 原生触发词)
- "单独一张"、"单独打磨"、"给我做精"、"这张我要海报级"
- "用宝玉老师那套"、"baoyu"

## 什么时候**不要**用 baoyu

明确反例:

- ❌ 批量跑公众号文章(一周 5 篇,每篇 4-6 张图)——太慢,用 WeWrite 自产
- ❌ 图只是装饰性过渡段(`decorative` 模式),不需要高密度 → 用 WeWrite 的旧 6 种模板(scene/flowchart 等)
- ❌ 用户催"赶紧发"——baoyu 多轮处理会拖时间
- ❌ 封面图(2.35:1)——baoyu 默认优化 3:4 和 16:9,封面比例走 WeWrite 自产更稳

## 互操作原则

**WeWrite 和 baoyu 共享同一批 layout × style 资源**(WeWrite 的 `references/visuals/` 就是从 baoyu vendor 的)。所以:

- WeWrite 里决定的 Layout 名(如 `dense-modules`)在 baoyu 里可以直接用
- Style 名(如 `pop-laboratory`)也一样
- 模块结构(Section 1-7 的 Key Concept / Content / Visual / Text Labels)格式兼容

用户可以:
1. 先用 WeWrite 跑完,看 prompts.md
2. 挑不满意的某张,把其 Section 结构抽出来
3. 直接喂给 baoyu 二次加工,拿到更精的提示词或直接出的图

## 一句话总结

- **日常批产公众号配图 → WeWrite**
- **单图精打 / 小红书分 P / 超大信息量 → baoyu**
- **两者共享同一套 layout × style 词汇,无缝互通**
