#!/usr/bin/env python3
"""sync_from_xhs_image.py · 把 xhswrite 发的小红书图文 · 直接转成微信公众号 image_post 草稿。

为啥跟 sync_from_xhs.py 分开:
  - sync_from_xhs.py:只把 xhs 发布主题入 wewrite idea_bank · auto_pick 后续用
  - sync_from_xhs_image.py:直接把 xhs 6 张 3:4 图复用 · 推 wewrite image_post 草稿
    (微信公众号「图片消息」横划轮播 · 跟小红书图文卡视觉一致)

为啥不进 12:00 主链 bundle:
  - WeChat bundle 限定 article_type=news · image_post 是 newspic · type 互斥
  - 所以 image_post 单独走草稿 · 不消耗主链群发配额
  - 用户决定哪天用 image_post 替代 article 群发(订阅号每日 1 次 · type 选其一)

数据流:
  1. xhswrite/scripts/workflow/publish.py 发完 fire 这个 sync(已配 fire-and-forget)
  2. 读 ~/xhswrite/bus/events.jsonl 找 publish kind=done 含 images 字段的 event
  3. 对每张 image upload_thumb → media_id
  4. publisher.create_image_post(title, image_media_ids, content) → 草稿 media_id
  5. push Discord「📸 image_post 草稿就绪」+ 提示用户哪天用它替代 article 群发
  6. 落 output/xhs_image_sync_state.yaml 防重复处理

跑法:
  venv/bin/python3 scripts/sync_from_xhs_image.py
  venv/bin/python3 scripts/sync_from_xhs_image.py --dry-run
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
sys.path.insert(0, str(ROOT / "toolkit"))
from publisher import create_image_post  # noqa: E402
from wechat_api import get_access_token, upload_thumb  # noqa: E402

XHS_EVENTS = Path("/Users/mahaochen/xhswrite/bus/events.jsonl")
SYNC_STATE = ROOT / "output" / "xhs_image_sync_state.yaml"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

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


def find_new_image_events(events: list[dict], last_ts: str | None) -> list[dict]:
    """筛 publish done + 含 images 列表 + ts > last_ts 的 event。"""
    out = []
    for e in events:
        if e.get("agent") != "publish" or e.get("kind") != "done":
            continue
        if not e.get("title") or not e.get("images"):
            continue
        ts = e.get("ts", "")
        if last_ts and ts <= last_ts:
            continue
        out.append(e)
    return out


def push_discord(text: str) -> None:
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", text],
            timeout=30, check=False,
        )
    except Exception:
        pass


def _load_token() -> str:
    """读 secrets/keys.env 拿 WECHAT_APPID / WECHAT_APPSECRET。"""
    keys = ROOT / "secrets" / "keys.env"
    appid = appsecret = ""
    if keys.exists():
        for line in keys.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("WECHAT_APPID="):
                appid = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("WECHAT_APPSECRET="):
                appsecret = line.split("=", 1)[1].strip().strip('"')
    if not (appid and appsecret):
        raise RuntimeError("缺 WECHAT_APPID / WECHAT_APPSECRET · 看 secrets/keys.env")
    return get_access_token(appid, appsecret)


def sync_one(event: dict, *, dry_run: bool = False) -> str | None:
    """把 1 个 xhs publish event 转成 wewrite image_post 草稿 · 返回 media_id 或 None。"""
    title = (event.get("title") or "").strip()[:32]  # WeChat image_post title ≤ 32
    content = (event.get("content") or "").strip()[:1000]
    images = event.get("images") or []
    images = [p for p in images if Path(p).exists()][:20]  # WeChat 限 20 张

    if not title or not images:
        print(f"  ⚠ skip: title 或 images 缺 · {event.get('ts', '?')}")
        return None

    print(f"  title({len(title)}字): {title}")
    print(f"  images({len(images)}): {[Path(p).name for p in images]}")

    if dry_run:
        return "DRYRUN"

    token = _load_token()
    image_media_ids = []
    for i, p in enumerate(images, 1):
        print(f"    [{i}/{len(images)}] uploading {Path(p).name} ...")
        try:
            mid = upload_thumb(token, p)
            image_media_ids.append(mid)
        except Exception as e:
            print(f"      ✗ {e}")
            continue

    if not image_media_ids:
        print("  ✗ 没有图能 upload · 跳过")
        return None

    result = create_image_post(
        access_token=token,
        title=title,
        image_media_ids=image_media_ids,
        content=content,
        open_comment=True,
        fans_only_comment=False,
    )
    return result.media_id


def main() -> int:
    p = argparse.ArgumentParser(description="xhs 图文 → wewrite image_post 草稿")
    p.add_argument("--dry-run", action="store_true", help="不真推草稿 · 只打印")
    p.add_argument("--no-push", action="store_true", help="不 push Discord")
    p.add_argument("--reset", action="store_true", help="重置 last_ts · 重跑全部")
    args = p.parse_args()

    if not XHS_EVENTS.exists():
        print(f"❌ {XHS_EVENTS} 不存在", file=sys.stderr)
        return 0

    state = load_sync_state()
    if args.reset:
        state["last_processed_ts"] = None

    last_ts = state.get("last_processed_ts")
    events = read_xhs_events()
    new_events = find_new_image_events(events, last_ts)

    print(f"→ xhs events: 总 {len(events)} 条 · 新 image-post candidates {len(new_events)} 条")

    if not new_events:
        print(f"  · 无新 image post · 上次处理 ts={last_ts or '从未'}")
        return 0

    posted: list[tuple[str, str]] = []  # (title, media_id)
    failed: list[tuple[str, str]] = []

    for e in new_events:
        ts = e.get("ts", "?")
        title = (e.get("title") or "")[:50]
        print(f"\n[{ts[:19]}] {title}")
        try:
            media_id = sync_one(e, dry_run=args.dry_run)
            if media_id:
                posted.append((title, media_id))
                print(f"  ✓ image_post 草稿 media_id={media_id[:30]}")
        except Exception as ex:
            failed.append((title, str(ex)))
            print(f"  ✗ {ex}", file=sys.stderr)

    if not args.dry_run and new_events:
        state["last_processed_ts"] = new_events[-1]["ts"]
        state["synced_count"] = state.get("synced_count", 0) + len(posted)
        state["last_synced_at"] = _now_iso()
        save_sync_state(state)

    print(f"\n=== xhs image-post 同步总结 ===")
    print(f"  新草稿: {len(posted)}")
    print(f"  失败: {len(failed)}")

    if not args.no_push and posted:
        lines = [
            f"📸 **xhs 图文 → wewrite image_post 草稿** · {len(posted)} 篇",
            "",
        ]
        for title, mid in posted:
            lines.append(f"  · {title} · `{mid[:24]}...`")
        lines += [
            "",
            "💡 提示:image_post 是横划轮播图 · 跟小红书视觉一致 ·",
            "WeChat 订阅号每日 1 次群发 · 你今天可选 article bundle 或 image_post · 二选一。",
            "草稿箱可以保留 · 你想哪天发就哪天发。",
        ]
        push_discord("\n".join(lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
