"""_topic_guard.py · 7 大主题守门 · 2026-04-26 锁。

提供:
  - is_ai_topic(title, summary="") → bool · 标题/摘要是否 AI 类
  - classify_topic(title, summary="") → str | None · 命中哪个主题(7 选 1)· None 表示越界
  - WHITELIST / BLACKLIST · AI 关键词清单(代码层守门)

被 fetch_kol.py / auto_pick.py / write.py 共用 · 单一信源。
"""
from __future__ import annotations

import re

# ──────────────────────────────────────────────────────────────
# 7 大主题(WeWrite 核心宗旨 · 用户 2026-04-26 重锁)
# ──────────────────────────────────────────────────────────────
THEMES_7 = [
    "AI 干货",
    "AI 教程",
    "AI 赚钱",
    "AI 创业",
    "AI 真实测评",
    "AI 踩坑",
    "AI 感悟",
]

# ──────────────────────────────────────────────────────────────
# AI 关键词白名单 · 标题/正文含 ≥1 才认 AI · 否则 reject
# ──────────────────────────────────────────────────────────────
AI_KEYWORDS = (
    # 通用
    "AI", "A.I.", "人工智能", "大模型", "LLM", "大语言模型", "多模态", "AIGC",
    # 模型 / 厂商
    "Claude", "Anthropic", "GPT", "ChatGPT", "OpenAI", "Gemini", "Grok",
    "DeepSeek", "Llama", "Qwen", "Mistral", "Sonnet", "Opus", "Haiku",
    "豆包", "文心", "通义", "智谱", "Kimi", "MiniMax",
    # Agent / 工具
    "Agent", "智能体", "多智能体", "Copilot", "Cursor", "Devin", "Codex",
    "Claude Code", "Cline", "Aider",
    # 提示词 / 工程
    "提示词", "Prompt", "提示工程", "RAG", "微调", "fine-tune", "embedding",
    "function calling", "tool use", "tool_use",
    # 图像 / 视频
    "Stable Diffusion", "Midjourney", "Sora", "nano-banana", "图像生成",
    "Veo", "Runway", "GPT Image",
    # 协议 / 框架
    "MCP", "Skills", "Skill", "workflow",
    # 实战词
    "自动化", "智能化", "向量数据库",
)

# 编译关键词正则(不区分大小写)· 避免逐个 in
_AI_PATTERN = re.compile(
    r"(?i)" + r"|".join(re.escape(k) for k in AI_KEYWORDS)
)

# ──────────────────────────────────────────────────────────────
# AI 新闻资讯黑名单 · 命中且没干货信号 → reject
# 用户 2026-04-26 原话「ai 新闻咨询不制作这类内容」
# ──────────────────────────────────────────────────────────────
NEWS_KEYWORDS = (
    # 资讯发布速报
    "刚刚", "速看", "重磅", "速递", "速报", "简报", "周报", "月报", "日报",
    "快讯", "突发",
    # 投资 / 估值
    "估值", "融资", "上市", "IPO", "投资人视角", "投资视角",
    # 趋势咨询
    "趋势预测", "趋势分析", "行业判断", "宏观判断", "季度展望",
    "市场分析", "行业研判", "市场展望", "格局展望",
    # 发布会式
    "发布会", "重大更新", "发布了", "正式发布", "重磅发布",
)

_NEWS_PATTERN = re.compile(
    r"(?i)" + r"|".join(re.escape(k) for k in NEWS_KEYWORDS)
)

# ──────────────────────────────────────────────────────────────
# 干货/实战信号词 · 即便命中 NEWS_KEYWORDS · 有这些就赦免
# ──────────────────────────────────────────────────────────────
SUBSTANCE_SIGNALS = (
    "我用", "我跑", "我测", "实测", "实战", "跑通", "踩坑", "翻车",
    "教程", "step", "Step", "step-by-step", "step by step",
    "对比", "横评", "横测", "PK", "vs",
    "复盘", "教训", "感悟", "心得",
    "副业", "月入", "ROI", "变现", "搞钱", "赚钱",
    "0 到 1", "0→1", "Day 0", "Day 1", "Day N",
)

_SUBSTANCE_PATTERN = re.compile(
    r"(?i)" + r"|".join(re.escape(k) for k in SUBSTANCE_SIGNALS)
)

# ──────────────────────────────────────────────────────────────
# 必拒话题词(无 AI 也不行)· 写作鸡汤 / 普通副业 / 养生 / 政治
# ──────────────────────────────────────────────────────────────
HARD_REJECT_KEYWORDS = (
    # 写作鸡汤(粥左罗式)
    "倾诉委屈", "敢吵架", "敢冲突", "敢强势",
    "外向", "社牛", "情商", "人际",
    # 普通副业
    "读书是", "读书,",
    # 养生 / 健康 / 旅游
    "修身养性", "养生", "保养", "健康饮食", "旅游攻略",
    # 政治 / 币圈
    "政治局", "比特币", "加密货币", "矿池",
    # 八卦
    "塌房", "出轨", "塌了",
)

_HARD_REJECT_PATTERN = re.compile(
    r"(?i)" + r"|".join(re.escape(k) for k in HARD_REJECT_KEYWORDS)
)


def is_ai_topic(title: str, summary: str = "") -> bool:
    """标题 + 摘要是否 AI 主题(关键词级别守门)。

    规则:
      1. 命中 HARD_REJECT_KEYWORDS → False(写作鸡汤 / 普通副业 / 政治 ...)
      2. 不含任何 AI 关键词 → False
      3. 命中 NEWS_KEYWORDS 且无 SUBSTANCE_SIGNALS → False(新闻资讯类)
      4. 否则 True
    """
    text = f"{title or ''}\n{summary or ''}"
    if not text.strip():
        return False
    if _HARD_REJECT_PATTERN.search(text):
        return False
    if not _AI_PATTERN.search(text):
        return False
    has_news = bool(_NEWS_PATTERN.search(text))
    has_substance = bool(_SUBSTANCE_PATTERN.search(text))
    if has_news and not has_substance:
        return False
    return True


def reject_reason(title: str, summary: str = "") -> str | None:
    """返回拒绝原因 · 命中 → 短句 · 通过 → None。"""
    text = f"{title or ''}\n{summary or ''}"
    if not text.strip():
        return "空标题"
    if m := _HARD_REJECT_PATTERN.search(text):
        return f"硬拒词:{m.group()}"
    if not _AI_PATTERN.search(text):
        return "无 AI 关键词"
    has_news = bool(_NEWS_PATTERN.search(text))
    has_substance = bool(_SUBSTANCE_PATTERN.search(text))
    if has_news and not has_substance:
        return "AI 新闻资讯类(只发新闻不写干货)"
    return None


def classify_topic(title: str, summary: str = "") -> str | None:
    """关键词级别粗分 · 返回 7 主题之一 · None 表越界。

    精细判断走 topic-curator sub-agent · 这里只做快速标注。
    """
    if not is_ai_topic(title, summary):
        return None
    text = f"{title or ''}\n{summary or ''}"
    t = text.lower()

    # 优先级从具体到泛
    if any(k in text for k in ("踩坑", "翻车", "教训", "失败", "坑")):
        return "AI 踩坑"
    if any(k in text for k in ("月入", "副业", "变现", "ROI", "赚钱", "搞钱", "红利")):
        return "AI 赚钱"
    if any(k in text for k in ("0 到 1", "0→1", "创业", "创办", "做产品", "SaaS")):
        return "AI 创业"
    if any(k in text for k in ("实测", "横评", "横测", "对比", "PK", "vs", "测评", "评测")):
        return "AI 真实测评"
    if any(k in text for k in ("教程", "step", "Step", "上手", "跑通", "明天就能用", "5 分钟")):
        return "AI 教程"
    if any(k in text for k in ("感悟", "心得", "反思", "冷观察", "非共识", "反共识")):
        return "AI 感悟"
    # 默认 AI 干货
    return "AI 干货"


__all__ = [
    "THEMES_7",
    "AI_KEYWORDS",
    "NEWS_KEYWORDS",
    "SUBSTANCE_SIGNALS",
    "HARD_REJECT_KEYWORDS",
    "is_ai_topic",
    "reject_reason",
    "classify_topic",
]
