#!/usr/bin/env python3
"""Workflow 2 · 写作 write
读 session 的 selected_idx · 调 claude -p 跑 Step 3-5(框架+素材+写作)。
输出到 output/YYYY-MM-DD-slug.md · push 全文到手机等用户审。

用法:
  python3 scripts/workflow/write.py 0           # 选 session Top N 里的第 1 条
  python3 scripts/workflow/write.py --idea "Cursor 2.0 冲击 Claude Code"  # 自定义 idea · 绕开 brief
"""
from __future__ import annotations
import os, re, subprocess, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state
import _idea_bank

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def slugify(title, maxlen=40):
    """从中文标题提取关键词 slug(简单版 · 保留字母数字 + 连字符)"""
    # Extract English/numbers from title
    eng = re.findall(r"[A-Za-z0-9]+", title)
    if eng:
        s = "-".join(eng[:5]).lower()
    else:
        # Fallback: hash prefix + timestamp
        import hashlib
        s = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
    return s[:maxlen]


_IDENTITY_DIR = ROOT / "identity"
_IDENTITY_SECTIONS_TO_INJECT = (
    "0. 基础身份",
    "1. 一句话定位",
    "2. 三句话定位",
    "3. bio 候选",
    "4. IP 故事",
)


def _extract_identity_sections(md_text: str) -> str:
    """从 identity.md 抽几个关键 ## section · 拼成 prompt 注入段。"""
    if not md_text:
        return ""
    lines = md_text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            # 是不是要保留的 section?
            if any(heading.startswith(s) for s in _IDENTITY_SECTIONS_TO_INJECT):
                current = [line]
                blocks.append(current)
            else:
                current = None
            continue
        if current is not None:
            current.append(line)
    out = "\n".join("\n".join(b).rstrip() for b in blocks)
    return out.strip()


def _load_identity_block() -> str:
    """组装 identity 注入段:精选 sections + voice/catchphrases + voice/forbidden。

    若 identity/ 目录或文件不存在,返回空字符串(向后兼容)。
    """
    if not _IDENTITY_DIR.is_dir():
        return ""

    parts: list[str] = []

    identity_md = _IDENTITY_DIR / "identity.md"
    if identity_md.exists():
        sections = _extract_identity_sections(identity_md.read_text(encoding="utf-8"))
        if sections:
            parts.append("### 你的身份与定位(写作时自然带出 · 不要直接复述)\n\n" + sections)

    catchphrases = _IDENTITY_DIR / "voice" / "catchphrases.md"
    if catchphrases.exists():
        parts.append("### 你的口头禅 / 招牌句式(可自然使用)\n\n" + catchphrases.read_text(encoding="utf-8").strip())

    forbidden = _IDENTITY_DIR / "voice" / "forbidden.md"
    if forbidden.exists():
        parts.append("### 禁忌词与雷区(命中即重写)\n\n" + forbidden.read_text(encoding="utf-8").strip())

    if not parts:
        return ""

    return (
        "\n\n"
        "**作者人设档案(写作时严格遵守 · 自然代入 · 不要直接引用)**\n\n"
        + "\n\n---\n\n".join(parts)
        + "\n"
    )


_KOL_PATTERNS_FILE = ROOT / "output" / "kol_patterns.yaml"


def _load_kol_patterns_block(*, top_n_hooks: int = 5) -> str:
    """读 output/kol_patterns.yaml(P2 产出)· 拼成「今日头部对标」prompt 段。

    Why: P3 · 让自动写文时参考头部 KOL 近 7 天的钩子模式 + 结构基线 + 风格签名 ·
    不要照抄 · 只对标。文件不存在(没跑过 fetch_kol)就静默返回空字串 · 不阻断老链路。
    """
    if not _KOL_PATTERNS_FILE.exists():
        return ""
    try:
        import yaml as _yaml
        data = _yaml.safe_load(_KOL_PATTERNS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""

    if not data.get("total_articles"):
        return ""

    hooks = (data.get("top_hooks") or [])[:top_n_hooks]
    sn = data.get("structural_norms") or {}
    ss = data.get("style_signature") or {}

    lines: list[str] = ["**=== 今日 KOL 头部对标(参考 · 不照抄)===**\n"]
    if hooks:
        lines.append(f"**Top {len(hooks)} 钩子模板**(近 {data.get('window_days', 7)} 天):")
        for h in hooks:
            kol = h.get("kol", "?")
            title = (h.get("title") or "")[:35]
            hook = (h.get("hook") or "")[:60]
            lines.append(f"  - [{kol}] {title}")
            lines.append(f"    钩子:{hook}")
        lines.append("")
    if sn:
        lines.append(
            f"**结构基线**(中位 · 你写的可以略有差异):"
            f"H2={sn.get('median_h2_count', 0)} 个 · "
            f"段={sn.get('median_paragraph_count', 0)} 个 · "
            f"段长 ≈ {sn.get('median_avg_para_chars', 0)} 字 · "
            f"图 {sn.get('median_image_count', 0)} 张 · "
            f"全文 ≈ {sn.get('median_total_chars', 0)} 字"
        )
    if ss and ss.get("top_emojis"):
        emojis = "".join(ss["top_emojis"][:5])
        lines.append(
            f"**风格签名**:常见 emoji {emojis} · "
            f"!! 密度 {ss.get('median_exclaim_per_100', 0)}/100字 · "
            f"数字 {ss.get('median_number_per_100', 0)}/100字 · "
            f"加粗 {ss.get('median_bold_per_100', 0)}/100字"
        )
    lines.append("\n**用法**:你的钩子可以借鉴上面的形式 · 但话题/数据/观点必须自己挖 · 不要照抄。")
    return "\n" + "\n".join(lines) + "\n"


def _load_news_hub_reactions_block(topic: dict) -> str:
    """When topic.from == news_hub, fetch matching KOL reactions + real-eval cards.

    Returns a markdown block to inject into the writer prompt as concrete
    evidence. Silent no-op for non-news_hub topics or any failure.
    """
    if not topic or topic.get("from") != "news_hub":
        return ""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from news_hub_reader import read_release_reactions, read_reviews  # type: ignore
    except Exception:
        return ""

    url = (topic.get("url") or "").rstrip("/")
    slug_raw = url.split("/")[-1].lower() if url else ""
    slug = re.sub(r"[^a-z0-9]+", "_", slug_raw)[:60]

    rxns = []
    revs = []
    try:
        if slug:
            rxns = read_release_reactions(slug=slug)
            revs = read_reviews(model_slug=slug)
    except Exception:
        pass

    out: list[str] = []
    summary = (topic.get("summary") or "").strip()
    if summary:
        out.append(f"**=== news_hub 发布摘要 ===**\n{summary[:600]}\n")
    if rxns:
        out.append("**=== 5 个 KOL 怎么说(news_hub release_reactions)===**")
        for r in (rxns[0].get("kol_reactions") or [])[:5]:
            author = r.get("author", "?")
            text = (r.get("text") or "").replace("\n", " ").strip()[:240]
            out.append(f"- @{author}:{text}")
        out.append("")
    if revs:
        out.append("**=== 5 个维度真测(news_hub reviews · 可在正文引用 eval 结论)===**")
        for c in (revs[0].get("cards") or [])[:5]:
            cat = c.get("category", "?")
            eid = c.get("eval_id", "?")
            out.append(f"- {cat}:{eid}")
        out.append("")
    if not out:
        return ""
    out.insert(0, "\n**用法**:本主题来自 ai-news-hub · 下方是真实 KOL/eval 素材 · "
                  "正文必须基于这些事实 · 不要编造数据,可在文中引用 KOL 原话作佐证。\n")
    return "\n" + "\n".join(out) + "\n"


_TOPIC_SCOPE_RULES = (
    "**🎯 主题必须命中以下 6 大范围之一(WeWrite 核心宗旨 · 越界即重写)**:\n"
    "1. **AI 搞钱** — 副业 / 变现 / 月入 / 路径 / ROI / 红利窗口\n"
    "2. **AI 实战** — 跑通流程 / 上手操作 / 工程化落地 / 「明天能用」\n"
    "3. **AI 真实案例** — Day 0/Day N 时间线 + 具体数字 + 失败/坑\n"
    "4. **AI 心得** — 反共识 / 冷观察 / 工程派判断 · 不堆 hype\n"
    "5. **AI 最新测试** — 工具评测 / 横向对比 / 实测数据\n"
    "6. **AI 咨询** — 行业判断 / 投资视角 / 趋势分析\n"
    "**违规清单**:政治 / 股票币圈 / 同行八卦 / 个人感情 / 翻译式无价值复述 / 空洞 hype / 健康养生旅游娱乐。\n"
    "若主题命中违规清单 · 直接报错退出 · 不要硬写。\n\n"
)


# 反 AI 检测 / humanize · 让 LLM 写出来的文章像人写(2026-04-26 加)
# Why:用户决策不勾「AI 创作声明」· 但必须骗过微信 AI 检测器避免软限流 50%+ 降权
# 核心原则:LLM 痕迹 = 句式整齐 + 连接词刻板 + emoji 模式化 + 数字过整 + 缺真实锚点
_HUMANIZE_RULES = (
    "**🚨 反 AI 检测必守(2026-04-26 用户锁 · 不勾 AI 声明 · 必须骗过算法)**:\n"
    "1. **句长方差大**:8 字短句 + 30-50 字长句**交错** · 不能全 20-30 字均匀句\n"
    "   ❌ LLM 写法:每句 25 字左右整齐(明显 AI)\n"
    "   ✅ 人写法:「这事儿一夜变了。」+ 「我昨晚 11 点收到群里截图,看完盯着屏幕 3 分钟没说话,因为这意味着...」\n"
    "2. **不用 LLM 套话连接词**:禁用「然而 / 此外 / 总之 / 综上 / 与此同时 / 值得一提的是」\n"
    "   改用人话:「但」「再说」「话说回来」「关键是」「这不」「问题是」\n"
    "3. **数字必须真实带波动**:不写 100 / 1000 / 50% 这种整数\n"
    "   ✅ 用 87 / 1247 / 53.4% / $12,847 这种「我真测过」的具体数字\n"
    "4. **必带 1-3 处真实经历锚点**:具体地点 + 时间 + 人(让 LLM 写不出来的细节)\n"
    "   ✅ 「上周三晚 11 点武汉光谷的星巴克」「我哈工大同学张工 4090 上跑的」\n"
    "   ✅ 智辰真实背景:深圳/武汉双基地 · openclaw 武汉创业群 · 半导体 6 年 · 哈工大本硕\n"
    "5. **段落长度不均**:1 行段 + 5 行段 + 单句段 混着用 · 不能全统一 3 行段\n"
    "6. **emoji 不模式化**:全文 0-3 个 emoji 即可(不是每段开头一个)· 偶尔在意外位置出现\n"
    "7. **偶尔个人怀疑句**:「我也没完全看明白」「这事我没想清楚」「不确定对不对」\n"
    "   LLM 不写自我怀疑 · 加 1-2 处立刻像人\n"
    "8. **方言 / 口头语点缀**:每篇 1-2 处 · 「这玩意儿」「整不明白」「咱」「得嘞」「服了」\n"
    "9. **不用「让我们」「我们一起」**:LLM 高频 · 改「我」第一人称\n"
    "10. **段尾偶尔不完整**:「这个先按下不表。」「这事我下篇再说。」(LLM 倾向每段都有总结)\n\n"
    "**自检步骤**(写完后):\n"
    "- 数一下「然而 / 此外 / 总之」出现几次 · ≥1 次重写\n"
    "- 数一下整数(100 / 50% / 1000)出现几次 · ≥3 次改成不规整数字\n"
    "- 看段长方差 · 全 3-5 行段就太规整 · 加几处单句段\n"
    "- 看有没有真实地点/时间/人名 · 0 处必加 1-2 处\n\n"
)


_COMMON_TAIL_RULES = (
    _TOPIC_SCOPE_RULES
    + _HUMANIZE_RULES
    + "**通用必守**:\n"
    "- **不要写 H1**(WeChat 草稿箱标题由 publish 单独传入,H1 会重复)\n"
    "- 第一行直接写 `![](images/cover.png)`(alt **必须留空**,否则会渲染出「封面」二字)\n"
    "- 文末**压轴必须**放一张完整的「智辰老师」介绍卡(含嵌入公众号关注卡视觉),格式:\n"
    "  ```\n"
    "  :::author-card\n"
    "  name: 智辰老师\n"
    "  tagline: 独立开发者 · AI 红利观察者 · openclaw 武汉创业群群主\n"
    "  bio: <根据本文主题自然带出 1-2 句 · 含「AI 红利,看智辰」口号>\n"
    "  mp_brand: 宸的 AI 掘金笔记\n"
    "  mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。\n"
    "  mp_meta: 关注获取每日 AI 红利信号 · 看智辰\n"
    "  tags: [AI 红利, <2-3 个本文相关标签>]\n"
    "  footer: 扫码加我微信备注「<本文相关关键词>」· 我会拉你进读者群\n"
    "  :::\n"
    "  ```\n"
    "  `mp_brand/mp_desc/mp_meta` 三字段会渲染成嵌入式公众号关注卡视觉。\n"
    "- author-card **下方**仍要带:两个二维码 `![](images/qr-zhichen.png)` 和 `![](images/qr-openclaw.png)` + aipickgold.com 安利段\n"
    "- 写完返回一行:'DONE {absolute_path}'\n"
    "- 即便忘了上述 · publish 阶段会兜底 sanitize · 但写对省一道清理。\n\n"
    "作者身份:style.yaml 的 author/brand 字段 · 口号「AI 红利,看智辰」"
)


def _build_prompt_hotspot(topic, out_path: Path) -> str:
    """热点观察 / 非共识解读 prompt(原 prompt)。"""
    return (
        "请使用 wewrite skill 写一篇微信公众号文章(**热点系列 · 非共识解读**),主题:\n\n"
        f"**{topic['title']}**\n(来源:{topic['source']} · 热度 {topic['hot']:.0f})\n\n"
        "**系列定位**:这篇属于「热点观察 / AI 非共识」系列。\n"
        "选用 `references/frameworks.md` 里的框架(痛点型/故事型/观点型/盘点型/对比型)。\n"
        "persona 推荐:`midnight-friend` / `industry-observer` / `sharp-journalist`。\n"
        + _load_identity_block()
        + _load_kol_patterns_block() + "\n"
        + _load_news_hub_reactions_block(topic)
        + "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **1800-2500 字** · 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "4. 按需插入内文 chart 占位符 `![](images/chart-1.png)` ... `chart-4.png`\n"
        "   配图 layout 推荐(信息密度型):dense-modules / dashboard / story-mountain / bento-grid / comparison-matrix\n\n"
        + _COMMON_TAIL_RULES
    )


def _build_prompt_shortform(topic, out_path: Path, *, shortform_type: str = "auto") -> str:
    """短文(副推位)prompt · 800-1500 字 · 钩子型 · 反复换行(2026-04-23 加)。

    shortform_type:
      - "auto" : 让 claude 自己根据主题选 S1-S7
      - "S1".."S7" : 强制走某套框架
    """
    type_hint = (
        f"**强制使用框架**:`references/shortform-frameworks.md` 里的 {shortform_type}。"
        if shortform_type != "auto"
        else "选用 `references/shortform-frameworks.md` 里 S1-S7 中**最适合本主题**的一套(默认 S2 数据快讯或 S7 失败踩坑)。"
    )
    return (
        "请使用 wewrite skill 写一篇微信公众号**副推短文**,主题:\n\n"
        f"**{topic['title']}**\n\n"
        + _TOPIC_SCOPE_RULES + _HUMANIZE_RULES +
        "**系列定位**:这是「短文 / 副推位」 · 跟主推一起 1 次群发 · **不是长文**。\n"
        "目标:让读者刷手机时一口气读完 · 短句 + 反复换行 + 数据密集 · 留个钩子让人加私域。\n\n"
        f"{type_hint}\n\n"
        "**写作 persona 用 `shortform-writer`**(短文写手 · 钩子型 · 第一人称 · 见 `personas/shortform-writer.yaml`)。"
        + _load_identity_block()
        + _load_kol_patterns_block(top_n_hooks=3) + "\n"
        + _load_news_hub_reactions_block(topic)
        + "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **800-1500 字**(超过 1500 直接砍 · 短文不允许凑字数)\n"
        "4. **★ 排版规则(死守 · 这是短文区别长文的核心):**\n"
        "   - 标题:钩子句 + `!!!`(5-15 字 · 必带情绪)\n"
        "   - 每段 **1-3 行**(超过 3 行就拆 · 4 行段直接错)\n"
        "   - 段间 **空一行**(留白密集 · 手机一屏只显示 4-6 行)\n"
        "   - 全文 `!!!` 出现 **2-5 次**(强化情绪)\n"
        "   - **每 200 字必带 1 个具体数字**(避免「很多」「不少」「不少人」)\n"
        "   - 每段最多 1 处 `**加粗**`(不要乱加粗)\n"
        "   - 至少 5 个段落是**单句段**(不是「一句话」 · 是「整段只有一句」)\n\n"
        "5. **★ 不要做的事(短文专属约束):**\n"
        "   - ❌ 不要写 `![](images/cover.png)`(短文用 1:1 thumb · 不放大封面)\n"
        "   - ❌ 不要写 `![](images/chart-3.png)` `chart-4`(短文最多 0-2 张内文图 · chart-1 / chart-2 即可)\n"
        "   - ❌ 不要写复杂 H2 结构(段落直接走 · H2 至多 2 个)\n"
        "   - ❌ 不要写完整 author-card(sanitize 会用 mini 版兜底)\n"
        "   - ❌ 不要写 SEO 锚点 `<!-- ✏️ ... -->` / TOC / 编辑标记\n"
        "   - ❌ 不要写「这里限于篇幅就不展开了」(短文本来就不展开)\n"
        "   - ❌ 不要凑长文的「目标 → 操作 → 验证」结构(那是长文的)\n\n"
        "6. **结尾**:1 句行动钩子(评论 / 转发 / 加私域)+ 一行空 + sanitize 自动注入 mini author-card + QR 二维码块。\n"
        "   你写的结尾示例(任选):\n"
        "   - 「你的看法?评论区。」\n"
        "   - 「完整论证看主推那篇。」\n"
        "   - 「加我备注「X」· 拉你进群。」\n"
        "   - 「认同?转发。不认同?评论区辩。」\n"
        "   sanitize 会兜底注入两个 QR 块(`qr-zhichen.png` + `qr-openclaw.png`)· 你不用主动写 ·\n"
        "   但若想自己写 · 用 `![](images/qr-openclaw.png)` 引用即可。\n\n"
        "7. **不要写「H1 一级标题」**(WeChat 草稿箱用 publish 单独传 title · H1 会重复)。\n"
        "   首行直接进首段钩子(参考 `references/shortform-frameworks.md` 各 S 模板)。\n\n"
        "8. 写完返回一行:'DONE {absolute_path}'\n\n"
        "**示例对比** · 一段长文要拆成 3 段短文:\n"
        "  长文段(✗ 短文不要):\n"
        '  > "在使用 Cursor 的过程中,我发现一个很关键的细节:它对长文件的索引能力其实是有上限的,大致在 2000 行左右,超过这个长度,代码补全就会出现明显的延迟和上下文丢失,这一点在官方文档里没有写明..."\n\n'
        "  短文重写(✓):\n"
        "  > Cursor 有个坑没人说。\n"
        "  > \n"
        "  > **超过 2000 行的文件 · 它就崩了。**\n"
        "  > \n"
        "  > 补全延迟 · 上下文丢失 · 各种诡异。\n"
        "  > \n"
        "  > 官方不说 · 我跑了 7 天发现的。\n"
        "  > \n"
        "  > 解决:文件拆 1500 行以下。亲测稳。\n"
    )


def _build_prompt_case(topic, out_path: Path) -> str:
    """AI 真实成功案例 prompt(2026-04-23 加 · 周三轮播 · 配图走 case-realistic)。"""
    return (
        "请使用 wewrite skill 写一篇微信公众号文章(**案例系列 · AI 真实成功案例**),主题:\n\n"
        f"**{topic['title']}**\n\n"
        "**系列定位**:这是「AI 真实成功案例」系列 · **不是教程也不是热点**。\n"
        "目标:让读者看完相信「这事确实跑通了 · 不是吹牛」 → 信任 → 关注 + 加私域。\n\n"
        "**写作 persona 用 `tutorial-instructor`** + 「案例叙事人」混合:\n"
        "- 第一人称(我 / 我们)讲一段真实经历\n"
        "- 时间线清晰(Day 0 / Day 7 / Day 30 ...)\n"
        "- 关键节点带具体数字(收入 / 用户 / 时长)\n"
        "- 不画大饼 · 不喊口号 · 失败/坑也要讲一两个(更可信)"
        + _load_identity_block()
        + _load_kol_patterns_block() + "\n"
        + _load_news_hub_reactions_block(topic)
        + "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **2200-3800 字** · 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "4. **结构走 T4 案例叙事型**:背景 → Day 0 起点 → 操作过程 → 结果数据 → 复盘\n"
        "5. **★ 配图占位规则(关键 · 配图阶段会按这个生图):**\n"
        "   - `![](images/cover.png)` · 真实产品 UI 截图风(macOS / iOS / 浏览器)\n"
        "   - `![](images/chart-1.png)` · 真实 dashboard 数据截图(Stripe / Mixpanel / Vercel 风)\n"
        "   - `![](images/chart-2.png)` · 功效对比图(before/after split 或 30 天曲线)\n"
        "   - `![](images/chart-3.png)` · 真实操作截图(terminal / VS Code / DevTools)\n"
        "   - `![](images/chart-4.png)` · 真实结果证明(Stripe 通知 / GitHub stars / Tweet 截图)\n"
        "6. **★ 配图占位符上方/下方文字必须含具体数字**(让生图能抓到):\n"
        "   - 不写「收入很多」 · 写「截至 Day 30 累计 $12,847」\n"
        "   - 不写「用户增长不少」 · 写「DAU 从 320 涨到 4,891」\n"
        "   - 不写「响应很快」 · 写「P95 latency 从 2,340ms 降到 187ms」\n"
        "   - 数字要看起来「不像是凑出来的整数」(避免 5000 / 10000 这种)\n"
        "7. 钩子用承诺型 + 反预期:「我以为 X · 结果 Y」「30 天前我还在 X · 现在 Y」\n"
        "8. 标题倾向(选一种):\n"
        "   - 「我用 X 30 天做到 Y · 完整复盘」\n"
        "   - 「跑通了:Cursor + Claude Code 写完 N 行代码的真实账单」\n"
        "   - 「读者反馈:用 X 一周搞了 $N · 是怎么做到的」\n"
        "   - 「Day N 复盘:X 跑通了哪些 · 没跑通哪些」\n\n"
        + _COMMON_TAIL_RULES
    )


def _build_prompt_tutorial(topic, out_path: Path) -> str:
    """干货 / 教程 / 方法论 prompt(2026-04-21 加 · 新系列入口)。"""
    return (
        "请使用 wewrite skill 写一篇微信公众号文章(**干货系列 · 教程方法论**),主题:\n\n"
        f"**{topic['title']}**\n\n"
        "**系列定位**:这篇属于「干货 / 教程 / 方法论」系列 · **不是热点观察**。\n"
        "选用 `references/tutorial-frameworks.md` 里的框架(T1 步骤教程 / T2 工具评测 / T3 方法论沉淀 / T4 知识科普 / T5 避坑清单),\n"
        "**默认用 T1 步骤教程型**(80% 干货文用这个),除非主题明显更适合其他。\n\n"
        "**写作 persona 用 `tutorial-instructor`**(教程讲师 · 步骤明确 · 操作性强 · 见 `personas/tutorial-instructor.yaml`)。"
        + _load_identity_block()
        + _load_kol_patterns_block() + "\n"
        + _load_news_hub_reactions_block(topic)
        + "严格要求:\n"
        f"1. 文章输出到 `{out_path.relative_to(ROOT)}`\n"
        "2. **只跑 Step 3-5**(框架/素材/写作/SEO/自检),**不要生成图片**,**不要推草稿箱**\n"
        "3. 正文 **2500-4500 字**(教程通常需要更长结构 · 步骤要展开)\n"
        "4. **结构必须步骤化**:每个核心步骤独立 H2 · 推荐格式「Step N: 一句话目标」\n"
        "5. 每步带四要素:【目标】→【操作】→【验证】→【常见坑】(可适度合并)\n"
        "6. 至少 2 个编辑锚点 `<!-- ✏️ ... -->`\n"
        "7. 按需插入内文 chart 占位符 `![](images/chart-1.png)` ... `chart-4.png`\n"
        "   配图 layout 推荐(操作流程型):\n"
        "   - **linear-progression**(★★★★★ 步骤流程 / SOP)\n"
        "   - **comparison-matrix**(★★★★★ 工具横评 / before-after)\n"
        "   - **hierarchical-layers**(★★★★★ 知识体系 / 三层递进)\n"
        "   - funnel(筛选决策)/ tree-branching(选择决策树)/ circular-flow(运行机制)\n"
        "   - 封面优先用 `bento-grid`(N 个要点速览)+ `ikea-manual` style(说明书风格)\n"
        "8. **避免热点系列的非共识口吻**:不要用「真相是」「其实没人告诉你」这种钩子;\n"
        "   要用「读完你能做到 X」「跟着我走一遍」这种承诺式钩子。\n"
        "9. 标题倾向(选一种):\n"
        "   - 「手把手:N 分钟用 X 做到 Y」\n"
        "   - 「X 的 N 个官方文档没说的细节」\n"
        "   - 「我用 X 半年总结的 N 个坑」\n"
        "   - 「从 0 到 1 配置 X 的完整 SOP」\n\n"
        + _COMMON_TAIL_RULES
    )


def run_claude_write(topic, date_str, out_path: Path, style: str = "hotspot"):
    """调 claude -p 让 WeWrite skill 跑 Step 3-5 · 只写文章不生图不发布。

    style:
      - "hotspot"   : 热点观察 / 非共识解读(默认 · 走 frameworks.md)
      - "tutorial"  : 干货 / 教程 / 方法论(走 tutorial-frameworks.md + tutorial-instructor)
      - "case"      : AI 真实成功案例(走 case-realistic 配图 · 数字优先)
      - "shortform" : 副推短文(800-1500 字 · S1-S7 框架 · shortform-writer)
    """
    if style == "shortform":
        prompt = _build_prompt_shortform(topic, out_path)
        print(f"→ claude -p writing [SHORTFORM]... (可能 2-5 分钟 · 短文)")
    elif style == "case":
        prompt = _build_prompt_case(topic, out_path)
        print(f"→ claude -p writing [CASE]... (可能 4-10 分钟 · 案例叙事)")
    elif style == "tutorial":
        prompt = _build_prompt_tutorial(topic, out_path)
        print(f"→ claude -p writing [TUTORIAL]... (可能 5-12 分钟 · 教程文较长)")
    else:
        prompt = _build_prompt_hotspot(topic, out_path)
        print(f"→ claude -p writing [HOTSPOT]... (可能 3-8 分钟)")

    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    r = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {r.stderr[-500:]}")
    return r.stdout


def push_article(md_path: Path, topic, style: str = "hotspot"):
    """Push markdown preview to Discord · 分块(Discord 1900 char 上限)。"""
    md = md_path.read_text(encoding="utf-8")
    word_count = len(md)
    style_tag = "🛠️ 干货系列" if style == "tutorial" else "🔥 热点系列"

    # Header message
    header = (
        f"📝 **文章初稿就绪 · {word_count} 字** · {style_tag}\n"
        f"📌 选题:{topic['title']}\n"
        f"📂 路径:`{md_path.relative_to(ROOT)}`\n"
        f"---\n"
        f"下面推送**预览首段 + 末段 + 目录**。完整正文 Mac 本地查看 `open {md_path}`。\n"
        f"回复 `ok` / `继续` 进入生图 · `改 XX` 编辑 · `重写` 换角度 · `pass` 放弃本篇。"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", header],
        check=True, timeout=60,
    )

    # Preview excerpt
    lines = md.splitlines()
    h2_outline = [l for l in lines if l.startswith("## ")][:8]
    first_para = next((l for l in lines if l and not l.startswith(("#", "!", "<"))), "")
    last_para = ""
    for l in reversed(lines):
        if l and not l.startswith(("#", "!", "<", ":", "-", ">", "|")):
            last_para = l
            break

    excerpt = (
        f"**📑 目录(H2)**\n" + "\n".join(h2_outline) + "\n\n"
        f"**✏️ 开头:**\n{first_para[:400]}{'...' if len(first_para) > 400 else ''}\n\n"
        f"**🎬 结尾:**\n{last_para[:300]}{'...' if len(last_para) > 300 else ''}"
    )
    subprocess.run(
        [str(PY), str(PUSH), "--text", excerpt],
        check=True, timeout=60,
    )


def _parse_argv():
    """解析命令行 · 返回 (argv_idx, custom_idea, style)。

    支持:
      python3 write.py 0                                     · idx
      python3 write.py --idea "<标题>"                        · 自定义 idea
      python3 write.py 0 --style tutorial                    · idx + style
      python3 write.py --idea "<标题>" --style tutorial       · idea + style
      python3 write.py --style tutorial --idea "<标题>"       · 顺序无关
    """
    args = sys.argv[1:]
    style = "hotspot"
    argv_idx = None
    custom_idea = None

    # 先抽 --style(无序)
    if "--style" in args:
        i = args.index("--style")
        if i + 1 >= len(args):
            print("❌ --style 需跟值: hotspot | tutorial | case | shortform", file=sys.stderr); sys.exit(1)
        style = args[i + 1]
        if style not in ("hotspot", "tutorial", "case", "shortform"):
            print(f"❌ --style 只能是 hotspot/tutorial/case/shortform · 收到 {style!r}", file=sys.stderr); sys.exit(1)
        args = args[:i] + args[i + 2:]

    # 再判 --idea / idx
    if args:
        if args[0] == "--idea":
            if len(args) < 2:
                print("❌ --idea 需要跟一个 idea 字符串", file=sys.stderr); sys.exit(1)
            custom_idea = " ".join(args[1:]).strip()
            if not custom_idea:
                print("❌ idea 不能为空", file=sys.stderr); sys.exit(1)
        else:
            try:
                argv_idx = int(args[0])
            except ValueError:
                print(f"❌ 首参数要么 idx (0-based) 要么 --idea '...'", file=sys.stderr); sys.exit(1)

    return argv_idx, custom_idea, style


def _auto_style_from_topic(topic: dict, cli_style: str) -> str:
    """阶段 D · idx 模式下根据 topic 来源 / category 推断 style。

    规则:
      - cli_style == "case"  → 强制 case(命令行显式指定优先 · 也覆盖 idea category)
      - from == "hotspot"   → 用 cli_style(默认 hotspot)
      - from == "idea":
          category == "tutorial"  → 强制 tutorial
          category == "hotspot"   → 强制 hotspot
          category == "flexible"  → 用 cli_style
      - 缺字段(老 session 兼容)→ 用 cli_style

    auto_pick 走 session.auto_schedule.style → 由 main() 显式传 cli_style="case",
    所以这里 case 优先级最高 · 不会被 idea category 覆盖回 tutorial。
    """
    if cli_style == "case":
        return "case"
    src = topic.get("from")
    if src == "idea":
        cat = topic.get("category", "flexible")
        if cat == "tutorial":
            return "tutorial"
        if cat == "hotspot":
            return "hotspot"
        return cli_style
    return cli_style


def main():
    argv_idx, custom_idea, cli_style = _parse_argv()
    style = cli_style  # 默认 = 命令行 · 走 idx 路径时可能被 idea category 覆盖
    idea_id_to_mark = None  # 写完成功后调 mark_used 的 id

    if custom_idea:
        # 构造一个虚拟 topic · 绕过 brief 状态检查
        topic = {
            "title": custom_idea,
            "source": "用户 idea",
            "hot": 0,
            "score": 100,
            "ai_kw": "custom",
            "url": "",
        }
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = slugify(custom_idea)
        out_path = ROOT / "output" / f"{date_str}-{slug}.md"
        _state.advance(
            "writing",
            selected_idx=-1, selected_topic=topic,
            article_md=str(out_path.relative_to(ROOT)),
        )
    else:
        s = _state.load()
        if s["state"] != _state.STATE_BRIEFED and argv_idx is None:
            print(f"❌ state={s['state']} · 先跑 brief 选 Top 3", file=sys.stderr); sys.exit(1)

        topics = s.get("topics") or []
        if not topics:
            print("❌ session 无 topics,先 brief", file=sys.stderr); sys.exit(1)

        idx = argv_idx if argv_idx is not None else (s.get("selected_idx") or 0)
        if idx < 0 or idx >= len(topics):
            print(f"❌ idx {idx} out of range(0-{len(topics)-1})", file=sys.stderr); sys.exit(1)

        topic = topics[idx]
        date_str = s.get("article_date") or datetime.now().strftime("%Y-%m-%d")
        slug = slugify(topic["title"])
        out_path = ROOT / "output" / f"{date_str}-{slug}.md"

        # 阶段 D · 按 from/category 自动推断 style · 记 idea_id 等写完后标 used
        style = _auto_style_from_topic(topic, cli_style)
        if topic.get("from") == "idea" and topic.get("idea_id") is not None:
            idea_id_to_mark = topic.get("idea_id")

        _state.advance(
            "writing",
            selected_idx=idx, selected_topic=topic,
            article_md=str(out_path.relative_to(ROOT)),
        )

    try:
        run_claude_write(topic, date_str, out_path, style=style)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr); sys.exit(2)

    if not out_path.exists():
        print(f"❌ claude 跑完但 {out_path} 不存在 · 看 claude stdout 排查", file=sys.stderr)
        sys.exit(3)

    _state.advance(_state.STATE_WROTE, article_md=str(out_path.relative_to(ROOT)),
                   style=style)

    # 阶段 D · idea 库选题写完 · 自动标 used
    src_tag = ""
    if idea_id_to_mark is not None:
        try:
            _idea_bank.mark_used(
                idea_id_to_mark,
                article_md=str(out_path.relative_to(ROOT)),
            )
            src_tag = f" · from idea #{idea_id_to_mark}"
        except Exception as e:
            print(f"⚠ mark_used idea #{idea_id_to_mark} 失败: {e}", file=sys.stderr)

    push_article(out_path, topic, style=style)
    print(f"✓ wrote [{style}{src_tag}] · {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
