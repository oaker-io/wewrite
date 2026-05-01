"""discover_kol.py · 每日发现 5 个 AI 博主候选 → 推 daily-report → 用户订阅 wewe-rss。

数据源(优先级排序):
  1. references/ai-kol-seed.yaml · 我维护的 AI KOL 种子库(目前 ~30)
  2. output/kol_corpus.yaml 文章正文里的 @公众号 / mp.weixin.qq.com 引用(自动发现)
  3. 已订阅 KOL 之间的相互引用(socializing)

输出:
  - output/kol_candidates.yaml · 候选清单 · 每天 append 5 个新候选
  - daily_report.py 读取这个 file · 在「学习」段展示

幂等:
  - 已 active 在 kol_list.yaml 的 → 排除
  - 已在 candidates.yaml 出现过 → 排除(不重复推)

目标:
  - 持续累积到 100 active AI KOL
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
KOL_LIST = ROOT / "config" / "kol_list.yaml"
KOL_SEED = ROOT / "references" / "ai-kol-seed.yaml"
KOL_CORPUS = ROOT / "output" / "kol_corpus.yaml"
KOL_CANDIDATES = ROOT / "output" / "kol_candidates.yaml"

DAILY_TARGET = 5


def _load_existing_names() -> set[str]:
    """已 active / archived 过的 KOL 名 · 不再推。"""
    if not KOL_LIST.exists():
        return set()
    try:
        data = yaml.safe_load(KOL_LIST.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return set()
    names = set()
    for k in data.get("list") or []:
        if isinstance(k, dict) and k.get("name"):
            names.add(k["name"])
    return names


def _load_candidates_history() -> dict:
    """已推过的候选 · 不重复推。"""
    if not KOL_CANDIDATES.exists():
        return {"date": "", "history": [], "queue": []}
    try:
        data = yaml.safe_load(KOL_CANDIDATES.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"date": "", "history": [], "queue": []}
    return data if isinstance(data, dict) else {"date": "", "history": [], "queue": []}


def _seed_pool() -> list[dict]:
    """读种子库 · 返回所有候选 · 带 name+theme+weight+why。"""
    if not KOL_SEED.exists():
        return []
    try:
        data = yaml.safe_load(KOL_SEED.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    return [c for c in (data.get("candidates") or []) if isinstance(c, dict) and c.get("name")]


def _corpus_mentions() -> list[str]:
    """从 KOL 已抓正文里抽 @公众号 引用 · 返回名字 list。"""
    if not KOL_CORPUS.exists():
        return []
    try:
        data = yaml.safe_load(KOL_CORPUS.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    arts = data.get("articles") or []
    found: list[str] = []
    pat = re.compile(r"@([\w一-鿿]{2,15})")  # @中英 2-15 字
    for a in arts:
        body = (a.get("content_md") or "") + " " + (a.get("summary") or "")
        for m in pat.findall(body):
            if 2 <= len(m) <= 15:
                found.append(m)
    return found


def discover_today() -> list[dict]:
    """选今日 5 个候选 · 排除已订/已推过的 · 优先种子库 · 兜底 corpus 引用。"""
    skip = _load_existing_names()
    history = _load_candidates_history()
    skip.update(history.get("history") or [])

    out: list[dict] = []

    # 优先 seed 库
    for c in _seed_pool():
        name = c["name"].split(" [")[0].strip()  # 去 [archived] 标记
        if name in skip:
            continue
        out.append({
            "name": name,
            "theme": c.get("theme", "AI 干货"),
            "weight": c.get("weight", 60),
            "why": c.get("why", ""),
            "source": "seed",
            "handle": c.get("handle"),
        })
        if len(out) >= DAILY_TARGET:
            return out

    # 兜底 corpus mentions
    from collections import Counter
    mentions = Counter(_corpus_mentions())
    for name, cnt in mentions.most_common(50):
        if name in skip or any(o["name"] == name for o in out):
            continue
        out.append({
            "name": name,
            "theme": "未知",
            "weight": 50 + min(cnt, 30),  # 引用次数转 weight
            "why": f"在已订 KOL 文章中被引用 {cnt} 次",
            "source": "corpus_mention",
            "handle": None,
        })
        if len(out) >= DAILY_TARGET:
            return out

    return out


def write_candidates(items: list[dict]) -> None:
    """append 今日候选到 output/kol_candidates.yaml · 维护 history 列表。"""
    history = _load_candidates_history()
    today = date.today().isoformat()
    queue = history.get("queue") or []
    hist = set(history.get("history") or [])

    # 把 queue 里超过 7 天没订的清掉(避免无限 push)
    queue = [q for q in queue if (q.get("pushed") or "")[:10] >= today]

    for it in items:
        if it["name"] in hist:
            continue
        queue.append({**it, "pushed": today})
        hist.add(it["name"])

    out = {
        "date": today,
        "history": sorted(hist),
        "queue": queue,
        "today": items,
    }
    KOL_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    KOL_CANDIDATES.write_text(
        yaml.dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def main() -> int:
    items = discover_today()
    if not items:
        print("⚠ 0 候选 · 种子库已耗尽 · 需要扩容种子库 / 跑 fetch_kol 累积 corpus")
        return 0
    write_candidates(items)
    print(f"✓ discover {len(items)} 个候选 · 写入 {KOL_CANDIDATES.relative_to(ROOT)}")
    for it in items:
        print(f"  · {it['name']:20s} [{it['theme']:10s} w={it['weight']}] {it['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
