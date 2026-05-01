#!/usr/bin/env python3
"""Workflow 1 · 选题 brief
跑 Step 1-2 · 生成 Top 3 选题 · push 到手机等用户回复序号。

用法: python3 scripts/workflow/brief.py
"""
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state
import _idea_bank

ROOT = Path(__file__).resolve().parent.parent.parent
PUSH = ROOT / "discord-bot" / "push.py"
FETCH = ROOT / "scripts" / "fetch_hotspots.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def fetch_hotspots(limit=60):
    r = subprocess.run(
        [str(PY), str(FETCH), "--limit", str(limit)],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        raise RuntimeError(f"fetch_hotspots: {r.stderr[:300]}")
    return json.loads(r.stdout).get("items", [])


def load_style_topics():
    sf = ROOT / "style.yaml"
    if not sf.exists():
        return []
    import yaml
    d = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
    return d.get("topics", [])


# =================================================================
# AI 白名单 · 严格过滤 · 非 AI 热点一律不入选
# 分 3 tier:核心词(满分命中) / 公司产品(满分) / 边缘词(半分)
# =================================================================

KW_CORE = [
    # 核心 AI 概念
    "AI", "ai", "人工智能", "大模型", "LLM", "AGI", "AIGC",
    "智能体", "agent", "Agent", "多模态", "神经网络",
    # 必点的 AI Coding / 效率 / 办公自动化
    "AI Coding", "AI coding", "vibe coding", "自动编程", "代码生成",
    "效率", "生产力", "办公自动化", "工作流", "workflow",
]

KW_PRODUCT = [
    # 海外明星产品/公司
    "ChatGPT", "GPT", "GPT-4", "GPT-5", "Claude", "claude", "Gemini",
    "Cursor", "cursor", "Copilot", "Codex", "Devin", "Windsurf",
    "OpenAI", "Anthropic", "Meta AI", "xAI", "Grok", "Mistral",
    "Midjourney", "Sora", "Runway", "Stable Diffusion", "Suno", "Pika",
    "Perplexity", "Cohere", "Character.AI",
    # 国产
    "Kimi", "月之暗面", "豆包", "字节", "通义", "文心", "智谱", "清言",
    "MiniMax", "DeepSeek", "deepseek", "百川", "阶跃", "零一", "moonshot",
    "可灵", "即梦", "讯飞星火", "腾讯混元", "Qwen", "ChatGLM",
    # AI 创业/赚钱
    "AI 创业", "AI创业", "AI 赚钱", "AI赚钱", "AI 副业", "AI副业",
    "AI 变现", "AI变现", "AI 工具", "AI工具",
]

KW_EDGE = [
    # 边缘 40 分 · 单独命中能入选但排在 core/product 后面
    "算力", "英伟达", "H100", "H200", "TPU", "GPU",
    "提示词", "prompt", "RAG", "微调", "训练", "蒸馏", "推理",
    "Notion", "Obsidian", "Raycast",
    "芯片", "台积电",
    # 机器人/具身 · 用户要求「少量掺杂」 · 降到边缘权重
    "机器人", "具身智能", "人形机器人", "Optimus", "宇树", "Figure",
    "特斯拉 FSD", "FSD", "自动驾驶",
]


def ai_score(title: str) -> tuple[int, str]:
    """
    返回 (ai_score, matched_kw)。未命中返回 (0, "")。
    核心词 100 · 产品公司 90 · 边缘词 40(单独不够,需组合)。
    """
    for kw in KW_CORE:
        if kw in title:
            return (100, kw)
    for kw in KW_PRODUCT:
        if kw in title:
            return (90, kw)
    for kw in KW_EDGE:
        if kw in title:
            return (40, kw)
    return (0, "")


def topic_bonus(title: str, focus_topics: list[str]) -> int:
    """style.yaml 的 topics 作为辅助权重 · 命中 +20"""
    for t in focus_topics:
        for kw in (t or "").replace("/", " ").split():
            kw = kw.strip()
            if kw and kw in title:
                return 20
    return 0


ROBOT_KWS = {"机器人", "具身智能", "人形机器人", "Optimus", "宇树", "Figure",
             "特斯拉 FSD", "FSD", "自动驾驶"}


def pick_top_ai(items, focus_topics, max_n=5, robot_cap=2):
    """
    硬过滤:只保留 ai_score > 0 的热点。
    综合分 = ai_score * 0.55 + hot_normalized * 0.3 + topic_bonus * 0.15
    机器人/具身类 cap · 最多占 robot_cap 条(用户要求「少量掺杂」)。
    返回 (topics, stats)。
    """
    scored = []
    total = len(items)
    for i, item in enumerate(items):
        title = item.get("title", "")
        ai, kw = ai_score(title)
        if ai == 0:
            continue  # 硬过滤 · 非 AI 直接剔除
        hot = item.get("hot_normalized", 0) or 0
        bonus = topic_bonus(title, focus_topics)
        score = round(ai * 0.55 + hot * 0.3 + bonus * 0.15, 1)
        scored.append({
            "idx": i,
            "title": title,
            "source": item.get("source", ""),
            "hot": hot,
            "score": score,
            "ai_kw": kw,
            "is_robot": kw in ROBOT_KWS,
            "url": item.get("url", ""),
            "from": "hotspot",
            "idea_id": None,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    # 应用 robot cap: 非机器人优先填 · 机器人最多 robot_cap 条
    picked, robots = [], []
    for s in scored:
        if s["is_robot"]:
            if len(robots) < robot_cap:
                robots.append(s)
        else:
            picked.append(s)
        if len(picked) + len(robots) >= max_n:
            break
    out = (picked + robots)[:max_n]

    stats = {"total": total, "ai_matched": len(scored),
             "robot_in_pool": sum(1 for s in scored if s["is_robot"])}
    return out, stats


def fetch_idea_topics(limit=3):
    """从 idea 库取未用 Top N · 转成跟 hotspot topic 同结构。

    返回 list[dict] · 每项含 from='idea' · idea_id · category。
    idea 库为空时返回 []。
    """
    try:
        ideas = _idea_bank.list_ideas(only_unused=True, limit=limit) or []
    except Exception:
        return []
    out = []
    for it in ideas:
        out.append({
            "title": it.get("title", ""),
            "source": "idea 库",
            "hot": 0,
            "score": float(it.get("priority", 0) or 0),
            "ai_kw": "idea",
            "is_robot": False,
            "url": "",
            "from": "idea",
            "idea_id": it.get("id"),
            "category": it.get("category", "flexible"),
        })
    return out


def format_message(topics, stats, idea_count=0):
    """格式化 Discord 推送消息 · 热点 + idea 分两段。

    topics 是合并后的列表(热点在前 · idea 在后)。
    idea_count 表示 topics 末尾连续 idea 项数(0 时不显示 idea 段)。
    """
    date = datetime.now().strftime("%m-%d")
    n = len(topics)
    hotspot_n = n - idea_count

    if n == 0:
        head = [
            f"📰 **{date} · 今日 AI 选题 Top 0**",
            f"_AI 白名单过滤 · {stats['ai_matched']}/{stats['total']} 命中 · 综合分排序_",
            "",
            "⚠️ 今日热点榜全是非 AI 内容 · 无可选题。",
            "可回 `pass` 跳过今天,或等晚些再 `brief`。",
            "(考虑加 36kr / IT 之家等 AI 专门源以改善)",
        ]
        return "\n".join(head)

    lines = [
        f"📰 **{date} · 今日 AI 选题 Top {n}**",
        f"_AI 白名单过滤 · {stats['ai_matched']}/{stats['total']} 命中 · 综合分排序_",
        "",
    ]

    # 热点段
    if hotspot_n > 0:
        lines.append(f"🔥 **今日热点 Top {hotspot_n}**")
        for i in range(hotspot_n):
            t = topics[i]
            lines.append(f"**{i+1}.** {t['title']}")
            lines.append(
                f"    📊 {t['score']} · 🔥 {t['source']} · 热度 {t['hot']:.0f} · 🎯 `{t['ai_kw']}`"
            )
        lines.append("")

    # idea 段
    if idea_count > 0:
        lines.append(f"📌 **你的 idea 库 Top {idea_count}**")
        for j in range(idea_count):
            i = hotspot_n + j
            t = topics[i]
            cat = t.get("category", "flexible")
            iid = t.get("idea_id")
            id_tag = f"#idea_id_{iid}" if iid is not None else ""
            lines.append(f"**{i+1}.** {t['title']}")
            lines.append(f"    📌 {cat} · {id_tag}")
        lines.append("")

    lines.append("---")
    pick_nums = " / ".join(f"`{i}`" for i in range(1, n + 1))
    lines.append(f"👉 回复 {pick_nums} 选一个 · 或 `pass` 今天跳过")
    return "\n".join(lines)


def push(text):
    r = subprocess.run(
        [str(PY), str(PUSH), "--text", text],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"push: {r.stderr[:300]}")


def main():
    print("→ fetching hotspots...")
    items = fetch_hotspots(60)
    print(f"  got {len(items)} items")
    hot_topics, stats = pick_top_ai(items, load_style_topics(), max_n=5)
    print(f"  AI-matched: {stats['ai_matched']}/{stats['total']} · picked {len(hot_topics)}")

    # 阶段 D · 追加 idea 库 Top 3 未用 idea
    idea_topics = fetch_idea_topics(limit=3)
    print(f"  idea bank: {len(idea_topics)} unused appended")

    topics = list(hot_topics) + list(idea_topics)
    idea_count = len(idea_topics)

    if not topics:
        # 既无 AI 热点也无 idea · 推消息告知用户 · 不进 briefed 状态
        push(format_message([], stats, idea_count=0))
        print("⚠ no hotspots & no ideas · kept state=idle · user notified", file=sys.stderr)
        return 0

    try:
        _state.advance(
            _state.STATE_BRIEFED,
            article_date=datetime.now().strftime("%Y-%m-%d"),
            topics=topics,
            selected_idx=None,
            article_md=None,
            images_dir=None,
            draft_media_id=None,
        )
    except _state.StateGuardError as e:
        cur = _state.get_state()
        push(f"⚠ brief skip · session 已在 {cur} · 不重置进行中的工作\n"
             f"如要开新文 · 在 Discord 回 `reset` 或 `pass`")
        print(f"⚠ {e}", file=sys.stderr)
        return 0
    msg = format_message(topics, stats, idea_count=idea_count)
    push(msg)
    print(f"✓ briefed · {len(hot_topics)} hotspots + {idea_count} ideas pushed · awaiting user pick")
    return 0


if __name__ == "__main__":
    sys.exit(main())
