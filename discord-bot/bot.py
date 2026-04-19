"""
WeWrite · Discord bot · 桥接 Claude Code CLI

用户在 Discord 里 @bot 或用命令,bot 把消息转给 `claude -p ...`,
把 Claude 的回复分段发回 Discord(单条消息 ≤2000 字符)。

典型用法:
  @WeWrite 今日热点
  @WeWrite /wewrite 写一篇关于 AI Coding 的文章
  @WeWrite 用 md2wx 重新排版最近那篇

环境变量:
  DISCORD_BOT_TOKEN   (必填) Discord Developer Portal → Bot → Token
  WEWRITE_DIR         (可选) WeWrite 仓库路径,默认本脚本的上一级
  CLAUDE_BIN          (可选) claude CLI 路径,默认 "claude"
  ALLOWED_USER_IDS    (可选) 逗号分隔的 Discord user ID 白名单,未设则允许所有
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import discord
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN 未设置", file=sys.stderr)
    sys.exit(1)

WEWRITE_DIR = Path(os.environ.get(
    "WEWRITE_DIR",
    Path(__file__).resolve().parent.parent,
))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

_allowed = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED = {int(x) for x in _allowed.split(",") if x.strip().isdigit()}

MAX_DISCORD_MSG = 1900  # Discord hard limit is 2000; leave buffer for ``` fences

intents = discord.Intents.default()
intents.message_content = True  # Needs "Message Content Intent" enabled in Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)


def _chunk(text: str, size: int = MAX_DISCORD_MSG) -> list[str]:
    """Split text into Discord-safe chunks, prefer newline boundaries."""
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        # Find last newline within size
        split = text.rfind("\n", 0, size)
        if split == -1 or split < size // 2:
            split = size
        chunks.append(text[:split])
        text = text[split:].lstrip("\n")
    return chunks


async def _run_claude(prompt: str, status_msg: discord.Message) -> str:
    """Run `claude -p PROMPT` in non-interactive mode, return combined stdout."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN,
        "-p",
        "--output-format", "text",
        "--permission-mode", "bypassPermissions",  # ACL already restricts to owner;
                                                    # non-interactive mode needs this to run tools
        prompt,
        cwd=str(WEWRITE_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Live-update "still thinking" every 30s
    async def tick():
        i = 0
        while True:
            await asyncio.sleep(30)
            i += 1
            try:
                await status_msg.edit(content=f"🤔 Claude 思考中... (已等 {i*30}s,请耐心)")
            except discord.HTTPException:
                pass
    ticker = asyncio.create_task(tick())
    try:
        stdout, stderr = await proc.communicate()
    finally:
        ticker.cancel()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"claude exited {proc.returncode}:\n{err}")
    return stdout.decode("utf-8", errors="replace")


import time


def _now():
    return time.strftime("%H:%M:%S")


@bot.event
async def on_ready():
    print(f"[{_now()}] ✅ Logged in as {bot.user} (id={bot.user.id})")
    print(f"   WEWRITE_DIR = {WEWRITE_DIR}")
    print(f"   CLAUDE_BIN  = {CLAUDE_BIN}")
    print(f"   ALLOWED     = {ALLOWED or '(all users)'}")


@bot.event
async def on_connect():
    # Fires once when the websocket first connects (before READY)
    print(f"[{_now()}] 🔌 websocket connected")


@bot.event
async def on_disconnect():
    # Fires whenever gateway connection drops (common under proxies)
    print(f"[{_now()}] ⚠️  gateway disconnected — discord.py will auto-reconnect")


@bot.event
async def on_resumed():
    # Fires when session resumes after a disconnect (events replayed)
    print(f"[{_now()}] ✅ gateway session resumed")


@bot.event
async def on_message(message: discord.Message):
    # Ignore self
    if message.author == bot.user:
        return
    # Only respond on @mention or DM
    if bot.user not in message.mentions and not isinstance(message.channel, discord.DMChannel):
        return
    # ACL
    if ALLOWED and message.author.id not in ALLOWED:
        await message.reply("⛔ 你不在白名单里。问管理员加 ALLOWED_USER_IDS。")
        return

    # Strip @mention from message
    content = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
    if not content:
        await message.reply(
            "👋 我在。试试:\n"
            "• `@bot 今日热点`\n"
            "• `@bot /wewrite 写一篇关于 XX 的文章`\n"
            "• `@bot 用 md2wx 的 `经典-暖橙` 主题重排最近那篇`"
        )
        return

    status = await message.reply("🤔 Claude 思考中... (约 10-30s)")
    try:
        reply = await _run_claude(content, status)
    except Exception as e:
        await status.edit(content=f"❌ 失败: {e}")
        return

    chunks = _chunk(reply) if reply.strip() else ["(Claude 无回应)"]
    await status.edit(content=chunks[0])
    for extra in chunks[1:]:
        await message.channel.send(extra)


if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)
