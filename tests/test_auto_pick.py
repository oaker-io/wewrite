"""auto_pick 测试 · 选题路由 + idea fallback。

跑法:
  venv/bin/python3 -m unittest tests.test_auto_pick -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestSelectIdeas(unittest.TestCase):
    """select_ideas · 主 category 缺时走 fallback · 都缺走 any。"""

    def setUp(self):
        # 用临时 idea_bank 隔离
        self._tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
        self._tmp.close()
        os.environ["WEWRITE_IDEA_BANK"] = self._tmp.name
        # 重新 import 让 auto_pick 拿到新 path
        for mod in ("auto_pick", "_idea_bank"):
            if mod in sys.modules:
                del sys.modules[mod]
        import _idea_bank  # noqa: F401
        import auto_pick
        self.ap = auto_pick
        self.bank = _idea_bank

    def tearDown(self):
        os.environ.pop("WEWRITE_IDEA_BANK", None)
        try:
            os.unlink(self._tmp.name)
        except FileNotFoundError:
            pass

    def test_returns_primary_when_category_has_ideas(self):
        # 标题需含 AI 关键词才能过 _topic_guard.is_ai_topic 守门(2026-04-26 加)
        self.bank.add("Claude 教程", category="tutorial")
        ideas, used = self.ap.select_ideas("tutorial", "flexible")
        self.assertEqual(len(ideas), 1)
        self.assertEqual(used, "tutorial")

    def test_falls_back_when_category_empty(self):
        self.bank.add("AI 灵感", category="flexible")
        ideas, used = self.ap.select_ideas("tutorial", "flexible")
        self.assertEqual(len(ideas), 1)
        self.assertEqual(used, "flexible")

    def test_returns_empty_when_all_empty(self):
        # allow_fetch=False · 跳过 fetch_changelog 兜底(避免单测真去抓 GitHub)
        ideas, used = self.ap.select_ideas("tutorial", "flexible", allow_fetch=False)
        self.assertEqual(ideas, [])
        self.assertEqual(used, "")

    def test_filters_non_ai_topics(self):
        """新加 · 验证非 AI 题被守门拦下。"""
        self.bank.add("男人外向社牛", category="flexible")  # 非 AI
        self.bank.add("Claude 干货", category="flexible")   # AI
        ideas, used = self.ap.select_ideas("flexible", "tutorial", allow_fetch=False)
        self.assertEqual(len(ideas), 1)
        self.assertEqual(ideas[0]["title"], "Claude 干货")


class TestPickForWeekday(unittest.TestCase):
    """pick_for_weekday · 找不到 weekday 用第一项。"""

    def setUp(self):
        for mod in ("auto_pick",):
            if mod in sys.modules:
                del sys.modules[mod]
        import auto_pick
        self.ap = auto_pick

    def test_finds_matching_weekday(self):
        cfg = {"schedule": [
            {"weekday": 0, "label": "周一"},
            {"weekday": 2, "label": "周三"},
        ]}
        item = self.ap.pick_for_weekday(cfg, 2)
        self.assertEqual(item["label"], "周三")

    def test_falls_back_to_first_when_missing(self):
        cfg = {"schedule": [{"weekday": 0, "label": "周一"}]}
        item = self.ap.pick_for_weekday(cfg, 5)
        self.assertEqual(item["label"], "周一")

    def test_raises_when_no_schedule(self):
        with self.assertRaises(ValueError):
            self.ap.pick_for_weekday({"schedule": []}, 0)


class TestToTopic(unittest.TestCase):
    """to_topic · idea 库记录 → session topic 同结构。"""

    def setUp(self):
        for mod in ("auto_pick",):
            if mod in sys.modules:
                del sys.modules[mod]
        import auto_pick
        self.ap = auto_pick

    def test_basic_fields(self):
        idea = {
            "id": 7,
            "title": "Test 主题",
            "priority": 60,
            "category": "tutorial",
        }
        t = self.ap.to_topic(idea, "tutorial")
        self.assertEqual(t["title"], "Test 主题")
        self.assertEqual(t["from"], "idea")
        self.assertEqual(t["idea_id"], 7)
        self.assertEqual(t["category"], "tutorial")
        self.assertEqual(t["score"], 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
