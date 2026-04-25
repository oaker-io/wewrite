#!/usr/bin/env python3
"""sync_from_xhs.py · 从 xhswrite 事件总线拉「小红书发布完成」事件 · 入 wewrite idea_bank。

为什么:
    用户在 xhswrite(/Users/mahaochen/xhswrite/)发了 1 篇小红书图文笔记 ·
    希望同主题在 wewrite 这边也起一篇微信公众号短文 · 形成跨平台覆盖。

最小桥(P1):
    - 不复用 xhs 文字(平台风格不一样 · 标题党 vs 工程派 · 改写比抄省事)
    - 不复用 xhs 图(3:4 竖图 vs 公众号 1:1 thumb · 比例不对)
    - **只复用主题(title)**:作为 idea 入 wewrite idea_bank · auto_pick 下次能选 ·
      然后 wewrite 自己的 write.py 用 wewrite 风格重写 · 自己的 images.py 生 1:1 thumb

G7 v2 升级 · 加 --payload 分支(2026-04-26):
    xhswrite/publish.py 现在会 fire 一个 tmp.json 含 image_plan 全文 + size_preset。
    此脚本读到 --payload <tmp.json> 时:
      1. 仍把主题入 idea_bank(idea 不变)
      2. **额外**:用 image_plan 渲染一张 wechat-cover 2.35:1 PNG 头图
         (调 wewrite/scripts/workflow/images_card.py · engine=html · 0 钱)
      3. 出图到 wewrite/output/sync-card/ · 推 1 张图给 Discord

数据源:
    /Users/mahaochen/xhswrite/bus/events.jsonl 每行一条 JSON event
    或:--payload <file.json> 单事件直传(G7 v2 · 含 image_plan)

去重:
    output/xhs_sync_state.yaml 记 last_processed_ts · 只处理 ts > last 的 event
    --payload 模式不去重(每次 publish 都跑)

跑法:
    venv/bin/python3 scripts/sync_from_xhs.py                  # 默认 · 拉 events.jsonl
    venv/bin/python3 scripts/sync_from_xhs.py --dry-run        # 不写 idea_bank · 只看
    venv/bin/python3 scripts/sync_from_xhs.py --no-push        # 不 push Discord
    venv/bin/python3 scripts/sync_from_xhs.py --payload tmp.json  # G7 v2 单事件 + image_plan
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import _idea_bank  # noqa: E402

XHS_EVENTS = Path("/Users/mahaochen/xhswrite/bus/events.jsonl")
SYNC_STATE = ROOT / "output" / "xhs_sync_state.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

# G7 v2 · sync 头图渲染脚本 + 输出目录
IMAGES_CARD = ROOT / "scripts" / "workflow" / "images_card.py"
SYNC_CARD_DIR = ROOT / "output" / "sync-card"

_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def load_sync_state() -> dict:
    if not SYNC_STATE.exists():
        return {"last_processed_ts": None, "synced_count": 0}
    return yaml.safe_load(SYNC_STATE.read_text(encoding="utf-8")) or {}


def save_sync_state(state: dict) -> None:
    SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def read_xhs_events() -> list[dict]:
    """读 xhswrite events.jsonl · 返回所有 event(每行一条 JSON)。"""
    if not XHS_EVENTS.exists():
        return []
    out = []
    for line in XHS_EVENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def find_new_publish_events(events: list[dict], last_ts: str | None) -> list[dict]:
    """筛 agent=publish kind=done 且 ts > last_ts 的 event。"""
    out = []
    for e in events:
        if e.get("agent") != "publish" or e.get("kind") != "done":
            continue
        if not e.get("title"):  # 没标题的跳过(发布失败兜底)
            continue
        ts = e.get("ts", "")
        if last_ts and ts <= last_ts:
            continue
        out.append(e)
    return out


def add_to_idea_bank(event: dict) -> int | None:
    """xhs publish event → idea_bank · 标 source=xhs · category=flexible。"""
    title = (event.get("title") or "").strip()
    if not title:
        return None
    notes = (
        f"from xhswrite · {event.get('ts', '?')[:19]}\n"
        f"images: {event.get('images', 0)} 张\n"
        f"url: {event.get('url') or '(xhs internal · MCP 没回 url)'}"
    )
    try:
        rec = _idea_bank.add(
            title=title,
            category="flexible",
            source="xhs",
            priority=80,
            tags=["xhs", "跨平台"],
            notes=notes,
        )
        return rec["id"]
    except Exception as e:
        print(f"  ✗ idea_bank add fail: {e}", file=sys.stderr)
        return None


def push_discord(text: str, *, image_path: str | None = None) -> None:
    try:
        cmd = [str(PY), str(PUSH), "--text", text]
        if image_path:
            cmd += ["--image", image_path]
        subprocess.run(cmd, timeout=60, check=False)
    except Exception:
        pass


# --- G7 v2 · payload 模式辅助 -------------------------------------------------

def _slugify(text: str, max_len: int = 40) -> str:
    """中文 OK · 去掉文件名敏感字符 · 保留 cn/en 字符。"""
    import re as _re
    s = (text or "").strip()
    s = _re.sub(r"\s+", "-", s)
    s = _re.sub(r"[^\w一-鿿A-Za-z0-9\-]", "", s)
    return s[:max_len] or "sync"


def _build_html_spec_from_image_plan(
    *, title: str, image_plan: dict, theme: str = "xhs-insight-news",
) -> dict:
    """从 xhswrite 的 image_plan.yaml(cover/img-1.. 顺序映射) 拼出 wewrite-cover spec。

    只取 cover 部分(头图 1 张就够) · 走 xhs-card 的 cover 模板。
    """
    cover = (image_plan or {}).get("cover") or {}
    headline = (cover.get("headline") or title or "公众号头条")[:18]
    subtitle = cover.get("subtitle") or ""
    data_points = cover.get("data_points") or []

    # 把 data_points 转成 hero_stats(cover.html 模板预期 v/l 对)
    hero_stats: list[dict] = []
    for dp in data_points[:3]:
        s = str(dp).strip()
        if not s:
            continue
        # "100+ 装满" → v=100+ l=装满
        parts = s.split(maxsplit=1)
        if len(parts) == 2:
            hero_stats.append({"v": parts[0][:6], "l": parts[1][:8]})
        else:
            hero_stats.append({"v": s[:6], "l": ""})

    return {
        "slug": f"sync-{_slugify(title)}",
        "engine": "html",
        "platform": "gzh",
        "theme": theme,
        "size_preset": "wechat-cover",   # ★ pipeline.py 读这个
        "author": "@wewrite",
        "pages": [
            {
                "template": "cover",
                "fields": {
                    "tag": "公众号头条",
                    "title_main": headline,
                    "title_sub": subtitle[:24],
                    "anchor_glyph": "★",
                    "kicker": "WEWRITE × XHS",
                    "hero_stats": hero_stats,
                },
            }
        ],
    }


def render_sync_cover(payload: dict, *, dry_run: bool = False) -> Path | None:
    """payload 含 image_plan + title · 渲一张 wechat-cover PNG 到 SYNC_CARD_DIR/。

    实现:
      - 走 xhs-card pipeline.py · engine=html · 0 钱
      - 我们有两种调用方式:1) 直接 spawn pipeline.py 2) 经由 wewrite/images_card.py
        当前选 1)更稳:images_card.py 默认从 article_md 抽 title · 不读 image_plan。
        直接调 xhs-card pipeline 把 image_plan 字段映射进 spec.json 即可。

    返回:出图绝对路径(成功)· None(失败 / dry-run / 缺 image_plan)
    """
    image_plan = payload.get("image_plan") or {}
    title = (payload.get("title") or "").strip()
    if not image_plan or not title:
        print("  · 无 image_plan / 无 title · 跳过 sync 头图", file=sys.stderr)
        return None

    # 如果 wewrite images_card.py 都不存在 · 说明 W2 还没建 · 静默跳
    if not IMAGES_CARD.exists():
        print(f"  · {IMAGES_CARD} 不存在 · 跳过 sync 头图(W2 未建)", file=sys.stderr)
        return None

    # 找 xhs-card pipeline.py(优先 wewrite/.claude · 后备 xhswrite/.claude)
    candidates = [
        ROOT / ".claude" / "skills" / "xhs-card" / "pipeline.py",
        Path("/Users/mahaochen/xhswrite/.claude/skills/xhs-card/pipeline.py"),
    ]
    pipeline = next((p for p in candidates if p.exists()), None)
    if not pipeline:
        print("  · xhs-card pipeline.py 找不到 · 跳过 sync 头图", file=sys.stderr)
        return None

    spec = _build_html_spec_from_image_plan(title=title, image_plan=image_plan)
    SYNC_CARD_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = SYNC_CARD_DIR / f"{spec['slug']}-spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"  → spec={spec_path.name} · theme={spec['theme']} · "
        f"size_preset=wechat-cover · dry_run={dry_run}"
    )
    if dry_run:
        return None

    cmd = [
        str(PY), str(pipeline), str(spec_path),
        "--output", str(SYNC_CARD_DIR),
        "--size-preset", "wechat-cover",
    ]
    try:
        proc = subprocess.run(cmd, timeout=180, check=False,
                              capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"  ✗ pipeline 失败 rc={proc.returncode}\n{proc.stderr[:400]}",
                  file=sys.stderr)
            return None
    except Exception as e:
        print(f"  ✗ pipeline spawn 失败: {e}", file=sys.stderr)
        return None

    # cover 文件名约定:01-cover-wechat-cover.png(pipeline 加了 size suffix)
    out_png = SYNC_CARD_DIR / "01-cover-wechat-cover.png"
    if not out_png.exists():
        # fallback · 取目录里第一张 PNG
        pngs = sorted(SYNC_CARD_DIR.glob("01-*wechat-cover*.png"))
        out_png = pngs[0] if pngs else None
    return out_png


def handle_payload(payload_path: Path, *, dry_run: bool, no_push: bool) -> int:
    """G7 v2 · 单事件 payload 模式:idea_bank + 渲 wechat-cover PNG + push。"""
    if not payload_path.exists():
        print(f"❌ payload 文件不存在: {payload_path}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ payload 解析失败: {e}", file=sys.stderr)
        return 1

    title = (payload.get("title") or "").strip()
    if not title:
        print("❌ payload 缺 title", file=sys.stderr)
        return 1

    print(f"→ payload mode · title={title[:50]}")

    # 1. idea_bank(沿用旧 add_to_idea_bank · 但把 payload 当 event 用)
    fake_event = {
        "title": title,
        "ts": payload.get("source_ts") or _now_iso(),
        "url": payload.get("feed_url") or "",
        "images": 1 if payload.get("image_plan") else 0,
    }
    idea_id: int | None = None
    if not dry_run:
        idea_id = add_to_idea_bank(fake_event)
        print(f"  ✓ idea_bank · id={idea_id}")
    else:
        print("  · dry-run · 不写 idea_bank")

    # 2. 渲头图(wechat-cover 2.35:1 · 0 钱 HTML)
    png_path = render_sync_cover(payload, dry_run=dry_run)

    # 3. Discord push
    if not no_push:
        lines = [
            "🔗 **xhs → wewrite 同步(v2)**",
            f"主题: {title[:50]}",
        ]
        if idea_id is not None:
            lines.append(f"idea_bank: #{idea_id}")
        if png_path and png_path.exists():
            lines.append(f"封面: {png_path.name} · 2350×1000 @2x")
            lines.append("→ 公众号头条头图已生成 · 待人审")
            push_discord("\n".join(lines), image_path=str(png_path))
        else:
            lines.append("封面: 跳过(无 image_plan / dry-run)")
            push_discord("\n".join(lines))

    return 0


# --- 旧 events.jsonl 模式(P1) -----------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="拉 xhswrite 发布事件 · 入 wewrite idea_bank")
    p.add_argument("--dry-run", action="store_true", help="不写 idea_bank · 只打印")
    p.add_argument("--no-push", action="store_true", help="不 push Discord")
    p.add_argument("--reset", action="store_true",
                   help="重置 last_processed_ts · 重跑全部历史(慎)")
    p.add_argument("--payload", default=None,
                   help="G7 v2 · 单事件 JSON(含 image_plan)· 由 xhswrite publish.py fire")
    args = p.parse_args()

    # G7 v2 · payload 模式 · 走单事件 + 头图渲染
    if args.payload:
        return handle_payload(
            Path(args.payload).expanduser().resolve(),
            dry_run=args.dry_run,
            no_push=args.no_push,
        )

    if not XHS_EVENTS.exists():
        print(f"❌ {XHS_EVENTS} 不存在 · xhswrite 还没产生事件?", file=sys.stderr)
        return 0  # 不报错(xhswrite 可能还没装)

    state = load_sync_state()
    if args.reset:
        state["last_processed_ts"] = None
        print("⚠ 重置 last_processed_ts · 全部历史重跑")

    last_ts = state.get("last_processed_ts")
    events = read_xhs_events()
    new_events = find_new_publish_events(events, last_ts)

    print(f"→ xhswrite events: 总 {len(events)} 条 · 新 publish done {len(new_events)} 条")

    if not new_events:
        print(f"  · 无新发布 · 上次处理到 ts={last_ts or '从未'}")
        return 0

    added_ids: list[int] = []
    for e in new_events:
        ts = e.get("ts", "?")
        title = e.get("title", "")[:50]
        print(f"  + [{ts[:19]}] {title}")
        if not args.dry_run:
            idea_id = add_to_idea_bank(e)
            if idea_id is not None:
                added_ids.append(idea_id)

    # 更新 state · last_ts = 最新 event 的 ts
    if new_events and not args.dry_run:
        state["last_processed_ts"] = new_events[-1]["ts"]
        state["synced_count"] = state.get("synced_count", 0) + len(added_ids)
        state["last_synced_at"] = _now_iso()
        save_sync_state(state)

    print(f"\n✓ 新入 wewrite idea_bank · {len(added_ids)} 条 · idea_id={added_ids}")

    # Discord 报告
    if not args.no_push and added_ids:
        lines = [
            f"🔗 **xhs → wewrite 同步** · {len(added_ids)} 条新 idea",
            "",
        ]
        for e, idea_id in zip(new_events, added_ids):
            lines.append(f"  [#{idea_id}] {(e.get('title') or '')[:50]}")
        lines.append("")
        lines.append("→ 明早 07:00 auto_pick 选题时 · 这些 xhs 主题进候选(weight=80)")
        lines.append("→ wewrite 用自己风格重写短文 · 不复用 xhs 文字 / 图")
        push_discord("\n".join(lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
