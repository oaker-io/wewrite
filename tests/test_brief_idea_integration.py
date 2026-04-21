"""阶段 D · brief × idea 库 集成测试。

覆盖:
  1. brief 把 idea 库 Top N 未用项追加到 topics(from='idea' / idea_id 字段)
  2. brief 在 idea 库为空时不报错 · 不显示 idea 段
  3. write idx 模式 · 从 topic 自动推断 style(from='idea' + tutorial → tutorial)
  4. write 写完(idea 来源)→ 调 _idea_bank.mark_used
  5. bot._classify_intent · 1-9 数字 pick(briefed 状态)

测试隔离:
  - WEWRITE_IDEA_BANK 环境变量指向 tmpdir · 不动真实库
  - session.yaml 用 backup/restore 模式

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_brief_idea_integration -v
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / "scripts" / "workflow"

sys.path.insert(0, str(WORKFLOW_DIR))
sys.path.insert(0, str(REPO_ROOT / "discord-bot"))


# =================================================================
# helper · 隔离 idea bank + session.yaml
# =================================================================
class _IsolatedFsMixin:
    """tmpdir + 备份-恢复 真实 session.yaml。"""

    def setUp(self):
        # idea bank → tmpdir 全新文件
        self._tmpdir = tempfile.mkdtemp(prefix="wewrite-d-")
        self._bank_file = Path(self._tmpdir) / "idea_bank.yaml"
        self._prev_env = os.environ.get("WEWRITE_IDEA_BANK")
        os.environ["WEWRITE_IDEA_BANK"] = str(self._bank_file)

        # session.yaml 备份
        self._session_file = REPO_ROOT / "output" / "session.yaml"
        self._session_backup = None
        if self._session_file.exists():
            self._session_backup = self._session_file.read_text(encoding="utf-8")

        # 测试结束时要清的临时 md 文件 (write 测试会创建)
        self._created_files: list[Path] = []

        # 强制 reload 涉及 _idea_bank / _state 的模块 · 让新 env 生效
        for mod in ("_idea_bank", "_state", "brief", "write"):
            sys.modules.pop(mod, None)

    def tearDown(self):
        # 还 env
        if self._prev_env is None:
            os.environ.pop("WEWRITE_IDEA_BANK", None)
        else:
            os.environ["WEWRITE_IDEA_BANK"] = self._prev_env
        # 还 session.yaml
        if self._session_file.exists():
            self._session_file.unlink()
        if self._session_backup is not None:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            self._session_file.write_text(self._session_backup, encoding="utf-8")
        # 清理测试期创建的 md 文件
        for f in self._created_files:
            f.unlink(missing_ok=True)
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# =================================================================
# 1. TestBriefAppendsIdeas · brief 拉 idea 后 topics 含 from='idea'
# =================================================================
class TestBriefAppendsIdeas(_IsolatedFsMixin, unittest.TestCase):
    def test_fetch_idea_topics_returns_normalized_dicts(self):
        """fetch_idea_topics 把 idea 库记录转成跟 hotspot 同结构。"""
        import _idea_bank
        _idea_bank.add("教程 A", category="tutorial", priority=80)
        _idea_bank.add("热点 B", category="hotspot", priority=90)
        _idea_bank.add("flex C", category="flexible", priority=50)

        import brief
        topics = brief.fetch_idea_topics(limit=3)
        self.assertEqual(len(topics), 3)
        for t in topics:
            self.assertEqual(t["from"], "idea")
            self.assertIsNotNone(t["idea_id"])
            self.assertIn("title", t)
            self.assertIn("category", t)
            self.assertIn(t["category"], ("tutorial", "hotspot", "flexible"))
        # 排序 · 高 priority 在前(_idea_bank 排序行为)
        titles = [t["title"] for t in topics]
        self.assertEqual(titles[0], "热点 B")  # priority 90 最高

    def test_brief_main_appends_ideas_to_topics(self):
        """模拟跑 brief.main · topics 应含热点 + idea 标 from='idea'。"""
        import _idea_bank
        _idea_bank.add("教程 idea Top", category="tutorial", priority=99)
        _idea_bank.add("flex idea 2", category="flexible", priority=10)

        import brief

        fake_hotspots = [
            {"title": "Claude 4.7 发布", "source": "微博", "hot_normalized": 80,
             "url": "http://x"},
            {"title": "ChatGPT 新功能", "source": "知乎", "hot_normalized": 70,
             "url": "http://y"},
        ]

        with mock.patch.object(brief, "fetch_hotspots", return_value=fake_hotspots), \
             mock.patch.object(brief, "push", return_value=None) as mock_push:
            rc = brief.main()

        self.assertEqual(rc, 0)
        # 验 session 写入
        import _state
        s = _state.load()
        self.assertEqual(s["state"], "briefed")
        topics = s["topics"]
        # 热点(2) + idea(2) = 4
        self.assertGreaterEqual(len(topics), 3)
        # 热点段 · from='hotspot' / idea_id=None
        hotspots = [t for t in topics if t.get("from") == "hotspot"]
        self.assertGreaterEqual(len(hotspots), 1)
        for h in hotspots:
            self.assertIsNone(h.get("idea_id"))
        # idea 段 · from='idea' / idea_id 是 int
        ideas = [t for t in topics if t.get("from") == "idea"]
        self.assertEqual(len(ideas), 2)
        for i in ideas:
            self.assertIsInstance(i.get("idea_id"), int)
            self.assertIn("category", i)

        # push 消息含 idea 段 marker
        sent = mock_push.call_args[0][0]
        self.assertIn("📌", sent)
        self.assertIn("idea 库", sent)
        self.assertIn("idea_id", sent)


# =================================================================
# 2. TestBriefEmptyIdeaBank · idea 库空时不报错 · 不追加 idea 段
# =================================================================
class TestBriefEmptyIdeaBank(_IsolatedFsMixin, unittest.TestCase):
    def test_brief_empty_bank_does_not_show_idea_section(self):
        # 不 add 任何 idea
        import brief

        fake_hotspots = [
            {"title": "AI Coding 最新进展", "source": "微博", "hot_normalized": 60,
             "url": "http://z"},
        ]
        with mock.patch.object(brief, "fetch_hotspots", return_value=fake_hotspots), \
             mock.patch.object(brief, "push", return_value=None) as mock_push:
            rc = brief.main()

        self.assertEqual(rc, 0)
        # 推送消息不应含 idea 段标记
        sent = mock_push.call_args[0][0]
        self.assertNotIn("idea 库", sent)
        self.assertNotIn("📌", sent)
        # 但热点段应在
        self.assertIn("🔥", sent)

    def test_format_message_idea_count_zero_omits_section(self):
        """单元 · idea_count=0 时格式化输出不含 idea 标识。"""
        import brief
        topics = [{
            "title": "测试", "source": "x", "hot": 10, "score": 50,
            "ai_kw": "AI", "from": "hotspot", "idea_id": None,
        }]
        stats = {"total": 10, "ai_matched": 1, "robot_in_pool": 0}
        msg = brief.format_message(topics, stats, idea_count=0)
        self.assertNotIn("idea 库", msg)
        self.assertNotIn("📌", msg)
        self.assertIn("🔥", msg)


# =================================================================
# 3. TestWriteAutoStyleFromIdea · idea + tutorial → 强制 tutorial
# =================================================================
class TestWriteAutoStyleFromIdea(_IsolatedFsMixin, unittest.TestCase):
    def test_auto_style_from_idea_tutorial(self):
        import write
        topic = {"title": "x", "from": "idea", "category": "tutorial", "idea_id": 5}
        self.assertEqual(write._auto_style_from_topic(topic, "hotspot"), "tutorial")
        self.assertEqual(write._auto_style_from_topic(topic, "tutorial"), "tutorial")

    def test_auto_style_from_idea_hotspot(self):
        import write
        topic = {"title": "x", "from": "idea", "category": "hotspot", "idea_id": 6}
        self.assertEqual(write._auto_style_from_topic(topic, "tutorial"), "hotspot")

    def test_auto_style_from_idea_flexible_uses_cli(self):
        import write
        topic = {"title": "x", "from": "idea", "category": "flexible", "idea_id": 7}
        self.assertEqual(write._auto_style_from_topic(topic, "hotspot"), "hotspot")
        self.assertEqual(write._auto_style_from_topic(topic, "tutorial"), "tutorial")

    def test_auto_style_from_hotspot_uses_cli(self):
        import write
        topic = {"title": "x", "from": "hotspot", "idea_id": None}
        self.assertEqual(write._auto_style_from_topic(topic, "hotspot"), "hotspot")
        self.assertEqual(write._auto_style_from_topic(topic, "tutorial"), "tutorial")

    def test_auto_style_missing_from_field_uses_cli(self):
        """老 session(没 from 字段) · 应该走 cli_style 兜底,不能崩。"""
        import write
        topic = {"title": "legacy"}
        self.assertEqual(write._auto_style_from_topic(topic, "hotspot"), "hotspot")
        self.assertEqual(write._auto_style_from_topic(topic, "tutorial"), "tutorial")

    def test_write_idx_with_idea_tutorial_calls_tutorial_prompt(self):
        """走 write.main · idx 选 idea tutorial · 应用 tutorial prompt 路径。

        策略:patch run_claude_write 拦截 style 入参 + patch push_article 跳过推送。
        """
        import _idea_bank, _state, write

        rec = _idea_bank.add("Step-by-Step Cursor 教程", category="tutorial",
                             priority=80)

        # 写一份 briefed session,topics 里只放这条 idea
        topic = {
            "title": rec["title"],
            "source": "idea 库",
            "hot": 0,
            "score": 80,
            "ai_kw": "idea",
            "url": "",
            "from": "idea",
            "idea_id": rec["id"],
            "category": "tutorial",
        }
        _state.advance("briefed", article_date="2026-04-21",
                       topics=[topic], selected_idx=None)

        # 假 stdout · 让 claude 调用看起来成功
        captured = {}

        def fake_run_claude(t, ds, op, style="hotspot"):
            captured["style"] = style
            captured["topic"] = t
            # 模拟写出 md 文件 · 记下来 tearDown 清掉
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_text("# x\n\n正文\n", encoding="utf-8")
            self._created_files.append(op)
            return "DONE " + str(op)

        with mock.patch.object(write, "run_claude_write", side_effect=fake_run_claude), \
             mock.patch.object(write, "push_article", return_value=None), \
             mock.patch.object(sys, "argv", ["write.py", "0"]):
            rc = write.main()

        self.assertEqual(rc, 0)
        # 关键断言:即便命令行没传 --style · idea+tutorial 也强制走 tutorial prompt
        self.assertEqual(captured["style"], "tutorial")


# =================================================================
# 4. TestWriteMarksIdeaUsedAfterWrite · 写完调 mark_used
# =================================================================
class TestWriteMarksIdeaUsedAfterWrite(_IsolatedFsMixin, unittest.TestCase):
    def test_idea_marked_used_after_successful_write(self):
        import _idea_bank, _state, write
        rec = _idea_bank.add("某 idea 标题", category="flexible", priority=60)
        self.assertFalse(rec["used"])

        topic = {
            "title": rec["title"],
            "source": "idea 库",
            "hot": 0, "score": 60, "ai_kw": "idea", "url": "",
            "from": "idea",
            "idea_id": rec["id"],
            "category": "flexible",
        }
        _state.advance("briefed", article_date="2026-04-21",
                       topics=[topic], selected_idx=None)

        def fake_run_claude(t, ds, op, style="hotspot"):
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_text("# x\n", encoding="utf-8")
            self._created_files.append(op)
            return "ok"

        with mock.patch.object(write, "run_claude_write", side_effect=fake_run_claude), \
             mock.patch.object(write, "push_article", return_value=None), \
             mock.patch.object(sys, "argv", ["write.py", "0"]):
            rc = write.main()
        self.assertEqual(rc, 0)

        # 验证 mark_used 已生效
        # 重新 import 强制重读
        sys.modules.pop("_idea_bank", None)
        import _idea_bank as fresh
        again = fresh.get(rec["id"])
        self.assertTrue(again["used"])
        self.assertIsNotNone(again["used_at"])
        self.assertIsNotNone(again["used_article_md"])

    def test_hotspot_topic_does_not_mark_anything(self):
        """hotspot topic 写完不应触碰 idea bank。"""
        import _idea_bank, _state, write
        rec = _idea_bank.add("不该被标的 idea", category="flexible")

        topic = {
            "title": "某 AI 热点", "source": "微博",
            "hot": 80, "score": 70, "ai_kw": "AI", "url": "",
            "from": "hotspot", "idea_id": None,
        }
        _state.advance("briefed", article_date="2026-04-21",
                       topics=[topic], selected_idx=None)

        def fake_run_claude(t, ds, op, style="hotspot"):
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_text("# x\n", encoding="utf-8")
            self._created_files.append(op)
            return "ok"

        with mock.patch.object(write, "run_claude_write", side_effect=fake_run_claude), \
             mock.patch.object(write, "push_article", return_value=None), \
             mock.patch.object(sys, "argv", ["write.py", "0"]):
            rc = write.main()
        self.assertEqual(rc, 0)

        sys.modules.pop("_idea_bank", None)
        import _idea_bank as fresh
        again = fresh.get(rec["id"])
        self.assertFalse(again["used"])  # 仍未用


# =================================================================
# 5. TestBotNumberPickExtendedTo9 · 1-9 都能命中 write_idx
# =================================================================
class TestBotNumberPickExtendedTo9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DISCORD_BOT_TOKEN", "dummy")
        os.environ.setdefault("WEWRITE_DIR", str(REPO_ROOT))
        try:
            sys.modules.pop("bot", None)
            cls.bot = importlib.import_module("bot")
        except Exception as e:
            raise unittest.SkipTest(f"bot module import failed: {e}")

    def _clf(self, text, state):
        return self.bot._classify_intent(text, state)

    def test_all_digits_1_to_9_route_to_write_idx(self):
        """1-9 都应该在 briefed 状态命中 write_idx · idx = N-1。"""
        for n in range(1, 10):
            action, kw = self._clf(str(n), "briefed")
            self.assertEqual(
                action, "write_idx",
                f"数字 {n} 应该路由到 write_idx · 实得 {action}",
            )
            self.assertEqual(kw["idx"], n - 1)

    def test_select_prefix_forms_for_6_to_9(self):
        """「选 6」/「第 7」/「选9」/「第8个」等变体也命中。"""
        for n in range(6, 10):
            for txt in (f"选{n}", f"第{n}", f"第{n}个"):
                action, kw = self._clf(txt, "briefed")
                self.assertEqual(action, "write_idx",
                                 f"{txt!r} 应路由 write_idx")
                self.assertEqual(kw["idx"], n - 1)

    def test_old_1_to_5_still_works(self):
        """阶段 D 不能破坏既有的 1-5 行为。"""
        for n in range(1, 6):
            action, kw = self._clf(str(n), "briefed")
            self.assertEqual(action, "write_idx")
            self.assertEqual(kw["idx"], n - 1)

    def test_digit_outside_briefed_state_not_routed(self):
        """只 briefed 状态才路由 number pick。"""
        for state in ("idle", "wrote", "imaged", "done"):
            action, _ = self._clf("3", state)
            self.assertNotEqual(action, "write_idx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
