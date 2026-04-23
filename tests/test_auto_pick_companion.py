"""auto_pick · 新版 schedule (main + companions) 解析测试。

跑法:
  venv/bin/python3 -m unittest tests.test_auto_pick_companion -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestNormalizeSchedule(unittest.TestCase):
    def setUp(self):
        for mod in ("auto_pick",):
            if mod in sys.modules:
                del sys.modules[mod]
        import auto_pick
        self.ap = auto_pick

    def test_new_format_passthrough(self):
        item = {
            "weekday": 2,
            "label": "周三",
            "main": {"category": "tutorial", "style": "case"},
            "companions": [{"type": "S3", "style": "shortform"}],
        }
        out = self.ap._normalize_schedule(item)
        self.assertEqual(out["main"]["style"], "case")
        self.assertEqual(len(out["companions"]), 1)
        self.assertEqual(out["companions"][0]["type"], "S3")

    def test_old_format_wrapped(self):
        item = {
            "weekday": 0,
            "label": "周一",
            "category": "tutorial",
            "style": "tutorial",
            "image_style": "mockup",
        }
        out = self.ap._normalize_schedule(item)
        self.assertEqual(out["main"]["category"], "tutorial")
        self.assertEqual(out["main"]["style"], "tutorial")
        self.assertEqual(out["main"]["image_style"], "mockup")
        self.assertEqual(out["companions"], [])

    def test_companions_default_empty_when_missing(self):
        item = {"main": {"category": "x"}}
        out = self.ap._normalize_schedule(item)
        self.assertEqual(out["companions"], [])


class TestPickForWeekdayNewFormat(unittest.TestCase):
    def setUp(self):
        for mod in ("auto_pick",):
            if mod in sys.modules:
                del sys.modules[mod]
        import auto_pick
        self.ap = auto_pick

    def test_picks_weekday_2_with_main_companions(self):
        cfg = {"schedule": [
            {
                "weekday": 2,
                "label": "周三",
                "main": {"category": "tutorial", "style": "case", "image_style": "case-realistic"},
                "companions": [{"type": "S3", "category": "tutorial", "style": "shortform"}],
            },
        ]}
        item = self.ap.pick_for_weekday(cfg, 2)
        self.assertEqual(item["main"]["style"], "case")
        self.assertEqual(item["main"]["image_style"], "case-realistic")
        self.assertEqual(len(item["companions"]), 1)
        self.assertEqual(item["companions"][0]["type"], "S3")


class TestPickCompanions(unittest.TestCase):
    def setUp(self):
        # 临时 idea_bank
        self._tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
        self._tmp.close()
        os.environ["WEWRITE_IDEA_BANK"] = self._tmp.name
        for mod in ("auto_pick", "_idea_bank"):
            if mod in sys.modules:
                del sys.modules[mod]
        import _idea_bank
        import auto_pick
        self.bank = _idea_bank
        self.ap = auto_pick

    def tearDown(self):
        os.environ.pop("WEWRITE_IDEA_BANK", None)
        try:
            os.unlink(self._tmp.name)
        except FileNotFoundError:
            pass

    def test_picks_companions_when_ideas_exist(self):
        self.bank.add("副推 idea 1", category="tutorial")
        self.bank.add("副推 idea 2", category="tutorial")
        comp_cfg = [
            {"type": "S2", "category": "tutorial", "fallback": "flexible", "style": "shortform"},
        ]
        out = self.ap._pick_companions(comp_cfg)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["topic"]["category"], "tutorial")
        self.assertEqual(out[0]["cfg"]["type"], "S2")

    def test_skips_when_no_ideas(self):
        # idea 库空 · companion 跳过(不报错)
        comp_cfg = [{"type": "S2", "category": "tutorial", "fallback": "flexible"}]
        out = self.ap._pick_companions(comp_cfg)
        self.assertEqual(out, [])

    def test_multiple_companions(self):
        self.bank.add("idea 1", category="tutorial")
        self.bank.add("idea 2", category="flexible")
        comp_cfg = [
            {"type": "S6", "category": "flexible", "style": "shortform"},
            {"type": "S4", "category": "flexible", "style": "shortform"},
        ]
        out = self.ap._pick_companions(comp_cfg)
        # 至少 1 个 (取决于 ideas 数 + 是否重复)
        self.assertGreaterEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
