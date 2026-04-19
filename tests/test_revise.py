"""Smoke tests for revise.py / revise_image.py / bot._classify_intent.

不调用 claude -p · 只验证:
  - state gating(state ≠ 目标 state 时报错 exit)
  - revise_image 的 target 归一 + prompt 构造
  - bot._classify_intent 在不同 state 下正确路由

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_revise -v
或:
  venv/bin/python3 tests/test_revise.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / "scripts" / "workflow"

# Ensure workflow scripts + discord-bot are importable
sys.path.insert(0, str(WORKFLOW_DIR))
sys.path.insert(0, str(REPO_ROOT / "discord-bot"))


def _run_script(script: Path, args: list[str], env_overrides: dict | None = None,
                cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a workflow script as subprocess · return CompletedProcess."""
    py = REPO_ROOT / "venv" / "bin" / "python3"
    if not py.exists():
        py = Path("python3")
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(py), str(script), *args],
        capture_output=True, text=True, timeout=30,
        cwd=str(cwd or REPO_ROOT), env=env,
    )


class IsolatedStateMixin:
    """Run each test against a temp output/session.yaml so we don't clobber real state."""

    def setUp(self):
        # Back up real session.yaml, swap in tmpdir
        self._tmpdir = tempfile.mkdtemp(prefix="wewrite-test-")
        self._real_session = REPO_ROOT / "output" / "session.yaml"
        self._backup = None
        if self._real_session.exists():
            self._backup = self._real_session.read_text(encoding="utf-8")
            self._real_session.unlink()

    def tearDown(self):
        # Restore
        if self._real_session.exists():
            self._real_session.unlink()
        if self._backup is not None:
            self._real_session.write_text(self._backup, encoding="utf-8")
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_session(self, state: str, **extra):
        import yaml
        d = {
            "state": state,
            "article_date": "2026-04-19",
            "topics": [],
            "selected_idx": None,
            "selected_topic": extra.get("selected_topic") or {"title": "测试选题"},
            "article_md": extra.get("article_md"),
            "images_dir": extra.get("images_dir"),
            "draft_media_id": None,
            "updated_at": None,
        }
        d.update(extra)
        self._real_session.parent.mkdir(parents=True, exist_ok=True)
        self._real_session.write_text(
            yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


# =========================================================================
# revise.py · state gating
# =========================================================================

class ReviseStateGateTests(IsolatedStateMixin, unittest.TestCase):

    def test_rejects_idle_state(self):
        """state=idle → revise.py 必须报错退出(非 0)."""
        self._write_session("idle")
        r = _run_script(
            WORKFLOW_DIR / "revise.py",
            ["--instruction", "改开头"],
        )
        self.assertNotEqual(r.returncode, 0,
                            f"expected non-zero exit; stderr={r.stderr}")
        self.assertIn("state=", r.stderr)

    def test_rejects_briefed_state(self):
        self._write_session("briefed")
        r = _run_script(
            WORKFLOW_DIR / "revise.py",
            ["--instruction", "改开头"],
        )
        self.assertNotEqual(r.returncode, 0)

    def test_rejects_imaged_state(self):
        self._write_session("imaged", article_md="output/2026-04-19-test.md")
        r = _run_script(
            WORKFLOW_DIR / "revise.py",
            ["--instruction", "改开头"],
        )
        self.assertNotEqual(r.returncode, 0)

    def test_missing_article_md_in_wrote_errors(self):
        """state=wrote 但 article_md=None → 也报错."""
        self._write_session("wrote", article_md=None)
        r = _run_script(
            WORKFLOW_DIR / "revise.py",
            ["--instruction", "改开头"],
        )
        self.assertNotEqual(r.returncode, 0)

    def test_dry_run_wrote_state_succeeds(self):
        """state=wrote + dry-run + 真实 md 文件 → exit 0."""
        # Write a dummy article md
        md = REPO_ROOT / "output" / "_test_revise_fixture.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# 测试标题\n\n![封面](images/cover.png)\n\n正文...\n",
                      encoding="utf-8")
        try:
            self._write_session(
                "wrote",
                article_md=str(md.relative_to(REPO_ROOT)),
            )
            r = _run_script(
                WORKFLOW_DIR / "revise.py",
                ["--instruction", "开头换个故事", "--dry-run"],
            )
            self.assertEqual(r.returncode, 0,
                             f"dry-run should succeed; stderr={r.stderr}")
            self.assertIn("dry-run", r.stdout)
        finally:
            md.unlink(missing_ok=True)

    def test_empty_instruction_errors(self):
        self._write_session("wrote", article_md="output/foo.md")
        r = _run_script(
            WORKFLOW_DIR / "revise.py",
            ["--instruction", "   "],
        )
        self.assertNotEqual(r.returncode, 0)


# =========================================================================
# revise_image.py · state gating + target parse + prompt build
# =========================================================================

class ReviseImageStateGateTests(IsolatedStateMixin, unittest.TestCase):

    def test_rejects_idle_state(self):
        self._write_session("idle")
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "cover"],
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("state=", r.stderr)

    def test_rejects_wrote_state(self):
        self._write_session("wrote", article_md="output/foo.md")
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "cover"],
        )
        self.assertNotEqual(r.returncode, 0)

    def test_rejects_invalid_target(self):
        self._write_session("imaged")
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "banner-99"],
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("非法", r.stderr)

    def test_accepts_case_insensitive_and_whitespace_target(self):
        """'CHART 3' / 'Cover' 都能被 normalize 到 chart-3 / cover."""
        self._write_session(
            "imaged",
            article_md="output/foo.md",
            selected_topic={"title": "AI 非共识"},
        )
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "CHART 3", "--dry-run"],
        )
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr}")
        self.assertIn("target=chart-3", r.stdout)

    def test_dry_run_builds_cover_prompt(self):
        self._write_session(
            "imaged",
            article_md="output/2026-04-19-ai.md",
            selected_topic={"title": "Cursor 2.0 冲击 Claude Code"},
        )
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "cover", "--hint", "色调冷一点", "--dry-run"],
        )
        self.assertEqual(r.returncode, 0)
        out = r.stdout
        self.assertIn("target=cover", out)
        self.assertIn("output/images/cover.png", out)
        self.assertIn("色调冷一点", out)
        self.assertIn("2.35:1", out)
        self.assertIn("Cursor 2.0", out)

    def test_dry_run_builds_chart_prompt(self):
        self._write_session(
            "imaged",
            article_md="output/x.md",
            selected_topic={"title": "T"},
        )
        r = _run_script(
            WORKFLOW_DIR / "revise_image.py",
            ["--target", "chart-2", "--dry-run"],
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("output/images/chart-2.png", r.stdout)
        self.assertIn("16:9", r.stdout)
        self.assertIn("infographic-dense", r.stdout)


# =========================================================================
# revise_image.py · normalize_target(unit)
# =========================================================================

class NormalizeTargetTests(unittest.TestCase):

    def test_various_shapes(self):
        import importlib
        mod = importlib.import_module("revise_image")
        normalize = mod.normalize_target

        self.assertEqual(normalize("cover"), "cover")
        self.assertEqual(normalize("Cover"), "cover")
        self.assertEqual(normalize("COVER"), "cover")
        self.assertEqual(normalize("chart-1"), "chart-1")
        self.assertEqual(normalize("chart-4"), "chart-4")
        self.assertEqual(normalize("CHART-3"), "chart-3")
        self.assertEqual(normalize("chart3"), "chart-3")
        self.assertEqual(normalize("chart 3"), "chart-3")
        self.assertEqual(normalize("chart_2"), "chart-2")
        # invalid
        self.assertIsNone(normalize("chart-5"))
        self.assertIsNone(normalize("banner"))
        self.assertIsNone(normalize(""))
        self.assertIsNone(normalize("cover.png"))


class BuildPromptTests(unittest.TestCase):

    def test_cover_prompt_includes_required_fields(self):
        import importlib
        mod = importlib.import_module("revise_image")
        p = mod.build_prompt(
            "cover",
            "output/2026-04-19-foo.md",
            "AI Coding 非共识",
            "色调冷一点",
        )
        self.assertIn("output/images/cover.png", p)
        self.assertIn("其他 4 张保留不要动", p)
        self.assertIn("2.35:1", p)
        self.assertIn("宸的 AI 掘金笔记", p)
        self.assertIn("色调冷一点", p)
        self.assertIn("DONE revised cover", p)

    def test_chart_prompt_uses_default_feedback_when_no_hint(self):
        import importlib
        mod = importlib.import_module("revise_image")
        p = mod.build_prompt("chart-3", "output/foo.md", "T", None)
        self.assertIn("chart-3", p)
        self.assertIn("16:9", p)
        self.assertIn("infographic-dense", p)
        # 默认兜底话术
        self.assertIn("用户不满意", p)


# =========================================================================
# revise.py · 字数警告
# =========================================================================

class LengthWarningTests(unittest.TestCase):

    def setUp(self):
        import importlib
        self.mod = importlib.import_module("revise")

    def test_short_triggers_warning(self):
        w = self.mod._length_warning(1200)
        self.assertIn("偏短", w)
        self.assertIn("1200", w)

    def test_long_triggers_warning(self):
        w = self.mod._length_warning(4000)
        self.assertIn("偏长", w)
        self.assertIn("4000", w)

    def test_in_range_no_warning(self):
        self.assertEqual(self.mod._length_warning(2000), "")
        self.assertEqual(self.mod._length_warning(1500), "")  # 下限等于
        self.assertEqual(self.mod._length_warning(3500), "")  # 上限等于


# =========================================================================
# bot._classify_intent · 路由表驱动测试
# =========================================================================

class ClassifyIntentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # bot.py 导入会触发 TOKEN 检查和 discord connect setup;
        # set dummy env + monkey-patch so we only pull the function out.
        os.environ.setdefault("DISCORD_BOT_TOKEN", "dummy")
        os.environ.setdefault("WEWRITE_DIR", str(REPO_ROOT))
        # discord lib is heavy;  bot.py imports it at top level · we assume
        # the venv has it (requirements.txt lists it). If not, skip.
        try:
            import importlib
            cls.bot = importlib.import_module("bot")
        except Exception as e:
            raise unittest.SkipTest(f"bot module import failed: {e}")

    def _clf(self, text, state):
        return self.bot._classify_intent(text, state)

    # ---- existing actions still work ----

    def test_brief_triggers_brief(self):
        self.assertEqual(self._clf("今日热点", "idle")[0], "brief")
        self.assertEqual(self._clf("brief", "idle")[0], "brief")
        self.assertEqual(self._clf("开始", "idle")[0], "brief")

    def test_number_pick_in_briefed(self):
        action, kw = self._clf("1", "briefed")
        self.assertEqual(action, "write_idx")
        self.assertEqual(kw["idx"], 0)
        action, kw = self._clf("选3", "briefed")
        self.assertEqual(action, "write_idx")
        self.assertEqual(kw["idx"], 2)

    def test_number_ignored_outside_briefed(self):
        """'1' 在 wrote 状态下不应该路由为 write_idx."""
        action, _ = self._clf("1", "wrote")
        self.assertNotEqual(action, "write_idx")

    def test_custom_idea(self):
        action, kw = self._clf("写 Cursor 2.0 冲击 Claude Code", "idle")
        self.assertEqual(action, "custom_idea")
        self.assertIn("Cursor", kw["idea"])

    def test_reset(self):
        self.assertEqual(self._clf("pass", "briefed")[0], "reset")
        self.assertEqual(self._clf("跳过", "wrote")[0], "reset")

    def test_ok_in_wrote_goes_next(self):
        """'ok' 在 wrote 状态下应该是 next(进生图),不是 revise."""
        self.assertEqual(self._clf("ok", "wrote")[0], "next")
        self.assertEqual(self._clf("继续", "wrote")[0], "next")
        self.assertEqual(self._clf("好的", "imaged")[0], "next")

    # ---- revise (new) ----

    def test_revise_rewrite(self):
        action, kw = self._clf("重写", "wrote")
        self.assertEqual(action, "revise")
        self.assertIn("换角度", kw["instruction"])

        action, kw = self._clf("重新写 · 换个视角", "wrote")
        self.assertEqual(action, "revise")

    def test_revise_edit_patterns(self):
        action, kw = self._clf("改开头", "wrote")
        self.assertEqual(action, "revise")
        self.assertEqual(kw["instruction"], "改开头")

        action, kw = self._clf("加段 Devin 对比", "wrote")
        self.assertEqual(action, "revise")
        self.assertIn("Devin", kw["instruction"])

        action, kw = self._clf("开头太硬", "wrote")
        self.assertEqual(action, "revise")
        self.assertIn("太硬", kw["instruction"])

        action, kw = self._clf("去掉最后那段吐槽", "wrote")
        self.assertEqual(action, "revise")

    def test_revise_fallback_long_free_text(self):
        """state=wrote · 任意长句 ≥ 4 字 · 都当 revise."""
        action, kw = self._clf("结尾太鸡汤了给换个落点", "wrote")
        self.assertEqual(action, "revise")

    def test_revise_not_triggered_outside_wrote(self):
        """state=idle/imaged · '改开头' 不应该走 revise."""
        self.assertNotEqual(self._clf("改开头", "idle")[0], "revise")
        self.assertNotEqual(self._clf("改开头", "briefed")[0], "revise")
        self.assertNotEqual(self._clf("改开头", "imaged")[0], "revise")

    # ---- revise_image (new) ----

    def test_revise_image_redo_cover(self):
        action, kw = self._clf("重做 cover", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "cover")
        self.assertIsNone(kw["hint"])

    def test_revise_image_redo_chart(self):
        action, kw = self._clf("重做 chart-3", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "chart-3")

        action, kw = self._clf("换 chart-1", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "chart-1")

    def test_revise_image_hint_form(self):
        """'cover 色调冷一点' → target=cover, hint='色调冷一点'."""
        action, kw = self._clf("cover 色调冷一点", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "cover")
        self.assertIn("色调冷", kw["hint"])

        action, kw = self._clf("chart-3 太密了", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "chart-3")
        self.assertIn("太密", kw["hint"])

    def test_revise_image_case_insensitive(self):
        action, kw = self._clf("重做 Cover", "imaged")
        self.assertEqual(action, "revise_image")
        self.assertEqual(kw["target"], "cover")

    def test_revise_image_not_triggered_outside_imaged(self):
        self.assertNotEqual(self._clf("重做 cover", "wrote")[0], "revise_image")
        self.assertNotEqual(self._clf("重做 cover", "idle")[0], "revise_image")

    def test_claude_fallback_idle_free_form(self):
        """state=idle · 自由问题 · 回退 claude_fallback."""
        action, _ = self._clf("帮我查一下 nano-banana-2 定价", "idle")
        self.assertEqual(action, "claude_fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
