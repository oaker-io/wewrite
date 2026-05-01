"""Tests for scripts/workflow/_idea_bank.py + idea.py CLI + bot.py idea intents.

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_idea_bank -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / "scripts" / "workflow"

sys.path.insert(0, str(WORKFLOW_DIR))
sys.path.insert(0, str(REPO_ROOT / "discord-bot"))


# -----------------------------------------------------------------
# helper: 隔离 idea_bank.yaml 到 tmpdir
# -----------------------------------------------------------------
class _BankIsolationMixin:
    """每个测试用 tmpdir 内的 idea_bank.yaml,避免污染真实文件。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="wewrite-idea-")
        self._bank_file = Path(self._tmpdir) / "idea_bank.yaml"
        self._prev_env = os.environ.get("WEWRITE_IDEA_BANK")
        os.environ["WEWRITE_IDEA_BANK"] = str(self._bank_file)

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("WEWRITE_IDEA_BANK", None)
        else:
            os.environ["WEWRITE_IDEA_BANK"] = self._prev_env
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# -----------------------------------------------------------------
# 1. TestIdeaBankModel · 纯函数接口
# -----------------------------------------------------------------
class TestIdeaBankModel(_BankIsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # 强制 reload _idea_bank · 防止跨测试缓存
        if "_idea_bank" in sys.modules:
            del sys.modules["_idea_bank"]
        import _idea_bank  # noqa
        self._mod = _idea_bank

    def test_add_returns_record_with_incremented_id(self):
        r1 = self._mod.add("第一条")
        r2 = self._mod.add("第二条")
        self.assertEqual(r1["id"], 1)
        self.assertEqual(r2["id"], 2)
        self.assertEqual(r1["title"], "第一条")
        self.assertFalse(r1["used"])
        self.assertEqual(r1["category"], "flexible")

    def test_add_raises_on_empty_title(self):
        with self.assertRaises(ValueError):
            self._mod.add("")
        with self.assertRaises(ValueError):
            self._mod.add("   ")

    def test_add_raises_on_invalid_category(self):
        with self.assertRaises(ValueError):
            self._mod.add("foo", category="not-a-cat")

    def test_list_returns_unused_only_by_default(self):
        a = self._mod.add("a")
        b = self._mod.add("b")
        self._mod.mark_used(a["id"])
        ideas = self._mod.list_ideas()
        ids = [i["id"] for i in ideas]
        self.assertIn(b["id"], ids)
        self.assertNotIn(a["id"], ids)
        # only_unused=False 时两条都返回
        all_ideas = self._mod.list_ideas(only_unused=False)
        self.assertEqual(len(all_ideas), 2)

    def test_list_filter_by_category(self):
        self._mod.add("教程类", category="tutorial")
        self._mod.add("热点类", category="hotspot")
        self._mod.add("普通类", category="flexible")
        tut = self._mod.list_ideas(category="tutorial")
        self.assertEqual(len(tut), 1)
        self.assertEqual(tut[0]["title"], "教程类")
        with self.assertRaises(ValueError):
            self._mod.list_ideas(category="bad-cat")

    def test_list_sorted_by_priority_then_id(self):
        a = self._mod.add("low pri", priority=10)   # id=1
        b = self._mod.add("high pri", priority=90)  # id=2
        c = self._mod.add("mid pri", priority=50)   # id=3
        d = self._mod.add("high pri 2", priority=90)  # id=4
        ideas = self._mod.list_ideas()
        # priority desc · 同 priority 按 id desc
        self.assertEqual([i["id"] for i in ideas],
                         [d["id"], b["id"], c["id"], a["id"]])

    def test_get_returns_none_when_missing(self):
        self.assertIsNone(self._mod.get(999))
        rec = self._mod.add("foo")
        self.assertEqual(self._mod.get(rec["id"])["title"], "foo")

    def test_mark_used_sets_used_and_timestamp(self):
        rec = self._mod.add("foo")
        self.assertFalse(rec["used"])
        self.assertIsNone(rec["used_at"])
        upd = self._mod.mark_used(rec["id"], article_md="output/x.md")
        self.assertTrue(upd["used"])
        self.assertIsNotNone(upd["used_at"])
        self.assertEqual(upd["used_article_md"], "output/x.md")
        # 持久化生效
        again = self._mod.get(rec["id"])
        self.assertTrue(again["used"])

    def test_remove_raises_on_missing_id(self):
        with self.assertRaises(KeyError):
            self._mod.remove(999)
        rec = self._mod.add("foo")
        removed = self._mod.remove(rec["id"])
        self.assertEqual(removed["id"], rec["id"])
        self.assertIsNone(self._mod.get(rec["id"]))

    def test_stats_counts(self):
        self._mod.add("a", category="tutorial")
        self._mod.add("b", category="hotspot")
        self._mod.add("c", category="flexible")
        used = self._mod.add("d", category="tutorial")
        self._mod.mark_used(used["id"])
        s = self._mod.stats()
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["used"], 1)
        self.assertEqual(s["unused"], 3)
        self.assertEqual(s["by_category"]["tutorial"], 2)
        self.assertEqual(s["by_category"]["hotspot"], 1)
        self.assertEqual(s["by_category"]["flexible"], 1)

    def test_load_returns_empty_when_no_file(self):
        # tmpdir 全新 · 没文件
        self.assertFalse(self._bank_file.exists())
        m = self._mod.load()
        self.assertEqual(m["next_id"], 1)
        self.assertEqual(m["ideas"], [])

    def test_persist_and_reload(self):
        self._mod.add("a")
        self._mod.add("b")
        # 重新 import · 模拟新进程
        del sys.modules["_idea_bank"]
        import _idea_bank as fresh
        ideas = fresh.list_ideas()
        self.assertEqual(len(ideas), 2)
        # next_id 也持久了
        m = fresh.load()
        self.assertEqual(m["next_id"], 3)


# -----------------------------------------------------------------
# 2. TestIdeaCli · subprocess 跑 idea.py · 验 stdout
# -----------------------------------------------------------------
class TestIdeaCli(_BankIsolationMixin, unittest.TestCase):
    def _run_cli(self, *args) -> tuple[int, str, str]:
        py = REPO_ROOT / "venv" / "bin" / "python3"
        if not py.exists():
            py = Path("python3")
        script = WORKFLOW_DIR / "idea.py"
        env = os.environ.copy()
        env["WEWRITE_IDEA_BANK"] = str(self._bank_file)
        proc = subprocess.run(
            [str(py), str(script), *args],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT), env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_add_then_list(self):
        rc, out, err = self._run_cli("add", "claude design 9 个使用技巧",
                                     "--category", "tutorial")
        self.assertEqual(rc, 0, msg=err)
        self.assertIn("✓ 已存 #1", out)

        rc, out, err = self._run_cli("list")
        self.assertEqual(rc, 0, msg=err)
        # markdown 表头
        self.assertIn("| # |", out)
        self.assertIn("title", out)
        self.assertIn("claude design", out)

    def test_add_with_priority_appears_first(self):
        self._run_cli("add", "low", "--priority", "10")
        self._run_cli("add", "high", "--priority", "90")
        rc, out, err = self._run_cli("list")
        self.assertEqual(rc, 0, msg=err)
        # high 在 low 上面
        i_high = out.find("high")
        i_low = out.find("low")
        self.assertGreater(i_high, 0)
        self.assertGreater(i_low, i_high)

    def test_done_marks_used(self):
        rc, _, _ = self._run_cli("add", "foo")
        self.assertEqual(rc, 0)
        rc, out, err = self._run_cli("done", "1")
        self.assertEqual(rc, 0, msg=err)
        self.assertIn("✓ idea #1 已标记", out)
        # 默认 list 不应再显示
        rc, out, _ = self._run_cli("list")
        self.assertNotIn("foo", out)

    def test_rm_removes(self):
        self._run_cli("add", "to-delete")
        rc, out, err = self._run_cli("rm", "1")
        self.assertEqual(rc, 0, msg=err)
        self.assertIn("🗑️ 已删 #1", out)
        # show 应该 404
        rc, _, err = self._run_cli("show", "1")
        self.assertEqual(rc, 1)
        self.assertIn("❌", err)

    def test_stats_format(self):
        self._run_cli("add", "a", "--category", "tutorial")
        self._run_cli("add", "b", "--category", "hotspot")
        rc, out, err = self._run_cli("stats")
        self.assertEqual(rc, 0, msg=err)
        self.assertIn("📊 总 2 条", out)
        self.assertIn("tutorial", out)
        self.assertIn("hotspot", out)

    def test_show_missing_id_errors(self):
        rc, out, err = self._run_cli("show", "999")
        self.assertEqual(rc, 1)
        self.assertIn("❌", err)


# -----------------------------------------------------------------
# 3. TestBotIntentIdea · _classify_intent 4 个新 intent
# -----------------------------------------------------------------
class TestBotIntentIdea(unittest.TestCase):
    def _classify(self, text, state="idle"):
        os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
        if "bot" in sys.modules:
            del sys.modules["bot"]
        import bot
        return bot._classify_intent(text, state)

    # -- idea_save --
    def test_save_tutorial_keyword_routes_to_idea_save_with_tutorial_category(self):
        action, kw = self._classify("存 idea: claude design 9 个使用技巧的教程")
        self.assertEqual(action, "idea_save")
        self.assertEqual(kw["category"], "tutorial")
        self.assertIn("claude design", kw["title"])

    def test_save_hotspot_keyword_routes_with_hotspot_category(self):
        action, kw = self._classify("记 idea: GPT-5 降智热点观察")
        self.assertEqual(action, "idea_save")
        self.assertEqual(kw["category"], "hotspot")
        self.assertIn("GPT-5", kw["title"])

    def test_save_default_category_flexible(self):
        action, kw = self._classify("存 idea: 关于 AI Agent 的随想")
        self.assertEqual(action, "idea_save")
        self.assertEqual(kw["category"], "flexible")
        self.assertIn("AI Agent", kw["title"])

    # -- idea_list --
    def test_list_keywords(self):
        for kw in ["我的 idea", "今日 idea", "idea 库", "idea list",
                   "看看 idea", "列 idea"]:
            action, _ = self._classify(kw)
            self.assertEqual(action, "idea_list",
                             f"关键词 {kw!r} 应触发 idea_list")

    # -- idea_done --
    def test_done_with_id(self):
        for txt, expect_id in [
            ("idea 3 用了", 3),
            ("idea 5 用", 5),
            ("标 idea 7", 7),
            ("done idea 12", 12),
        ]:
            action, kw = self._classify(txt)
            self.assertEqual(action, "idea_done",
                             f"{txt!r} 应触发 idea_done")
            self.assertEqual(kw["id"], expect_id)

    # -- idea_remove --
    def test_remove_with_id(self):
        for txt, expect_id in [
            ("删 idea 3", 3),
            ("删除 idea 7", 7),
            ("rm idea 12", 12),
        ]:
            action, kw = self._classify(txt)
            self.assertEqual(action, "idea_remove",
                             f"{txt!r} 应触发 idea_remove")
            self.assertEqual(kw["id"], expect_id)

    # -- 优先级 --
    def test_idea_save_not_swallowed_by_custom_idea(self):
        """「存 idea: XX」必须先匹配 idea_save · 不能被「写 XX / 选题: XX」截胡。"""
        action, kw = self._classify("存 idea: claude design 的某个技巧")
        self.assertEqual(action, "idea_save")
        self.assertNotEqual(action, "custom_idea")
        self.assertNotEqual(action, "tutorial_idea")


if __name__ == "__main__":
    unittest.main(verbosity=2)
