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


_IMAGE_TARGET_RE = re.compile(
    r"(cover|chart[-\s]?[1-4])",
    re.IGNORECASE,
)


def _normalize_image_target(raw: str) -> str | None:
    """'Cover' / 'CHART-3' / 'chart 3' → cover|chart-N · None if invalid."""
    if not raw:
        return None
    t = raw.strip().lower().replace("_", "-")
    t = re.sub(r"\s+", "", t)
    if t == "cover":
        return "cover"
    m = re.match(r"^chart[-‐‒–—]?([1-4])$", t)
    if m:
        return f"chart-{m.group(1)}"
    return None


def _classify_intent(text: str, state: str) -> tuple[str, dict]:
    """
    Return (action, kwargs). Actions:
      brief / custom_idea / write_idx / next / reset /
      revise / revise_image / claude_fallback
    """
    raw = text.strip()
    t = raw.lower()

    # ============================================================
    # 优先级最高:明确的流程控制(next / reset / brief / 选号 / custom_idea)
    # 这些关键词即便在 wrote/imaged 状态也要优先于 revise
    # ============================================================

    # Reset / pass
    if any(kw in t for kw in ["pass", "跳过", "今天不写", "reset", "重置", "放弃"]):
        return ("reset", {})

    # Natural "continue / next / ok" · 比 revise 优先,免得 "ok" 被当改稿指令
    # 匹配整句就是这几个确认词(避免 "可以加段 XXX" 误判)
    short_ok = {"ok", "okay", "好", "好的", "继续", "下一步", "next", "go",
                "行", "行了", "没问题", "可以", "嗯", "嗯嗯"}
    if t in short_ok:
        return ("next", {})

    # ============================================================
    # === Idea 库管理(优先级高于 tutorial_idea / custom_idea) ===
    # 让「存 idea: XX」不被「写 XX」截胡
    # ============================================================

    # idea_done · 标已用 ── 优先于 idea_save / idea_remove(精确匹配)
    m_done = re.search(r'(?:^|\b)(?:done\s*idea|标\s*idea|idea)\s+(\d+)\s*(?:用了?)?$', raw, re.IGNORECASE)
    if m_done:
        # 进一步细分:idea\s+\d+\s*用了 / 标 idea N / done idea N
        m1 = re.match(r'^idea\s+(\d+)\s*用了?\s*$', raw, re.IGNORECASE)
        m2 = re.match(r'^标\s*idea\s+(\d+)\s*$', raw, re.IGNORECASE)
        m3 = re.match(r'^done\s*idea\s+(\d+)\s*$', raw, re.IGNORECASE)
        for mm in (m1, m2, m3):
            if mm:
                return ("idea_done", {"id": int(mm.group(1))})

    # idea_remove · 删
    m_rm = re.match(r'^(?:删除|删|rm)\s*idea\s+(\d+)\s*$', raw, re.IGNORECASE)
    if m_rm:
        return ("idea_remove", {"id": int(m_rm.group(1))})

    # idea_list · 列 idea 库
    list_kw = ["我的 idea", "我的idea", "今日 idea", "今日idea", "idea 库", "idea库",
               "有什么 idea", "有什么idea", "看看 idea", "看看idea",
               "idea list", "列 idea", "列idea"]
    if any(kw in t for kw in list_kw):
        return ("idea_list", {})

    # idea_save (主) · 显式带 idea 关键词
    m_save = re.match(r'^(?:存|记|保存)\s*(?:个)?\s*idea\s*[::,,、]?\s*(.+)', raw, re.IGNORECASE)
    if m_save:
        title = m_save.group(1).strip()
        if title:
            cat = "tutorial" if any(k in title for k in ["教程", "干货", "方法论", "手把手"]) \
                else "hotspot" if any(k in title for k in ["热点", "反共识", "吐槽"]) \
                else "flexible"
            return ("idea_save", {"title": title, "category": cat})

    # idea_save (后备) · 「存/记下/记录 XXX」 + 暗示词 + 长度 ≥ 4
    m_save2 = re.match(r'^(?:存|记下|记录)\s*[::,,、]?\s*(.+?)$', raw)
    if m_save2:
        body = m_save2.group(1).strip()
        hint_kw = ["想写", "以后写", "值得写", "可以写", "要写", "得写"]
        if len(body) >= 4 and any(h in body for h in hint_kw):
            cat = "tutorial" if any(k in body for k in ["教程", "干货", "方法论", "手把手"]) \
                else "hotspot" if any(k in body for k in ["热点", "反共识", "吐槽"]) \
                else "flexible"
            return ("idea_save", {"title": body, "category": cat})

    # === 干货系列 · tutorial_idea ===
    # 触发词:教程/干货/方法论/手把手/how to/如何 + 内容
    # 优先级在 custom_idea 之前 · 避免「教程: XX」被当成普通 custom_idea 走 hotspot 系列
    m_tut = re.match(
        r'^(?:教程|干货|方法论|手把手|how\s*to|如何)\s*[::,,、]?\s*(.+)',
        raw, re.IGNORECASE,
    )
    if m_tut:
        idea = m_tut.group(1).strip()
        if len(idea) >= 3:
            return ("tutorial_idea", {"idea": idea})

    # Custom idea · "写 XXX" / "选题: XXX" / "主题: XXX" / "话题: XXX"
    # 「选题/主题/话题」+ 内容 → 用户指定具体主题(避免被下面的 brief 关键词截胡)
    m = re.match(
        r'^(?:写一篇|写篇|帮我写|来一篇|来篇|写|选题|主题|话题)\s*[::,,、]?\s*(.+)',
        raw,
    )
    if m:
        idea = m.group(1).strip()
        if len(idea) >= 3 and idea not in ("今天", "今日", "一下", "点东西"):
            return ("custom_idea", {"idea": idea})

    # Trigger brief · 主动看热搜
    # 注意:「选题」从这里**移除**,避免「选题:XXX」被错路由(已在上方 custom_idea 处理)
    if any(kw in t for kw in ["brief", "今日热点", "今天写", "开始", "看看有什么写"]):
        return ("brief", {})
    # 「选题」单独成词(无内容) · 仍触发 brief
    if t in ("选题", "选题吧", "看看选题", "今天选题", "选个题", "选题呢"):
        return ("brief", {})

    # Number pick (only valid after brief) · 支持 1-5
    if state == "briefed":
        for i, num_kw in enumerate(["1", "2", "3", "4", "5"]):
            if t == num_kw or t == f"选{num_kw}" or t == f"第{num_kw}" or f"选 {num_kw}" in t or f"第{num_kw}个" in t:
                return ("write_idx", {"idx": i})

    # ============================================================
    # state=done · republish(重新 sanitize + 推草稿箱)
    # 关键词必须含「重新」/「再」/「republish」 · 避免误触发
    # ============================================================
    if state == "done":
        rep_kw = ["重新排版", "重新发布", "重新推", "重新推送", "重发",
                  "再发一次", "再排一次", "再推一次", "重排", "republish"]
        if any(kw in raw for kw in rep_kw):
            return ("republish", {})

    # ============================================================
    # state=imaged · 图片返工(比 revise 文本优先,避免 "chart-3 太密" 走错路)
    # ============================================================
    if state == "imaged":
        # "重做 cover" / "重生 chart-3" / "换 cover" / "cover 不好"
        img_trigger = re.match(
            r'^(?:重做|重生|重新生成|换|再来一张)\s*(cover|chart[-\s]?[1-4])\s*(.*)$',
            raw, re.IGNORECASE,
        )
        if img_trigger:
            target = _normalize_image_target(img_trigger.group(1))
            hint = img_trigger.group(2).strip() or None
            if target:
                return ("revise_image", {"target": target, "hint": hint})

        # "cover 不好" / "chart-3 太密" / "cover 色调冷一点"
        m = re.match(
            r'^(cover|chart[-\s]?[1-4])\s+(.+)$',
            raw, re.IGNORECASE,
        )
        if m:
            target = _normalize_image_target(m.group(1))
            hint = m.group(2).strip()
            if target and hint:
                return ("revise_image", {"target": target, "hint": hint})

    # ============================================================
    # state=wrote · 文章改稿
    # ============================================================
    if state == "wrote":
        # "重写" / "重新写" → 全量换角度
        if re.match(r'^(?:重写|重新写)\b', raw) or t in ("重写", "重新写"):
            return ("revise", {"instruction": "从头重写 · 换角度"})

        # 局部编辑关键字 · 整句原话当 instruction
        edit_patterns = [
            r"^改(.+)",
            r"(.+)太硬$", r"(.+)太硬[,,。]",
            r"(.+)不好$", r"(.+)不好[,,。]",
            r"^加段(.+)", r"^加一段(.+)", r"^加(.+)",
            r"^换(.+)", r"^去掉(.+)", r"^删掉(.+)", r"^删(.+)",
        ]
        for pat in edit_patterns:
            if re.search(pat, raw):
                return ("revise", {"instruction": raw})

        # Fallback:state=wrote · 消息 ≥ 4 字 · 不是短确认词 · 当自然语言改稿
        if len(raw) >= 4:
            return ("revise", {"instruction": raw})

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
            "• 「写 Cursor 2.0 冲击 Claude Code」→ 绕过 brief · 直接按你的 idea 写\n"
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

    if action == "custom_idea":
        idea = kw["idea"]
        status = await message.reply(
            f"💡 收到自定义 idea(🔥 热点系列):\n**{idea}**\n\n"
            f"绕过 brief · claude 直接开写(3-8 分钟)..."
        )
        rc, out = await _run_workflow_script("write.py", ["--idea", idea], status)
        await status.edit(
            content=(f"✓ 文章就绪,已推预览 · 回 `ok` 进生图" if rc == 0
                     else f"❌ 写作失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "idea_save":
        title = kw["title"]
        category = kw.get("category", "flexible")
        status = await message.reply(f"💾 存 idea(分类:{category})...")
        rc, out = await _run_workflow_script(
            "idea.py", ["add", title, "--category", category], status,
        )
        await status.edit(
            content=(out.strip()[-1800:] if rc == 0
                     else f"❌ 存 idea 失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "idea_list":
        status = await message.reply("📋 列 idea 库...")
        rc, out = await _run_workflow_script("idea.py", ["list"], status)
        await status.edit(
            content=(out.strip()[-1800:] if rc == 0
                     else f"❌ 列 idea 失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "idea_done":
        idea_id = kw["id"]
        status = await message.reply(f"✓ 标 idea {idea_id} 已用...")
        rc, out = await _run_workflow_script("idea.py", ["done", str(idea_id)], status)
        await status.edit(
            content=(out.strip()[-1800:] if rc == 0
                     else f"❌ 标已用失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "idea_remove":
        idea_id = kw["id"]
        status = await message.reply(f"🗑️ 删 idea {idea_id}...")
        rc, out = await _run_workflow_script("idea.py", ["rm", str(idea_id)], status)
        await status.edit(
            content=(out.strip()[-1800:] if rc == 0
                     else f"❌ 删除失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "tutorial_idea":
        idea = kw["idea"]
        status = await message.reply(
            f"🛠️ 收到干货 idea(🛠️ 干货系列 · tutorial-instructor 人格):\n"
            f"**{idea}**\n\n"
            f"走 `tutorial-frameworks.md`(T1-T5)+ 步骤化结构(2500-4500 字 · 5-12 分钟)..."
        )
        rc, out = await _run_workflow_script(
            "write.py", ["--idea", idea, "--style", "tutorial"], status,
        )
        await status.edit(
            content=(f"✓ 干货初稿就绪,已推预览 · 回 `ok` 进生图" if rc == 0
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

    if action == "republish":
        status = await message.reply("🔁 重新 sanitize + 推草稿箱(几十秒)...")
        rc, out = await _run_workflow_script("publish.py", [], status)
        await status.edit(
            content=(f"✓ 已重推草稿箱 · 带最新 sanitize(H1/cover-alt/author-card)"
                     if rc == 0
                     else f"❌ republish 失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "revise":
        instruction = kw.get("instruction", "").strip()
        if not instruction:
            await message.reply("🤷 改稿意图为空 · 直接说「改开头太硬」之类。")
            return
        status = await message.reply(
            f"✏️ 收到改稿意图:\n**{instruction[:80]}**\n\nclaude 改写中(2-6 分钟)..."
        )
        rc, out = await _run_workflow_script(
            "revise.py", ["--instruction", instruction], status,
        )
        await status.edit(
            content=(f"✓ 改稿完成,已推新预览" if rc == 0
                     else f"❌ 改稿失败\n```\n{out[-600:]}\n```")
        )
        return

    if action == "revise_image":
        target = kw.get("target")
        hint = kw.get("hint")
        if not target:
            await message.reply("🤷 没识别出要重做哪张 · 试「重做 cover」或「重做 chart-3」。")
            return
        args_list = ["--target", target]
        if hint:
            args_list += ["--hint", hint]
        status = await message.reply(
            f"🎨 重做 **{target}.png**"
            + (f" · 反馈:{hint[:60]}" if hint else "")
            + "\n(2-8 分钟)..."
        )
        rc, out = await _run_workflow_script("revise_image.py", args_list, status)
        await status.edit(
            content=(f"✓ {target}.png 已重做,图已推给你" if rc == 0
                     else f"❌ 图片返工失败\n```\n{out[-600:]}\n```")
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
