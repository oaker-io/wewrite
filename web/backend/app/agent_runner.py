"""用 Claude Agent SDK 运行 WeWrite 的 SKILL.md 管道，并把过程流式产出为任务事件。

NOTE(生产/安全): Agent 以 permission_mode="bypassPermissions" 执行 Bash —— 必须把每个任务
跑在隔离的沙箱容器里。下面把整个 os.environ 透传给 Agent 进程是为了让 `claude` CLI 拿到
PATH / node / ANTHROPIC_API_KEY；生产应改为最小白名单环境并清除无关机密。
"""
from __future__ import annotations

import asyncio
import importlib.util as _ilu
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from .config import Settings, get_settings
from .platforms import HUMANNESS_THRESHOLD, MAX_REWRITE_RETRIES, SIMILARITY_THRESHOLD, get_profile
from .store import Job
from .workspace import agent_env, build_workspace, cleanup_workspace

# 与 SKILL.md frontmatter 的 allowed-tools 对齐
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite"]

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_COMPLETION_RE = re.compile(r"\b(DONE_WITH_CONCERNS|DONE|BLOCKED|NEEDS_CONTEXT)\b")


def _skill_system_prompt(settings: Settings) -> dict:
    body = (settings.skill_dir / "SKILL.md").read_text(encoding="utf-8")
    body = _FRONTMATTER.sub("", body, count=1).strip()
    note = (
        "\n\n---\n# 运行环境说明\n"
        "你正在云端为外部用户执行 WeWrite 公众号写作管道。\n"
        "- 本说明上方的内容来自 WeWrite 的 SKILL.md，是你要严格遵循的主管道。\n"
        "- `{skill_dir}` 指你当前的工作目录（cwd）。toolkit/scripts/references/personas 已就位。\n"
        "- 风格在 style.yaml；微信与图片密钥已通过环境变量注入（toolkit 会自动读取）。\n"
        "- 用户看不到你的中间思考，过程进度请用简短的一行行文本表达。\n"
    )
    return {"type": "preset", "preset": "claude_code", "append": body + note}


def _build_prompt(job: Job, *, publish: bool) -> str:
    mode = "交互模式（在选题/框架/配图处可暂停确认）" if job.interactive else "全自动模式（一口气跑完 Step 1-8，不中途停）"
    if publish:
        pub = "完成后把成稿推送到微信公众号草稿箱（appid/secret 已注入环境，可直接发布）。"
    else:
        pub = "只在本地生成并排版，不要推送草稿箱（视作 skip_publish 降级）。"
    return (
        f"{job.prompt}\n\n"
        f"（{mode}。请按 SKILL.md 主管道 Step 1-8 完整执行；"
        f"每进入一步输出一行 `[N/8] 步骤名` 的文本进度。{pub} "
        f"最终把文章正文保存为 `output/article.md`（这是要交付给用户的正文）；"
        f"配图提示词、SEO 备注等辅助 Markdown 请另存到 `output/assets/` 子目录，"
        f"不要和正文一起堆在 output 顶层。）"
    )


def _summarize_tool_input(name: str, tool_input: dict) -> str:
    if name == "Bash":
        cmd = str(tool_input.get("command", ""))
        return cmd[:200]
    if name in ("Read", "Write", "Edit"):
        return str(tool_input.get("file_path", ""))
    if name in ("Glob", "Grep"):
        return str(tool_input.get("pattern", ""))
    if name in ("WebSearch", "WebFetch"):
        return str(tool_input.get("query") or tool_input.get("url", ""))
    return ""


async def _consume_stream(message_iter, job) -> str:
    """消费 Agent SDK 流，emit 事件，返回最后一段 assistant 文本。"""
    last_text = ""
    async for message in message_iter:
        if isinstance(message, SystemMessage):
            continue
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if text:
                        last_text = text
                        job.emit({"type": "assistant_text", "text": text})
                elif isinstance(block, ToolUseBlock):
                    job.emit({"type": "tool_use", "name": block.name,
                              "detail": _summarize_tool_input(block.name, block.input or {})})
                elif isinstance(block, ThinkingBlock):
                    continue
        elif isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    job.emit({"type": "tool_result", "is_error": bool(block.is_error)})
        elif isinstance(message, ResultMessage):
            job.completion = _detect_completion(last_text, getattr(message, "result", None))
            job.emit({"type": "result_meta", "completion": job.completion,
                      "num_turns": getattr(message, "num_turns", None),
                      "total_cost_usd": getattr(message, "total_cost_usd", None),
                      "is_error": getattr(message, "is_error", False)})
    return last_text


async def run_job(job: Job) -> None:
    settings = get_settings()
    from .store import STORE

    account = STORE.account(job.user_id)
    theme = job.theme or account.theme
    persona = job.persona or account.writing_persona
    # 只有用户已绑定微信，才真正允许推送
    publish = job.publish_draft and account.wechat_bound

    job.status = "running"
    job.emit({"type": "status", "status": "running"})
    if job.publish_draft and not account.wechat_bound:
        job.emit({
            "type": "notice",
            "text": "未绑定微信公众号，已自动降级为仅本地生成（不推送草稿箱）。",
        })

    ws: Optional[Path] = None
    try:
        ws = build_workspace(settings, account, theme=theme, persona=persona)
        job.emit({"type": "log", "text": f"工作区已就绪：{ws.name}"})

        env = {**os.environ, **agent_env(settings, account, theme=theme)}
        options = ClaudeAgentOptions(
            system_prompt=_skill_system_prompt(settings),
            allowed_tools=ALLOWED_TOOLS,
            permission_mode="bypassPermissions",
            model=settings.model,
            cwd=str(ws),
            env=env,
            max_turns=settings.max_turns,
            setting_sources=None,
        )

        await _consume_stream(
            query(prompt=_build_prompt(job, publish=publish), options=options), job)

        _collect_outputs(job, ws, theme=theme)
        job.status = "done"
        job.emit({"type": "status", "status": "done", "completion": job.completion})
    except Exception as exc:  # noqa: BLE001 - 把任意失败回传给前端
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
        job.emit({"type": "status", "status": "error", "error": job.error})
    finally:
        cleanup_workspace(ws)
        job.finish()


def _detect_completion(last_text: str, result_text: Optional[str]) -> Optional[str]:
    for blob in (result_text or "", last_text):
        m = _COMPLETION_RE.search(blob)
        if m:
            return m.group(1)
    return "DONE"


_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _collect_outputs(job: Job, ws: Path, *, theme: str) -> None:
    out = ws / "output"
    if not out.exists():
        return
    # 先持久化图片（工作区随后会被清理）
    _persist_images(job, out)
    md = _pick_article(out)
    if md is None:
        return
    text = md.read_text(encoding="utf-8")
    job.preview_html = _generate_preview(ws, md, theme=theme)  # 预览基于原始相对路径
    # 把正文里的本地图片引用改写成持久化后的 URL，使 markdown 自包含
    job.article_markdown = _rewrite_md_images(text, job)
    job.title = _first_heading(text) or md.stem


# 文件名 / 首标题里出现这些标记，视为辅助产物（配图提示词、SEO 备注等），不是正文
_AUX_NAME_HINTS = ("prompt", "preview", "metadata", "seo", "image", "提示词", "配图")
_AUX_HEADING_HINTS = ("配图", "提示词", "prompt", "封面文案", "seo")


def _looks_auxiliary(p: Path) -> bool:
    name = p.stem.lower()
    if any(h in name for h in _AUX_NAME_HINTS):
        return True
    try:
        head = _first_heading(p.read_text(encoding="utf-8")) or ""
    except OSError:
        return False
    return any(h in head.lower() for h in _AUX_HEADING_HINTS)


def _pick_article(out: Path) -> Optional[Path]:
    """从 output/ 里挑出"文章正文"。

    不能盲取最近修改的 .md —— 管道在正文之后常会再写辅助产物（配图提示词包、SEO 备注），
    那些 mtime 更新，会被误当成正文。选取顺序：
      1) 约定的固定名 output/article.md（_build_prompt 已要求 agent 这样存）；
      2) 排除 assets/ 子目录与明显的辅助产物后，取最新的 .md；
      3) 若全被排除（极端情况），兜底取最新的任意 .md。
    """
    canonical = out / "article.md"
    if canonical.is_file():
        return canonical
    mds = [
        p for p in out.glob("**/*.md")
        if p.is_file() and "assets" not in p.relative_to(out).parts[:-1]
    ]
    if not mds:
        return None
    non_aux = [p for p in mds if not _looks_auxiliary(p)]
    pool = non_aux or mds
    return max(pool, key=lambda p: p.stat().st_mtime)


def _image_sort_key(p: Path) -> tuple:
    name = p.name.lower()
    if "cover" in name or "封面" in name:
        return (0, 0, name)
    m = re.search(r"fig(\d+)", name)
    if m:
        return (1, int(m.group(1)), name)
    return (2, 0, name)


def _persist_images(job: Job, out: Path) -> None:
    from .config import get_settings

    settings = get_settings()
    imgs = sorted(
        (p for p in out.glob("**/*") if p.is_file() and p.suffix.lower() in _IMAGE_EXTS),
        key=_image_sort_key,
    )
    if not imgs:
        return
    dest = settings.artifact_root / job.id
    dest.mkdir(parents=True, exist_ok=True)
    for p in imgs:
        target = dest / p.name
        try:
            shutil.copy2(p, target)
        except OSError:
            continue
        rel = f"/artifacts/{job.id}/{p.name}"
        job.images.append(settings.public_base_url + rel if settings.public_base_url else rel)
        job.image_paths.append(str(target))


def _rewrite_md_images(md: str, job: Job) -> str:
    if not job.images:
        return md
    # basename -> URL
    by_name = {Path(u).name: u for u in job.images}

    def repl(m: re.Match) -> str:
        alt, path = m.group(1), m.group(2)
        url = by_name.get(Path(path).name)
        return f"![{alt}]({url})" if url else m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md)


def _first_heading(markdown: str) -> Optional[str]:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            return line[:60]
    return None


def _generate_preview(ws: Path, md: Path, *, theme: str) -> Optional[str]:
    """用 toolkit 把 Markdown 渲染成微信风格 HTML（best-effort）。"""
    py = ws / ".venv" / "bin" / "python3"
    python = str(py) if py.exists() else "python3"
    preview = ws / "output" / "preview.html"
    try:
        subprocess.run(
            [python, "toolkit/cli.py", "preview", str(md), "--theme", theme,
             "--no-open", "-o", str(preview)],
            cwd=str(ws), capture_output=True, timeout=120, check=False,
        )
        if preview.exists():
            return preview.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - 预览失败不影响主产物
        return None
    return None


def _load_similarity():
    """从仓库 scripts/similarity_check.py 动态加载 similarity 函数。"""
    settings = get_settings()
    path = settings.skill_dir / "scripts" / "similarity_check.py"
    spec = _ilu.spec_from_file_location("similarity_check", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.similarity


def gate_passes(humanness: float | None, max_similarity: float | None) -> bool:
    if humanness is not None and humanness < HUMANNESS_THRESHOLD:
        return False
    if max_similarity is not None and max_similarity > SIMILARITY_THRESHOLD:
        return False
    return True


_TAG_RE = re.compile(r"#(\w[\w一-鿿]*)")


def _extract_tags(md: str) -> list[str]:
    seen, out = set(), []
    for m in _TAG_RE.findall(md):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _humanness_best_effort(ws: Path, filename: str) -> float | None:
    """跑 humanness_score.py 取分；失败则返回 None（降级，不阻断）。"""
    py = ws / ".venv" / "bin" / "python3"
    python = str(py) if py.exists() else "python3"
    try:
        r = subprocess.run(
            [python, "scripts/humanness_score.py", f"output/{filename}", "--json"],
            cwd=str(ws), capture_output=True, timeout=120, check=False, text=True,
        )
        data = json.loads(r.stdout or "{}")
        for key in ("composite", "score", "humanness"):
            if isinstance(data.get(key), (int, float)):
                return float(data[key])
    except Exception:  # noqa: BLE001 - 评分失败不阻断
        return None
    return None


def _collect_platform_versions(job, ws: Path, source_md: str, profiles: list) -> list[dict]:
    out = ws / "output"
    try:
        similarity = _load_similarity()
    except Exception:  # noqa: BLE001 - 相似度脚本不可用则降级，不丢已产出的版本
        def similarity(a, b):  # noqa: ANN001
            return 0.0
    read: list[tuple] = []
    versions: list[dict] = []
    for prof in profiles:
        f = out / prof.output_filename
        if not f.is_file():
            versions.append({
                "platform": prof.id, "label": prof.label, "output_kind": prof.output_kind,
                "title": "", "markdown": "", "images": [], "tags": [],
                "humanness": None, "max_similarity": None, "passed": False,
                "status": "failed", "warning": "未产出该平台版本",
            })
            continue
        read.append((prof, f.read_text(encoding="utf-8")))
    for prof, md in read:
        sim_src = similarity(source_md, md)
        sim_peers = max((similarity(md, other) for p2, other in read if p2.id != prof.id),
                        default=0.0)
        max_sim = round(max(sim_src, sim_peers), 4)
        hu = _humanness_best_effort(ws, prof.output_filename)
        passed = gate_passes(hu, max_sim)
        v = {
            "platform": prof.id, "label": prof.label, "output_kind": prof.output_kind,
            "title": _first_heading(md) or prof.label,
            "markdown": _rewrite_md_images(md, job) if prof.needs_images else md,
            "images": list(getattr(job, "images", [])) if prof.needs_images else [],
            "tags": _extract_tags(md),
            "humanness": hu, "max_similarity": max_sim,
            "passed": passed, "status": "done",
            "warning": "" if passed else "未完全通过质量门（相似度偏高或反AI偏低），建议人工微调",
        }
        versions.append(v)
    return versions


def _distribute_system_prompt(settings: Settings, profiles: list) -> dict:
    guide = (settings.skill_dir / "references" / "multiplatform-rewrite.md").read_text(encoding="utf-8")
    briefs = "\n\n".join(
        f"### 平台：{p.label}（id={p.id}）\n"
        f"- 产出文件：output/{p.output_filename}\n"
        f"- 形态：{p.output_kind}；需配图：{p.needs_images}\n"
        f"- 规范：\n{p.rewrite_brief}"
        for p in profiles
    )
    body = (
        "你是 WeWrite 的多平台改写引擎。把 `output/source.md` 的源内容改写成下列各平台的适配版本。\n\n"
        f"{guide}\n\n## 本次目标平台\n{briefs}\n\n"
        "- 用户看不到你的中间思考，进度用简短一行行文本表达。\n"
        f"- 每个平台版本写完后跑质量门自查，不过则重写，最多重试 {MAX_REWRITE_RETRIES} 次。"
    )
    return {"type": "preset", "preset": "claude_code", "append": body}


def _distribute_prompt(profiles: list) -> str:
    names = "、".join(p.label for p in profiles)
    files = "、".join(f"output/{p.output_filename}" for p in profiles)
    return (
        f"请把 output/source.md 改写为：{names}。\n"
        f"分别保存到：{files}。每进入一个平台输出一行 `[改写] 平台名` 的进度。\n"
        "严格遵守原创铁律（内容级真改、与源和彼此都拉开差异）与各平台规范，"
        "并对每个版本跑 humanness_score.py 与 similarity_check.py 自查。"
    )


async def run_distribute_job(job: Job) -> None:
    settings = get_settings()
    from .store import STORE

    account = STORE.account(job.user_id)
    theme = job.theme or account.theme
    persona = job.persona or account.writing_persona
    profiles = [p for p in (get_profile(pid) for pid in job.target_platforms) if p]

    job.status = "running"
    job.emit({"type": "status", "status": "running"})
    if not profiles:
        job.status = "error"
        job.error = "无有效目标平台"
        job.emit({"type": "status", "status": "error", "error": job.error})
        job.finish()
        return

    ws: Optional[Path] = None
    try:
        ws = build_workspace(settings, account, theme=theme, persona=persona)
        (ws / "output").mkdir(exist_ok=True)
        (ws / "output" / "source.md").write_text(job.source_markdown, encoding="utf-8")
        _seed_source_images(job, ws)
        job.emit({"type": "log",
                  "text": f"改写工作区就绪，目标：{'、'.join(p.label for p in profiles)}"})

        env = {**os.environ, **agent_env(settings, account, theme=theme)}
        options = ClaudeAgentOptions(
            system_prompt=_distribute_system_prompt(settings, profiles),
            allowed_tools=ALLOWED_TOOLS, permission_mode="bypassPermissions",
            model=settings.model, cwd=str(ws), env=env,
            max_turns=settings.max_turns, setting_sources=None,
        )
        await _consume_stream(query(prompt=_distribute_prompt(profiles), options=options), job)

        # 收集前先把源图片持久化（供小红书复用）
        _persist_images(job, ws / "output")
        # 收集含同步子进程评分，放到线程，避免阻塞事件循环冻结其它 SSE
        job.platform_versions = await asyncio.to_thread(
            _collect_platform_versions, job, ws, job.source_markdown, profiles)
        job.status = "done"
        job.emit({"type": "status", "status": "done",
                  "versions": [{"platform": v["platform"], "status": v["status"],
                                "passed": v.get("passed")} for v in job.platform_versions]})
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
        job.emit({"type": "status", "status": "error", "error": job.error})
    finally:
        cleanup_workspace(ws)
        job.finish()


def _seed_source_images(job: Job, ws: Path) -> None:
    """把内联源（generate job）已持久化的图片拷进改写工作区 output/，供小红书复用。"""
    for p in getattr(job, "source_image_paths", None) or []:
        src = Path(p)
        if src.is_file():
            try:
                shutil.copy2(src, ws / "output" / src.name)
            except OSError:
                continue
