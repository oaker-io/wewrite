"""LLM service wrapper for wewrite — 2026-04-26 新建 · 接入 cpa.gateway。

为何新建:wewrite 历史上 5 个 workflow 脚本(write/revise/picpost/auto_review/_state)
都是直接 subprocess `claude -p` · 没统一 wrapper。这次接入 cpa 顺便建一个标准 wrapper
让以后 caller 改造时有目标可去。

v1 范围:仅提供 wrapper · caller 暂不改(保留旧 claude -p 路 · v2 渐进迁移)。

接口:
    generate_text(prompt, system=None, kind="L1_creative") → str
    generate_structured(prompt, schema_hint, system=None, kind="L1_creative") → dict

支持 CPA_DISABLED=1 跳过 cpa 退回 raw claude -p(逃生舱)。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CLAUDE_BIN = shutil.which("claude") or "claude"


class LLMError(RuntimeError):
    pass


def _run_claude(prompt: str, system: str | None = None, timeout: int = 180,
                 retries: int = 1) -> str:
    """Subprocess `claude -p` · retries once on non-zero exit."""
    cmd = [CLAUDE_BIN, "-p"]
    if system:
        cmd += ["--append-system-prompt", system]

    last_err = ""
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(
                cmd, input=prompt,
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            last_err = f"timeout after {timeout}s"
            if attempt < retries:
                time.sleep(2)
                continue
            raise LLMError(f"claude -p {last_err}") from exc

        if proc.returncode == 0:
            return proc.stdout.strip()

        last_err = (
            f"exited {proc.returncode} | "
            f"stderr={proc.stderr.strip()[:200]!r} | "
            f"stdout={proc.stdout.strip()[:200]!r}"
        )
        if attempt < retries:
            time.sleep(2)
            continue
        raise LLMError(f"claude -p {last_err}")


def generate_text(
    prompt: str,
    system: str | None = None,
    kind: str = "L1_creative",
) -> str:
    """生成文本 · 优先走 cpa.gateway · fallback raw claude -p。"""
    if os.environ.get("CPA_DISABLED") != "1":
        try:
            _cpa_root = str(Path.home() / "cpa")
            if _cpa_root not in sys.path:
                sys.path.insert(0, _cpa_root)
            from cpa import gateway as _cpa_gw  # type: ignore
            return _cpa_gw.run(kind=kind, prompt=prompt, system=system)
        except Exception as e:
            print(f"[wewrite/llm_service] cpa 路由失败 · 退回 raw claude -p: {e}",
                  file=sys.stderr)
    return _run_claude(prompt, system=system)


def generate_structured(
    prompt: str,
    schema_hint: dict | str,
    system: str | None = None,
    retries: int = 2,
    kind: str = "L1_creative",
) -> dict:
    """Force JSON output · schema_hint 给 LLM 看 + retry 解析。"""
    schema_str = (
        json.dumps(schema_hint, ensure_ascii=False, indent=2)
        if isinstance(schema_hint, dict)
        else str(schema_hint)
    )
    json_prompt = (
        f"{prompt}\n\n"
        "OUTPUT FORMAT — return ONLY valid JSON (no prose, no fences) matching this shape:\n"
        f"{schema_str}\n"
    )
    last_err: Exception | None = None
    for _ in range(retries + 1):
        raw = generate_text(json_prompt, system=system, kind=kind)
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            last_err = exc
            json_prompt += "\n\nRESPOND WITH VALID JSON ONLY — your last reply did not parse."
    raise LLMError(f"failed to parse JSON after {retries + 1} attempts: {last_err}")
