#!/usr/bin/env python3
"""
WeWrite · Discord 主动推送 CLI

用 bot token 给预设用户发 DM 或在指定 channel @mention。脚本本身是一次性的
(不常驻),所以不需要 discord.py — 直接调 Discord REST API,无外部依赖。

为什么要独立脚本而不是复用 bot.py:
- bot.py 是 launchd 常驻进程,监听入站
- push.py 是被 routine / hook / shell 任意时候调起的出站推送
- 两者都用同一个 DISCORD_BOT_TOKEN,但职责分离

用法:
    python3 discord-bot/push.py --text "早上好,今日选题就绪"
    python3 discord-bot/push.py --text "封面生成了" --image output/images/cover.png
    python3 discord-bot/push.py --text "5 张图完成" \\
        --image output/images/cover.png --image output/images/chart-1.png
    python3 discord-bot/push.py --text "..." --to channel    # 强制 channel 不走 DM

环境变量:
    DISCORD_BOT_TOKEN   必填  (secrets/keys.env 或 launchctl getenv)
    ALLOWED_USER_IDS    必填,取第一个作为默认接收者
    DISCORD_CHANNEL_ID  可选,指定 channel 而不是自动用第一个 text channel

退出码:
    0  推送成功
    1  配置缺失(token / user_id)
    2  Discord API 失败
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

API = "https://discord.com/api/v10"


def _get_env(name):
    """优先 os.environ,fallback 到 launchctl getenv。"""
    val = os.environ.get(name)
    if val:
        return val.strip()
    try:
        r = subprocess.run(
            ["launchctl", "getenv", name],
            capture_output=True, text=True, timeout=5,
        )
        v = r.stdout.strip()
        if v:
            return v
    except Exception:
        pass
    return None


def _token():
    t = _get_env("DISCORD_BOT_TOKEN")
    if not t:
        print("❌ DISCORD_BOT_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)
    return t


def _default_user_id():
    uids = _get_env("ALLOWED_USER_IDS")
    if not uids:
        print("❌ ALLOWED_USER_IDS 未设置", file=sys.stderr)
        sys.exit(1)
    return uids.split(",")[0].strip()


def _headers(token):
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def open_dm(token, user_id):
    """尝试开 DM · 成功返回 channel_id · 失败(隐私)返回 None"""
    r = requests.post(
        f"{API}/users/@me/channels",
        headers=_headers(token),
        json={"recipient_id": user_id},
        timeout=15,
    )
    return r.json()["id"] if r.status_code == 200 else None


def find_default_channel(token):
    override = _get_env("DISCORD_CHANNEL_ID")
    if override:
        return override
    r = requests.get(f"{API}/users/@me/guilds", headers=_headers(token), timeout=15)
    guilds = r.json() if r.status_code == 200 else []
    for g in guilds:
        gr = requests.get(
            f"{API}/guilds/{g['id']}/channels",
            headers=_headers(token),
            timeout=15,
        )
        if gr.status_code != 200:
            continue
        for c in gr.json():
            if c.get("type") == 0:
                return c["id"]
    return None


def send_message(token, channel_id, content, image_paths, mention_user_id=None):
    if mention_user_id:
        content = f"<@{mention_user_id}>\n{content}"
    if len(content) > 1900:
        content = content[:1897] + "..."

    payload = {
        "content": content,
        "allowed_mentions": {
            "users": [mention_user_id] if mention_user_id else [],
        },
    }

    if not image_paths:
        r = requests.post(
            f"{API}/channels/{channel_id}/messages",
            headers=_headers(token),
            json=payload,
            timeout=30,
        )
    else:
        files = []
        for i, p in enumerate(image_paths):
            if not p.exists():
                print(f"⚠️  image not found: {p}", file=sys.stderr)
                continue
            files.append((f"files[{i}]", (p.name, open(p, "rb"), "image/png")))
        data = {"payload_json": json.dumps(payload)}
        hdrs = {"Authorization": f"Bot {token}"}
        r = requests.post(
            f"{API}/channels/{channel_id}/messages",
            headers=hdrs,
            data=data,
            files=files,
            timeout=120,
        )
    if r.status_code not in (200, 201):
        print(f"❌ Discord API {r.status_code}: {r.text[:300]}", file=sys.stderr)
        sys.exit(2)
    return r.json()


def main():
    ap = argparse.ArgumentParser(description="WeWrite Discord outbound push")
    ap.add_argument("--text", required=True, help="消息正文")
    ap.add_argument("--image", action="append", default=[], help="图片路径(可重复,≤10 张)")
    ap.add_argument(
        "--to", choices=["dm", "channel", "auto"], default="auto",
        help="auto(默认:先 DM 失败回 channel)· dm · channel",
    )
    ap.add_argument("--user-id", default=None)
    ap.add_argument("--channel-id", default=None)
    args = ap.parse_args()

    token = _token()
    user_id = args.user_id or _default_user_id()
    image_paths = [Path(p) for p in args.image][:10]

    target_channel = None
    mention_user = None

    if args.to in ("dm", "auto"):
        dm_id = open_dm(token, user_id)
        if dm_id:
            target_channel = dm_id
        elif args.to == "dm":
            print("❌ DM 开不成功(隐私设置)", file=sys.stderr)
            sys.exit(2)

    if target_channel is None:
        target_channel = args.channel_id or find_default_channel(token)
        if not target_channel:
            print("❌ 找不到可用 channel", file=sys.stderr)
            sys.exit(2)
        mention_user = user_id

    msg = send_message(token, target_channel, args.text, image_paths, mention_user)
    print(
        f"✓ pushed · message_id={msg['id']} · channel={target_channel} "
        f"· images={len(image_paths)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
