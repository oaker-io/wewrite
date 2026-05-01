# WeWrite 发布计划 · 每日时间表 + 内容设计 + 评论运营

> 本文档是「全自动发文 + 涨粉」体系的完整操作手册。
> 7 天轮播 · 每天 1 主推 + 1-2 副推 · 占 1 次群发配额 · 月产能 ≥ 60 篇。
> 改 schedule 编辑 `config/auto-schedule.yaml` · 立即生效。

---

## 一天的时间表(全自动)

```
07:00  auto-pick.sh        选今日 1 主 + 1-2 副 idea (从 idea_bank · 按 weekday/category)
                           · 推 Discord 「今天准备发: <主推标题> + N 副」
08:00  auto-write.sh       claude -p 写主推 (5-15 分钟)
                           · 主推完后 · 跑 N 次 write.py --style shortform 写副推
                           · 推 Discord 「主推 + 副推 全部写完 · 字数 X / Y / Z」
10:00  auto-images.sh      生主推 6 张图(cover + cover-square + chart×4)
                           · 副推每篇生 cover-square (周三案例额外加数字大字风)
                           · 推 Discord「图片就绪」
11:00  auto-review.sh      LLM 自审 5+1 维度 (钩子/字数/图数/口头禅/禁忌词 + 案例真实感)
                           · 不达标 push 警报 · 但不阻断 publish
12:00  auto-publish.sh     cli.py publish-bundle 一次推 1+N 篇 · 占 1 次群发配额
                           · 推 Discord 「草稿就绪 · media_id=...」
                           · 评论默认开 · 允许非粉丝评论
19:30  auto-notify.sh      推 Discord 「请到 mp.weixin.qq.com 点群发」
                           · 用户 1 tap 点群发(订阅号每日 1 次配额耗尽)
20:00  auto-comment-kickoff.sh  推 Discord 候选置顶话术 (2 个模板 + 自动回复速查)
                           · 用户复制粘贴 → 评论区发 + 长按置顶
22:00  (可选 · 用户睡前)    扫一遍未回评论 · 每条 1-2 句回(参考 references/comment-playbook.md)
周日 02:00  auto-stats.sh   回填本周 fan_count/read_count/评论数/转发数 → output/history.yaml
```

**用户每天只需做的事**:
1. 19:30-20:30 之间 1 tap 「群发」(30 秒)
2. 20:00 后复制置顶话术 → 评论区粘贴 + 长按置顶(1 分钟)
3. 当天和次日扫评论 · 每条回 1-2 句(累计 5-10 分钟)

**总计每天人工**:7-12 分钟。

---

## 7 天内容设计

### 周一 · AI 使用手册(产品向)

**主推**(2500-4000 字 · style=tutorial · image_style=mockup):
- 例:「Claude Code 完整 SOP · 从 0 到 1 配置」「Cursor 9 个隐藏快捷键」
- 配图:macOS / iOS / 浏览器拟真截图(mockup-* 套件)
- 标签:`#AI 非共识 #AI 工具 #保姆级教程 #<具体工具>`

**副推 1**(800-1200 字 · style=shortform · S1 即时观点):
- 例:「Cursor 这事还有个细节没说」「Claude Code 我没用 X 的真实理由」
- 标签:`#AI 非共识 #<具体工具> #观察`

### 周二 · 干货教程(框架向)

**主推**(2500-4500 字 · style=tutorial · image_style=infographic):
- 例:「30 天写完 SaaS 的完整 SOP」「AI Agent 系统架构 9 步」
- 配图:dashboard / linear-progression / hierarchical-layers 信息图
- 标签:`#AI 非共识 #AI Coding #干货合集 #<具体工具>`

**副推 1**(600-1000 字 · style=shortform · S2 数据快讯):
- 例:「Claude 4.7 发布 · 关键 3 个数字」「Cursor 2.0 偷偷改了 5 个东西」
- 标签:`#AI 非共识 #数据`

### 周三 ★ AI 真实成功案例(故事向)

**主推**(2200-3800 字 · style=case · image_style=case-realistic):
- 例:「30 天 Cursor 复盘 · 完整账单 $12,847」「读者跟我反馈 · 7 天搞定 SaaS」
- 配图:**case-realistic 拟真套件**(Stripe 通知 / GitHub stars / Tweet 截图 + 1:1 大数字 thumb)
- 标签:`#AI 非共识 #案例复盘 #真实跑通 #<具体工具>`

**副推 1**(800-1000 字 · style=shortform · S3 30 秒复盘):
- 例:「30 天 Cursor 复盘 · 30 秒 5 个结论」(主推 TL;DR · 一长一短互文)
- 标签:`#AI 非共识 #<具体工具> #金句`

**★ 周三是涨粉曲线最关键的一天 · 配图逼真度直接决定信任度**

### 周四 · AI 工具评测(对比向)

**主推**(2500-4000 字 · style=tutorial · image_style=mockup):
- 例:「Cursor vs Windsurf · 7 天压测结论」「6 个 Claude Code 替代品 实测」
- 配图:左右对比 mockup / comparison-matrix 横评
- 标签:`#AI 非共识 #工具横评 #<工具 A> #<工具 B>`

**副推 1**(800-1200 字 · style=shortform · S7 失败踩坑):
- 例:「我以为 X · 结果踩了 Y · 30 分钟救回来」
- 标签:`#AI 非共识 #踩坑实录 #<具体工具>`

### 周五 · 深度解读热点(观点向)

**主推**(1800-2800 字 · style=hotspot · image_style=infographic):
- 例:「Claude 4.7 发布:被忽略的 3 个非共识信号」「Cursor 估值这事真相」
- 配图:infographic-dense 高密度数据图
- 标签:`#AI 非共识 #观察`

**副推 1**(600-1000 字 · style=shortform · S2 数据快讯):
- 例:「<厂家> 刚发布 · 关键 N 个数字」(跟主推热点联动)
- 标签:`#AI 非共识 #<厂家> #数据`

### 周六 · 轻量分享(2 副推 · 主推短)

**主推**(1500-2500 字 · style=tutorial · image_style=simple):
- 例:「本周收集的 5 个 AI 工具 · 我都试了」「我读完的 3 篇 AI 论文」
- 标签:`#AI 非共识 #干货合集`

**副推 1**(200-400 字 · style=shortform · S6 金句卡):
- 例:1 张 1:1 大字图 + 100-300 字解读
- 标签:`#AI 非共识 #金句`

**副推 2**(700-1000 字 · style=shortform · S4 读者问答):
- 例:「读者问:X · 我答」(从本周评论挑 1 条)
- 标签:`#AI 非共识 #读者群 #<话题>`

### 周日 · 本周精华合集(汇总向)

**主推**(2000-3000 字 · style=hotspot · image_style=simple):
- 例:「本周 7 篇精华 · 智辰 5 个判断」(对本周内容 + 观察的回顾)
- 标签:`#AI 非共识 #干货合集 #本周回顾`

**副推 1**(1000-1500 字 · style=shortform · S5 资源清单):
- 例:「本周收集的 N 个 AI 工具 + 1 个踩雷」
- 标签:`#AI 非共识 #AI 工具 #本周收藏`

---

## 副推群发的关键认知

**订阅号每日 1 次群发 = 1 主图文 + 0-7 副图文 = 1-8 篇**

这意味着:
- 一次群发占 1 次配额 · 但能推 1-8 篇内容
- 我们设计:每天 1 主 + 1-2 副 = 2-3 篇 / 群发
- 用户在订阅号首页一打开 · 看到一组 stack(主 + 副 缩略)
- thumb_media_id 用 1:1 cover-square 显示 80×80 缩略 · 大字清晰

**月产能预估**:
```
周一-周五:每日 2 篇 = 10 篇
周六:    3 篇
周日:    2 篇
总计:    15 篇 / 周 = 60-70 篇 / 月
```

跟改造前 (1 篇 / 天 = 30 篇 / 月) 相比 · **触达 +120%**。

---

## 评论区运营时间节点(完整)

```
T+0       19:30 用户 tap 群发 · 推送出去
T+5min    auto-comment-kickoff.sh push Discord(候选置顶话术 + 自动回复速查)
T+10min   用户复制话术 → mp.weixin.qq.com 评论区 → 发评论 → 长按置顶
T+30min   第一波评论涌入 · 用户开始回(每条 1-2 句)
T+4h      评论稳定 · 睡前再扫一遍
T+24h     必须回完所有未回评论(参考 references/comment-playbook.md 速查表)
周日 整理本周评论 · 挑 3 条做 S4 读者问答素材
```

**为什么这套节奏**:WeChat 算法 CES 评分(关注 8 分 > 评论 4 分 = 转发 4 分 > 收藏 1 分 = 点赞 1 分)· 评论 + 关注是最值钱的。
**作者本人沙发置顶 + 24h 内回完** = CES 飙升 · feed 算法判定「优质账号」 · 拉曝光池。

---

## 启动 / 暂停命令速查

### 一键安装全部 launchd
```bash
./routine/install-auto.sh
```

### 看哪些任务已装
```bash
./routine/install-auto.sh --list
```

### 临时停某一步(eg 不想自动 publish · 想手审 publish)
```bash
# 编辑 config/auto-schedule.yaml#steps · 把 publish 改成 false · 重新 reload 不用
```

### 全停一天(eg 出差不发)
```bash
# 编辑 config/auto-schedule.yaml#enabled · 改成 false
```

### 全卸 launchd
```bash
./routine/install-auto.sh --uninstall
```

### 临时只跑某一步
```bash
./scripts/auto/auto-pick.sh        # 立即选题
./scripts/auto/auto-write.sh       # 立即写
./scripts/auto/auto-images.sh      # 立即配图
./scripts/auto/auto-review.sh      # 立即自审
./scripts/auto/auto-publish.sh     # 立即推草稿
./scripts/auto/auto-notify.sh      # 立即推群发提醒
```

### 立即推置顶话术(测试 / 手动触发)
```bash
venv/bin/python3 scripts/workflow/comment_kickoff.py
```

---

## 特殊场景 SOP

### 场景 1 · 周三案例文(★ 涨粉关键)

加配图人眼检查:
```bash
# 跑完 auto-images 后 · 看 5 张图是否「不像 AI 画的」
open output/images/cover.png         # 真实产品 UI 截图风
open output/images/cover-square.png  # 1:1 数字大字风
open output/images/chart-1.png       # Stripe-like dashboard
open output/images/chart-2.png       # before/after split
open output/images/chart-3.png       # terminal/IDE 真截图
open output/images/chart-4.png       # 真实结果证明
```

不像真实 → 改 `references/visuals/styles/case-realistic.md` prompt 关键词。

### 场景 2 · 临时插入手动选题(eg 突发热点)

```bash
# 跳过 auto-pick · 直接 write
venv/bin/python3 scripts/workflow/write.py --idea "突发热点主题" --style hotspot

# 或 Discord 发:「写 突发热点主题」
```

### 场景 3 · 副推 idea 库不够 · 想补

```bash
# 命令行
venv/bin/python3 scripts/workflow/idea.py add "下篇副推主题" --category tutorial

# 或 Discord 发:「存 idea: 主题 教程」
```

### 场景 4 · 周日合集主推

合集主推可以**复用本周已发文章** · 不用重新写:
```bash
# 用 brief.py 选 6 个本周已用 idea · 让 claude 写合集
# (后续可加 auto-weekly-recap.py 自动化 · 当前手动)
```

### 场景 5 · 想做贴图笔记 (公众号「贴图」+ 小红书互通)

```bash
# 单独跑 picpost · 不影响主流程
venv/bin/python3 scripts/workflow/picpost.py "30 天 Cursor 复盘 · 7 张图" --framework P1

# 看输出
open output/picpost/<date>-<slug>/

# 手动到公众号「贴图」+ 小红书 app 上传(API 没开 · 暂手动)
```

---

## 成功指标(每周日 stats 回填后看)

| 指标 | 月 1 目标 | 月 3 目标 | 半年目标 |
|---|---|---|---|
| 总粉丝数 | 500 | 3000 | 10000 |
| 单篇平均阅读 | 200 | 400 | 800 |
| 单次群发触达 | 主+副平均 300 阅读 | 平均 600 | 平均 1500 |
| 单篇评论数 | ≥ 5 | ≥ 12 | ≥ 25 |
| 作者回复率 | 100% | 100% | ≥ 80%(粉多了顾不过来) |
| 评论 → 私域转化 | ≥ 1/篇 | ≥ 3/篇 | ≥ 8/篇 |
| 转发:阅读比 | 0.3% | 1% | 3% |
| 副推阅读 / 主推阅读 | 30% | 40% | 50% |

---

## 不做什么

- ❌ 不实现 masssend 群发 API(用户每晚 1 tap · 比 API 安全)
- ❌ 不一天发超 8 篇(订阅号配额上限就是 8)
- ❌ 不评论刷数(WeChat 检测 · 降权)
- ❌ 不删差评(显得真实)
- ❌ 不在评论区发长文(评论一句话即可)
- ❌ 不蹭无关热点标签
- ❌ 不在 author-card 之后再放任何内容(WeChat 末尾视觉收尾)

## 改了 config 不需要重启 launchd

`config/auto-schedule.yaml` 是每次 step 跑时**实时读取** · 改完保存即下次生效。
launchd plist 只控制时间触发 · 不缓存 yaml 内容。
