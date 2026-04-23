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


def select_ideas(category: str, fallback: str) -> tuple[list[dict], str]:
    """从 idea_bank 选 1 主 + 1 备 · 返回 (ideas, used_category)。

    优先用 category · 不够再用 fallback · 仍不够返回 [] · 调用方处理。
    """
    primary = _idea_bank.list_ideas(category=category, only_unused=True, limit=2)
    if len(primary) >= 1:
        return primary, category

    backup = _idea_bank.list_ideas(category=fallback, only_unused=True, limit=2)
    if len(backup) >= 1:
        return backup, fallback

    # 任何 category 都没了 · 用 flexible 兜底
    any_idea = _idea_bank.list_ideas(only_unused=True, limit=2)
    if any_idea:
        return any_idea, "any"

    return [], ""


def to_topic(idea: dict, source_label: str) -> dict:
    """idea 库记录 → session.yaml 的 topic 字典(跟 brief.py 同结构)。"""
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


def _pick_companions(companions_cfg: list[dict]) -> list[dict]:
    """给每个 companion 配置 · 从 idea_bank 选 1 个未用 idea · 返回 [{topic, cfg}, ...]。

    若某个 companion 找不到合适 idea · 跳过那个位(不报错 · 让主推继续)。
    """
    out = []
    for i, c in enumerate(companions_cfg):
        cat = c.get("category", "flexible")
        fb = c.get("fallback", "flexible")
        ideas, used_cat = select_ideas(cat, fb)
        if not ideas:
            print(f"  ⚠ companion-{i+1} ({c.get('type','?')}) 无可用 idea · 跳过")
            continue
        # 取第 1 个可用 · 但要跟主推不重复(id 不等)
        topic = to_topic(ideas[0], used_cat)
        out.append({"topic": topic, "cfg": c})
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
    companions = _pick_companions(companions_cfg) if companions_cfg else []
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
    push_picked_notice(item, primary, backup, companions=companions)
    n_comp = len(companions)
    print(f"✓ session BRIEFED · 1 主 + {n_comp} 副 · 等 08:00 auto-write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
