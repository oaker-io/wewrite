# KOL 准入 5 条标准(2026-04-26 锁)

> 招新 KOL 进 `config/kol_list.yaml#status=active` 必须 5 条全过 · 任意 1 条不过 → status=archived 或不收。

## 5 条硬标准

### 1. 主题在 7 大主题范围
- AI 干货 / AI 教程 / AI 赚钱 / AI 创业 / AI 真实测评 / AI 踩坑 / AI 感悟
- **必拒**:AI 新闻资讯 / AI 行业咨询 / 写作鸡汤 / 普通副业 / 养生情感

### 2. 历史 10 篇文章 ≥ 7 篇能过 `_topic_guard.is_ai_topic`
- 拉 RSS 最新 10 篇 · 用 `scripts/workflow/_topic_guard.py` 跑 `is_ai_topic`
- 通过率 < 70% → 这位博主**主旋律不是 AI** · 不收
- 例:粥左罗 0/10 通过 → archived

### 3. tags 必须含 AI / AIGC / 大模型 / Agent / AI 评测 至少 1 个
- 写错就改:tags 是给 `_kol_category` 映射用的
- 反例:tags=[商业, 案例, 框架] → 拒 · 这是商业 KOL
- 正例:tags=[AI 工具, 实战, 副业] → 收

### 4. 有可订阅的 wewe-rss feed
- 必须能在 wewe-rss web UI 添加成功 · 拿到 `MP_WXS_xxx` biz_name
- 抓不到的(秦刚 / 白无常C4D 等抓挂的)留 status=archived 直到 feed 修好
- 不能依赖手动复制 url 的方式

### 5. 是头部博主(weight ≥ 70)
- 看看 last 5 文章平均阅读量(走 wewe-rss 拿不到 · 用 mp.weixin.qq.com 看一眼)
- 阅读量 < 5000 / 文章 → weight = 50 · 不进选题主链(只做钩子学习材料)
- 阅读量 ≥ 1w / 文章 → weight = 80(对标级)

## 7 大主题 × 推荐对标 KOL 类型

| 主题 | 找什么类型博主 | 关键词搜 |
|---|---|---|
| AI 干货 | 工具实战 / SOP / 框架 | AI 工作流 / AI 实战 / Claude Code / Cursor 实战 |
| AI 教程 | step-by-step 教学 | 5 分钟教你 / GPT 教程 / Claude 上手 |
| AI 赚钱 | 副业变现 / 月入 X | AI 副业 / AI 月入 / AIGC 接单 / 自媒体 + AI |
| AI 创业 | 0→1 / SaaS / Indie | AI 创业 / Indie Hacker / Day 0 |
| AI 真实测评 | 工具横评 | XX vs YY / 实测 30 天 / Cursor 评测 |
| AI 踩坑 | 翻车 / 坑 / 教训 | 踩坑 / 翻车 / 教训复盘 |
| AI 感悟 | 工程师 take / 反共识 | 反共识 / 冷观察 / 长期视角 |

## 操作流程(招新 KOL · 用户视角)

1. **每天看 daily-report**(22:00 自动推 Discord)· 「KOL 候选」段会推 5 个 AI 博主候选
2. **用户决定**:这 5 个里有想收的 → 复制名字 + url → wewe-rss web UI 订阅
3. **订阅成功后**:运行 `setup_kol_feeds.py` 把 wewe-rss 的 feed 反向回填到 `kol_list.yaml`
4. **设 tags**:必须含 AI / AIGC / 大模型 / Agent / AI 评测 至少 1 个
5. **跑次 fetch_kol** 验证抓得到 + 文章过 is_ai_topic ≥ 70% · 才正式进 active
6. **目标**:100 个 active AI KOL · 当前 5 个 · 缺口 95

## archived KOL 的用法

不能进选题流 · 但可以**当钩子学习材料**:
- 粥左罗的「你有没有过这样的时刻?」「身处人情往来,总逃不开两种选择」 — **形式好**(钩子模板)· **内容不能用**(写作鸡汤)
- 处理:`scripts/analyze_kol.py` 提取钩子模板入 `output/kol_patterns.yaml#hook_templates` · 然后**借形不借神**改成 AI 主题

## archived 复活流程

如果某 KOL 改方向开始写 AI(比如刘润开了「AI 商业」专栏):
1. 重新跑该 KOL 最近 10 篇过 `is_ai_topic`
2. 通过率 ≥ 70% → status=active 复活
3. 通过率 30%-70% → 留 archived · 但单篇 if pass 也可以入 corpus
4. 通过率 < 30% → 继续 archived
