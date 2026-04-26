"""hotspot_to_idea.py · 半小时拉 ai-news-hub 热点 · LLM 改写成「干货 idea」入 idea_bank。

关键设计:
  - news_hub_reader.read_news 拉最近 72 小时(前 2 天热点也允许 · 用户原话)
  - _topic_guard.is_ai_topic 守门(必须 AI · 拒新闻资讯类)
  - 命中 NEWS 词 + 没 SUBSTANCE 信号的 hotspot:LLM 改写成干货标题
  - 改写后再过守门 · 验证不变成新闻播报
  - 入 idea_bank · category="hotspot_substance" · source="hotspot"
  - 半小时 cron 跑 · 每次 ≤ 5 个 hotspot · 单日上限 60(防 LLM 成本失控)

用户原话(2026-04-26 11:23):
  「根据 ai-news-hub 每半个小时的热点来写干货文章 · 你随时都可以获取灵感 ·
   甚至前两天的内容只要有热度你就可以做」

幂等:hotspot 已被 mark_seen=wewrite → news_hub_reader 自动跳过 · 不重复入库。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))  # for lib/

import _idea_bank  # noqa: E402
from _topic_guard import is_ai_topic, reject_reason  # noqa: E402
from lib import llm_service  # noqa: E402 · 统一接 cpa.gateway

try:
    import news_hub_reader as nhub  # noqa: E402
except ImportError:
    nhub = None

# 单日上限(防 LLM 失控)
DAILY_CAP = int(os.environ.get("HOTSPOT_DAILY_CAP", "60"))
# 每次跑最多 N 个 hotspot · 半小时 5 个 = 一天 240 候选 · 守门 + dedup 后预计 60 入库
PER_RUN_LIMIT = int(os.environ.get("HOTSPOT_PER_RUN_LIMIT", "5"))

REWRITE_PROMPT = """你是中文 AI 公众号选题编辑。任务:把「AI 发布速报」标题改写成「具体的干货 idea 标题」。

7 大允许主题(必须命中 1 个):
  1. AI 干货 — know-how / 框架 / 模板
  2. AI 教程 — step-by-step
  3. AI 赚钱 — 副业 / 变现 / 月入
  4. AI 创业 — 0→1 / SaaS / Indie
  5. AI 真实测评 — 实测 / 横评 / 数据
  6. AI 踩坑 — 翻车 / 教训 / 复盘
  7. AI 感悟 — 反共识 / 长期视角

🚫 严禁:
  - 不要写新闻速报(「刚刚 X 发布」「重磅速看」)
  - 不要直接复述发布会内容
  - 不要罗列特性(「3 个变化」「5 大新功能」这种纯归纳)

✅ 必做:
  - 改成第一人称视角:「我用 / 我跑 / 我测 / 我对比 / 我实战」
  - 加具体数字 / 时间 / 对比维度(如能从 hotspot summary 抽到)
  - 标题 50 字以内

输出格式:仅 1 行新标题 · 不要任何解释 · 不要引号。

──── 例 1 ────
原:Claude Opus 4.7 发布
摘要:速度提升 30% · 支持 1M context · ...
改写:Claude Opus 4.7 真测:5 个真实任务速度比 4.6 快 30%

──── 例 2 ────
原:Cursor 估值 100 亿背后
摘要:融资 $200M · ...
改写:Cursor 我用了 30 天 · 比 Copilot 强在哪 5 件事

──── 例 3 ────
原:Gemini 3 Pro 重磅上线
摘要:多模态 + 视频理解 + ...
改写:我用 Gemini 3 Pro 跑了 5 个视频任务 · 这 2 个真改变了工作流

现在改写下面这条:
原:{title}
摘要:{summary}

新标题:"""


def llm_rewrite(title: str, summary: str = "") -> str | None:
    """调 cpa.gateway(L4_short)· 把 hotspot 标题改写成干货 idea · 失败返回 None。

    走 lib/llm_service.generate_text · 统一接 cpa.gateway · 自动 fallback 池。
    L4_short = 短文本改写 · 一般走 glm-api(便宜)兜 poe-api。
    """
    summary_clip = (summary or "").strip()[:500]
    prompt = REWRITE_PROMPT.format(title=title, summary=summary_clip)
    try:
        text = llm_service.generate_text(
            prompt=prompt,
            system=None,  # REWRITE_PROMPT 已含全部 instruction
            kind="L4_short",
        )
    except Exception as e:
        print(f"⚠ LLM 改写失败: {e}", file=sys.stderr)
        return None
    text = (text or "").strip()
    if not text:
        return None
    # 抽第 1 行 · 去引号
    line = text.splitlines()[0].strip().strip('"').strip("'").strip("「").strip("」")
    if not line or len(line) > 80:
        return None
    return line


def _today_count_in_bank() -> int:
    """idea_bank 今天 source=hotspot 的条目数 · 防超过 DAILY_CAP。"""
    today = date.today().isoformat()
    model = _idea_bank.load()
    n = 0
    for i in model.get("ideas", []):
        if i.get("source") != "hotspot":
            continue
        ts = (i.get("created_at") or i.get("added_at") or "")
        if isinstance(ts, str) and ts[:10] == today:
            n += 1
    return n


def _mark_seen(item: dict) -> None:
    """调 news_hub reader.py --mark-seen wewrite 给单条 id 标记已看过。

    这是兜底 · 真实 mark_seen 在 reader.py 内部完成 · 这里只是显式触发。
    """
    if nhub is None or not nhub.NEWS_HUB_READER.exists():
        return
    try:
        subprocess.run(
            [str(nhub.NEWS_HUB_PY), str(nhub.NEWS_HUB_READER),
             "--platform", "wewrite", "--mark-seen", item.get("id", "")],
            capture_output=True, text=True, timeout=10,
            cwd=str(nhub.NEWS_HUB_DIR),
        )
    except Exception:
        pass


def process_hotspots(limit: int = PER_RUN_LIMIT, *, dry_run: bool = False) -> dict:
    """主流程 · 返回 stats {fetched, rewritten, added, skipped_guard, skipped_dup}。"""
    if nhub is None:
        return {"error": "news_hub_reader missing"}

    today_n = _today_count_in_bank()
    if today_n >= DAILY_CAP:
        print(f"⚠ 今日已入 {today_n} 条 hotspot · 达单日上限 {DAILY_CAP} · skip")
        return {"capped": True, "today_count": today_n}

    items = nhub.read_news(limit=limit * 3, since_hours=72)
    if not items:
        return {"fetched": 0, "added": 0, "note": "news_hub returned []"}

    stats = {"fetched": len(items), "rewritten": 0, "added": 0,
             "skipped_guard": 0, "skipped_dup": 0, "skipped_cap": 0}

    for it in items[:limit * 3]:  # 多拉一些 · 避免守门拒后没东西
        if stats["added"] >= limit:
            break
        if today_n + stats["added"] >= DAILY_CAP:
            stats["skipped_cap"] += 1
            break

        title_raw = (it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        if not title_raw:
            continue

        # 第一道守门:本来就是 AI 干货形态 → 直接入(不浪费 LLM)
        if is_ai_topic(title_raw, summary):
            new_title = title_raw
        else:
            # 第二道:LLM 改写 · 改完再过守门
            print(f"  ↻ rewrite: {title_raw[:50]}")
            new_title = llm_rewrite(title_raw, summary) if not dry_run else f"[mock-rewrite] {title_raw[:30]}"
            stats["rewritten"] += 1
            if not new_title:
                stats["skipped_guard"] += 1
                continue
            if not is_ai_topic(new_title, summary):
                rsn = reject_reason(new_title, summary)
                print(f"  ✗ rewrite 后仍不过守门: {rsn} · {new_title[:50]}")
                stats["skipped_guard"] += 1
                continue

        notes = (
            f"from news_hub · {it.get('source','?')}\n"
            f"orig title: {title_raw}\n"
            f"url: {it.get('url','')}\n"
            f"summary: {summary[:300]}\n"
            f"hub_id: {it.get('id','')}"
        )

        if dry_run:
            print(f"  [dry] would add: {new_title}")
            stats["added"] += 1
            continue

        try:
            rec = _idea_bank.add(
                title=new_title,
                category="hotspot_substance",
                source="hotspot",
                priority=int(it.get("wx_score", 50)),
                tags=["hotspot", "ai-news-hub"],
                notes=notes,
            )
            print(f"  ✓ #{rec['id']} {new_title[:50]}")
            stats["added"] += 1
            _mark_seen(it)
        except Exception as e:
            print(f"  ✗ idea_bank.add 失败: {e}")
            stats["skipped_dup"] += 1

    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=PER_RUN_LIMIT,
                    help="单次最多入库的干货 idea 数(默认 5)")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印 · 不入库 / 不调 LLM(mock 改写)")
    args = ap.parse_args()

    print(f"=== hotspot_to_idea · limit={args.limit} · dry={args.dry_run} ===")
    stats = process_hotspots(limit=args.limit, dry_run=args.dry_run)
    print()
    print("=== stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
