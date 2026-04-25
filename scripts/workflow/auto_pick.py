#!/usr/bin/env python3
"""auto_pick · 全自动选题(替代用户回数字选号)。

读 config/auto-schedule.yaml 决定今天要 pick 什么 category 的 idea,
从 idea_bank 选未用 Top 1 主 + Top 1 备 · 写到 session.yaml,
进入 STATE_BRIEFED · 然后 auto-write.sh 直接消费。

设计公约:
  - 只跑一次 idea_bank query · 不调 LLM(选题逻辑写死在 yaml 里)
  - 主题不够时按 fallback category 兜底
  - idea 库完全空时 push Discord「请加 idea」· 不 raise · exit 1
  - 跟 brief.py 不冲突 · brief.py 推荐用户审 · auto_pick.py 自动决定
  - schedule 表里 weekday=今天 的项决定一切

用法:
  python3 scripts/workflow/auto_pick.py              # 用今天 weekday
  python3 scripts/workflow/auto_pick.py --weekday 2  # 强制周三(测试用)
  python3 scripts/workflow/auto_pick.py --dry-run    # 不动 session.yaml
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state  # noqa: E402
import _idea_bank  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "config" / "auto-schedule.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")


def load_config() -> dict:
    if not CONFIG.exists():
        raise FileNotFoundError(f"找不到 {CONFIG}")
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def pick_for_weekday(cfg: dict, weekday: int) -> dict:
    """返回 schedule 表里 weekday 项 · 找不到用 weekday=0 兜底。

    新版 schedule 项结构:
      {weekday, label, main: {category, fallback, style, image_style, target_words, topic_tags},
       companions: [{type, category, style, target_words, topic_tags}, ...]}
    旧版兼容:item 顶层直接有 category/style/...(无 main 嵌套)· _normalize_schedule 自动转。
    """
    sched = cfg.get("schedule") or []
    item = None
    for it in sched:
        if int(it.get("weekday", -1)) == weekday:
            item = it
            break
    if item is None and sched:
        item = sched[0]
    if item is None:
        raise ValueError("config/auto-schedule.yaml 没有任何 schedule 项")
    return _normalize_schedule(item)


def _normalize_schedule(item: dict) -> dict:
    """新旧版 schedule 项归一化 · 总是返回 {label, main: {...}, companions: [...]}.

    旧版:item 顶层 category/style/...
    新版:item.main / item.companions
    """
    if "main" in item:
        # 新版 · 直接返回(确保 companions 是 list)
        out = dict(item)
        out.setdefault("companions", [])
        return out
    # 旧版 · 包一下
    main = {
        "category": item.get("category", "flexible"),
        "fallback": item.get("fallback", "flexible"),
        "style": item.get("style", "tutorial"),
        "image_style": item.get("image_style", "infographic"),
        "target_words": item.get("target_words", [1800, 3000]),
        "topic_tags": item.get("topic_tags", ["AI 非共识"]),
    }
    return {
        "weekday": item.get("weekday"),
        "label": item.get("label", ""),
        "main": main,
        "companions": [],
    }


_FETCH_CHANGELOG = ROOT / "scripts" / "fetch_changelog.py"


def _refill_via_fetch_changelog(timeout: int = 120) -> tuple[bool, str]:
    """idea 库空时 · 调 fetch_changelog 抹道(github trending + anthropic blog/changelog)入库。

    返回 (是否成功新增 · stdout 摘要)。
    fetch_changelog 自带去重 · 多次跑不会重复入。
    """
    if not _FETCH_CHANGELOG.exists():
        return False, "fetch_changelog.py 不存在"
    try:
        r = subprocess.run(
            [str(PY), str(_FETCH_CHANGELOG), "--source", "all", "--limit", "5"],
            cwd=str(ROOT),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "fetch_changelog 超时"
    out = (r.stdout or "")[-800:]
    if r.returncode != 0:
        return False, f"fetch_changelog rc={r.returncode}\n{out}"
    # 抓 added 数(stdout 含「added=N」)
    import re as _re
    m = _re.search(r"added=(\d+)", out)
    added = int(m.group(1)) if m else 0
    return added > 0, f"added={added}\n{out[-300:]}"


def select_ideas(category: str, fallback: str, *, allow_fetch: bool = True,
                 exclude_ids: set[int] | None = None
                 ) -> tuple[list[dict], str]:
    """从 idea_bank 选 1 主 + 1 备 · 返回 (ideas, used_category)。

    优先 category · 不够 fallback · 仍不够任意 unused。
    全空时若 allow_fetch=True · 自动调 fetch_changelog 抹道入库 · 再重试一次。
    依然空才返回 ([], "")。

    exclude_ids 用于副推去重 · 跳过主推已选的 idea_id(主推=副推会让 write.py 跑同一篇 → 副推 article_md 未变)。
    """
    excl = exclude_ids or set()

    def _filter(ideas: list[dict]) -> list[dict]:
        return [i for i in ideas if i.get("id") not in excl]

    def _try() -> tuple[list[dict], str]:
        # 拉宽 limit 补偿被 exclude 掉的 · 拿 limit+len(excl) 让过滤后仍有 2 个候选
        n = 2 + len(excl)
        primary = _filter(_idea_bank.list_ideas(category=category, only_unused=True, limit=n))[:2]
        if len(primary) >= 1:
            return primary, category
        backup = _filter(_idea_bank.list_ideas(category=fallback, only_unused=True, limit=n))[:2]
        if len(backup) >= 1:
            return backup, fallback
        any_idea = _filter(_idea_bank.list_ideas(only_unused=True, limit=n))[:2]
        if any_idea:
            return any_idea, "any"
        return [], ""

    ideas, used = _try()
    if ideas:
        return ideas, used

    if not allow_fetch:
        return [], ""

    # 兜底:idea 库空 → 主动抹道一次
    print("⚠ idea 库全空 · 自动调 fetch_changelog 抹道入库...", file=sys.stderr)
    ok, summary = _refill_via_fetch_changelog()
    print(f"  fetch_changelog: {summary}", file=sys.stderr)
    if not ok:
        return [], ""

    # 重试 select(此时 allow_fetch=False 防递归)
    ideas, used = select_ideas(category, fallback, allow_fetch=False)
    if ideas:
        return ideas, used

    # 终极兜底:从 ai-news-hub 拉 release/eval 素材 · 转成 idea 形态
    print("⚠ idea 库仍空 · 尝试从 ai-news-hub 共享层拉候选...", file=sys.stderr)
    news_picks = _read_news_hub_as_ideas(2, exclude_ids=excl)
    if news_picks:
        return news_picks, "news_hub"
    return [], ""


def _read_news_hub_as_ideas(limit: int, *, exclude_ids: set | None = None) -> list[dict]:
    """Pull recent wewrite-scored news_hub items, shape them like idea_bank rows.

    Returns list of dicts with keys: id, title, category, priority, plus
    `_news_hub` payload (url, source, summary) consumed by to_topic.
    Silent on any failure.
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from news_hub_reader import read_news  # type: ignore
    except Exception:  # noqa: BLE001
        return []
    try:
        items = read_news(limit=max(limit * 2, 6), since_hours=72)
    except Exception:  # noqa: BLE001
        return []
    if not items:
        return []
    out: list[dict] = []
    for it in items:
        if len(out) >= limit:
            break
        # synthesize a stable negative id so it never collides with idea_bank rows
        try:
            iid = -(int(str(it.get("id", "0"))[:12], 16) % 9_000_000_000)
        except Exception:  # noqa: BLE001
            iid = -abs(hash(it.get("title", ""))) % 9_000_000_000
            iid = -iid if iid > 0 else iid
        if exclude_ids and iid in exclude_ids:
            continue
        out.append({
            "id": iid,
            "title": (it.get("title") or "")[:80],
            "category": "hotspot",
            "priority": float(it.get("wx_score", 0) or 0),
            "_news_hub": {
                "url": it.get("url", ""),
                "source": it.get("source", ""),
                "summary": (it.get("summary") or "")[:600],
            },
        })
    return out


def to_topic(idea: dict, source_label: str) -> dict:
    """idea 库记录 → session.yaml 的 topic 字典(跟 brief.py 同结构)。

    news_hub 来源时,from="news_hub" + 携带 url/source/summary,让 write.py
    可以注入 KOL reactions + eval reviews 上下文。
    """
    payload = idea.get("_news_hub")
    if payload:
        return {
            "title": idea.get("title", ""),
            "source": f"news_hub / {payload.get('source','?')}",
            "hot": 0,
            "score": float(idea.get("priority", 0) or 0),
            "ai_kw": "auto",
            "is_robot": False,
            "url": payload.get("url", ""),
            "from": "news_hub",
            "idea_id": idea.get("id"),
            "category": idea.get("category", "hotspot"),
            "summary": payload.get("summary", ""),
        }
    return {
        "title": idea.get("title", ""),
        "source": f"idea 库 / {source_label}",
        "hot": 0,
        "score": float(idea.get("priority", 0) or 0),
        "ai_kw": "auto",
        "is_robot": False,
        "url": "",
        "from": "idea",
        "idea_id": idea.get("id"),
        "category": idea.get("category", "flexible"),
    }


def push_discord(text: str, *, fail_silent: bool = True) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            check=True, timeout=60,
        )
    except Exception as e:
        msg = f"⚠ push Discord 失败: {e}"
        if fail_silent:
            print(msg, file=sys.stderr)
        else:
            raise


def push_picked_notice(weekday_item: dict, primary_topic: dict, backup_topic: dict | None,
                       *, companions: list[dict] | None = None) -> None:
    label = weekday_item.get("label", "")
    main_cfg = weekday_item.get("main") or weekday_item
    cat = main_cfg.get("category", "")
    style = main_cfg.get("style", "")
    img_style = main_cfg.get("image_style", "")
    msg_lines = [
        f"🤖 **auto_pick · {label}**",
        f"📂 主推 category={cat} · style={style} · image_style={img_style}",
        "",
        f"✅ **主推**:{primary_topic['title']}",
    ]
    if companions:
        msg_lines += ["", "📎 **副推**:"]
        for i, c in enumerate(companions):
            t = c["topic"]
            ctype = c["cfg"].get("type", "?")
            cstyle = c["cfg"].get("style", "shortform")
            msg_lines.append(f"  {i+1}. [{ctype}/{cstyle}] {t['title'][:50]}")
    if backup_topic:
        msg_lines += ["", f"🥈 备选(主推备份):{backup_topic['title']}"]
    n_comp = len(companions) if companions else 0
    msg_lines += [
        "",
        f"📊 总计:1 主 + {n_comp} 副 · 占 1 次群发配额",
        "",
        "📅 接下来:08:00 auto_write → 10:00 auto_images → 11:00 auto_review → 12:00 auto_publish",
    ]
    push_discord("\n".join(msg_lines))


def push_no_idea_notice(weekday_item: dict) -> None:
    label = weekday_item.get("label", "")
    cat = weekday_item.get("category", "")
    fallback = weekday_item.get("fallback", "")
    msg = (
        f"❌ **auto_pick 失败** · {label}\n"
        f"idea 库里 category={cat} 和 fallback={fallback} 都没有未用 idea。\n\n"
        f"**请补 idea**(任一方式):\n"
        f"• Discord 发 `存 idea: <主题> 教程`\n"
        f"• 或跑 `scripts/fetch_changelog.py` 抹道入库\n"
        f"• 或 `python3 scripts/workflow/idea.py add ...`\n\n"
        f"今天的自动发文 chain 已中止 · 后续 step 不会跑。"
    )
    push_discord(msg)


def _pick_companions(companions_cfg: list[dict], *, allow_fetch: bool = True,
                     exclude_ids: set[int] | None = None) -> list[dict]:
    """给每个 companion 配置 · 从 idea_bank 选 1 个未用 idea · 返回 [{topic, cfg}, ...]。

    若某个 companion 找不到合适 idea · 跳过那个位(不报错 · 让主推继续)。
    allow_fetch=False 跳过 fetch_changelog 兜底(单测用 · 避免真去抓 GitHub)。
    exclude_ids: 调用方传入主推已选的 idea_id · 副推之间也会互相去重。
    """
    excl = set(exclude_ids or set())
    out = []
    for i, c in enumerate(companions_cfg):
        cat = c.get("category", "flexible")
        fb = c.get("fallback", "flexible")
        ideas, used_cat = select_ideas(cat, fb, allow_fetch=allow_fetch, exclude_ids=excl)
        if not ideas:
            print(f"  ⚠ companion-{i+1} ({c.get('type','?')}) 无可用 idea · 跳过")
            continue
        topic = to_topic(ideas[0], used_cat)
        out.append({"topic": topic, "cfg": c})
        excl.add(ideas[0].get("id"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="auto_pick · 全自动选题")
    parser.add_argument(
        "--weekday", type=int, default=None,
        help="0=周一 ... 6=周日 · 默认用今天",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印不动 session.yaml / 不 push",
    )
    parser.add_argument(
        "--skip-companions", action="store_true",
        help="只选主推 · 不选副推(测试主流程用)",
    )
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("enabled", True):
        print("⚠ auto-schedule.yaml enabled=false · 跳过", file=sys.stderr)
        return 0
    if not (cfg.get("steps") or {}).get("pick", True):
        print("⚠ steps.pick=false · 跳过", file=sys.stderr)
        return 0

    weekday = args.weekday if args.weekday is not None else datetime.now().weekday()
    item = pick_for_weekday(cfg, weekday)
    main_cfg = item["main"]
    companions_cfg = item.get("companions", []) if not args.skip_companions else []
    print(f"→ weekday={weekday} · {item.get('label', '')}")
    print(f"  main.category={main_cfg.get('category')} · style={main_cfg.get('style')} · image_style={main_cfg.get('image_style')}")
    print(f"  companions 期望数: {len(companions_cfg)}")

    # 主推
    ideas, used_cat = select_ideas(
        main_cfg.get("category", "flexible"),
        main_cfg.get("fallback", "flexible"),
    )
    if not ideas:
        print("❌ idea 库无可用 idea · 主推失败", file=sys.stderr)
        if not args.dry_run:
            push_no_idea_notice({"label": item.get("label",""), "category": main_cfg.get("category"), "fallback": main_cfg.get("fallback")})
        return 1

    primary = to_topic(ideas[0], used_cat)
    backup = to_topic(ideas[1], used_cat) if len(ideas) > 1 else None
    print(f"  ✓ 主选: #{primary['idea_id']} {primary['title'][:60]}")

    # 副推(若 companions_cfg 非空 · 选 N 个)
    # 排除主推 + 备选已用的 idea_id · 避免副推和主推撞同一篇
    excl_main = {primary["idea_id"]}
    if backup and backup.get("idea_id") is not None:
        excl_main.add(backup["idea_id"])
    companions = _pick_companions(companions_cfg, exclude_ids=excl_main) if companions_cfg else []
    for i, c in enumerate(companions):
        t = c["topic"]
        print(f"  ✓ 副推 {i+1} ({c['cfg'].get('type','?')}): #{t['idea_id']} {t['title'][:50]}")

    if args.dry_run:
        print("(dry-run · session.yaml 未动 · Discord 未推)")
        return 0

    # 写 session · topics = [main] + [backup?] + [companions...]
    # companions 单独存 · 便于 auto-write.sh 区分
    topics = [primary] + ([backup] if backup else [])
    companion_topics = [c["topic"] for c in companions]
    companion_styles = [c["cfg"].get("style", "shortform") for c in companions]
    companion_types = [c["cfg"].get("type", "") for c in companions]
    companion_tags = [c["cfg"].get("topic_tags", []) for c in companions]

    try:
        _state.advance(
            _state.STATE_BRIEFED,
            article_date=datetime.now().strftime("%Y-%m-%d"),
            topics=topics,
            selected_idx=0,
            selected_topic=primary,
            article_md=None,
            images_dir=None,
            draft_media_id=None,
            auto_schedule={
                "weekday": weekday,
                "label": item.get("label", ""),
                "style": main_cfg.get("style", "tutorial"),
                "image_style": main_cfg.get("image_style", "infographic"),
                "target_words": main_cfg.get("target_words", [1800, 3000]),
                "topic_tags": main_cfg.get("topic_tags", ["AI 非共识"]),
                # 副推信息(auto-write / auto-images / auto-publish 读)
                "companions": companion_topics,
                "companion_styles": companion_styles,
                "companion_types": companion_types,
                "companion_tags": companion_tags,
            },
        )
    except _state.StateGuardError as e:
        cur = _state.get_state()
        push_discord(
            f"⚠ auto-pick skip · session 已在 {cur} · 不覆盖进行中的工作\n"
            f"昨/今天的文章可能还没走完 publish · 检查 Discord 历史"
        )
        print(f"⚠ {e}", file=sys.stderr)
        return 0
    push_picked_notice(item, primary, backup, companions=companions)
    n_comp = len(companions)
    print(f"✓ session BRIEFED · 1 主 + {n_comp} 副 · 等 08:00 auto-write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
