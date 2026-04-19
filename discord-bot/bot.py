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


# =================================================================
# Workflow routing · natural-language → step scripts
# =================================================================

WORKFLOW_DIR = WEWRITE_DIR / "scripts" / "workflow"
VENV_PY = WEWRITE_DIR / "venv" / "bin" / "python3"
WORKFLOW_PY = str(VENV_PY) if VENV_PY.exists() else "python3"


def _get_session_state():
    """读 output/session.yaml 的 state(无 deps fallback)"""
    p = WEWRITE_DIR / "output" / "session.yaml"
    if not p.exists():
        return "idle"
    try:
        import yaml
        return (yaml.safe_load(p.read_text()) or {}).get("state", "idle")
    except Exception:
        return "idle"


def _classify_intent(text: str, state: str) -> tuple[str, dict]:
    """
    Return (action, kwargs). Actions:
      brief / write_idx / next / reset / claude_fallback
    """
    t = text.strip().lower()

    # Trigger brief
    if any(kw in t for kw in ["brief", "今日热点", "今天写", "开始", "选题", "看看有什么写"]):
        return ("brief", {})

    # Reset / pass
    if any(kw in t for kw in ["pass", "跳过", "今天不写", "reset", "重置", "放弃"]):
        return ("reset", {})

    # Number pick (only valid after brief) · 支持 1-5
    if state == "briefed":
        for i, num_kw in enumerate(["1", "2", "3", "4", "5"]):
            if t == num_kw or t == f"选{num_kw}" or t == f"第{num_kw}" or f"选 {num_kw}" in t or f"第{num_kw}个" in t:
                return ("write_idx", {"idx": i})

    # Natural "continue / next / ok"
    if any(kw in t for kw in ["ok", "好", "继续", "下一步", "next", "go", "行", "没问题", "可以"]):
        return ("next", {})

    # Unknown → fallback to generic claude -p
    return ("claude_fallback", {})


async def _run_workflow_script(script_name: str, args: list[str], status_msg):
    """Run scripts/workflow/X.py as subprocess · live-update status msg."""
    path = WORKFLOW_DIR / script_name
    if not path.exists():
        return 1, f"(脚本 {script_name} 不存在)"

    async def tick():
        i = 0
        while True:
            await asyncio.sleep(30)
            i += 1
            try:
                await status_msg.edit(
                    content=f"⏳ 跑 {script_name} 中... (已 {i*30}s,长任务可能 5-15 分钟)"
                )
            except discord.HTTPException:
                pass
    ticker = asyncio.create_task(tick())

    proc = await asyncio.create_subprocess_exec(
        WORKFLOW_PY, str(path), *args,
        cwd=str(WEWRITE_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await proc.communicate()
    finally:
        ticker.cancel()
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    return proc.returncode, (out + "\n---stderr---\n" + err)[-1200:]


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if bot.user not in message.mentions and not isinstance(message.channel, discord.DMChannel):
        return
    if ALLOWED and message.author.id not in ALLOWED:
        await message.reply("⛔ 你不在白名单里。")
        return

    content = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
    if not content:
        state = _get_session_state()
        await message.reply(
            f"👋 当前状态:**{state}** · 命令示例:\n"
            "• 「今日热点」/「开始」 → 触发选题(AI 白名单过滤)\n"
            "• 「1」~「5」 → 选 Top N(仅在 briefed 状态)\n"
            "• 「ok」/「继续」 → 下一步(根据当前状态自动路由)\n"
            "• 「pass」/「跳过」 → 放弃当前任务\n"
            "• 其他自由问题 → 回退给 Claude 回答"
        )
        return

    state = _get_session_state()
    action, kw = _classify_intent(content, state)

    # --- Action dispatch ---

    if action == "brief":
        status = await message.reply("🤔 跑 brief 拉热点 + 选 Top 3...")
        rc, out = await _run_workflow_script("brief.py", [], status)
        await status.edit(
            content=(f"✓ brief 完成,已推 Top 3 给你审" if rc == 0
                     else f"❌ brief 失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "write_idx":
        idx = kw["idx"]
        status = await message.reply(
            f"✍️ 选了 #{idx+1} · claude 开始写(3-8 分钟),写完自动 push 给你..."
        )
        rc, out = await _run_workflow_script("write.py", [str(idx)], status)
        await status.edit(
            content=(f"✓ 文章就绪,已推预览" if rc == 0
                     else f"❌ 写作失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "next":
        if state == "wrote":
            status = await message.reply("🎨 进入生图阶段(5-15 分钟)...")
            rc, out = await _run_workflow_script("images.py", [], status)
            await status.edit(
                content=(f"✓ 图片就绪,已推 5 张给你审" if rc == 0
                         else f"❌ 生图失败\n```\n{out[-600:]}\n```")
            )
        elif state == "imaged":
            status = await message.reply("🚀 推到微信草稿箱...")
            rc, out = await _run_workflow_script("publish.py", [], status)
            await status.edit(
                content=(f"✓ 推送完成,已推提示给你" if rc == 0
                         else f"❌ 发布失败\n```\n{out[-600:]}\n```")
            )
        else:
            await message.reply(
                f"🤷 当前状态 **{state}** · 没下一步可走。\n"
                f"想开新流程回复「今日热点」或「brief」。"
            )
        return

    if action == "reset":
        # Reset session and notify
        p = WEWRITE_DIR / "output" / "session.yaml"
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
        await message.reply("🧹 已清 session · 随时回「brief」重新开始。")
        return

    # Fallback: pass through to claude -p for free-form questions
    status = await message.reply("🤔 Claude 思考中...")
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
