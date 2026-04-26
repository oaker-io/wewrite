"""tests for series_picker · 系列调度。"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))


class TestSeriesPicker(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="series-")
        self.config = Path(self.tmp) / "series.yaml"
        # 1 个到期 + 1 个未到期 + 1 个已发完
        today = date.today().isoformat()
        future = (date.today() + timedelta(days=10)).isoformat()
        data = {
            "version": 1,
            "series": [
                {
                    "id": "due-now",
                    "name": "Due 系列",
                    "theme": "AI 干货",
                    "cadence_days": 2,
                    "total": 5,
                    "published": 0,
                    "next_due": today,
                    "topic_queue": ["第 1 篇", "第 2 篇", "第 3 篇"],
                },
                {
                    "id": "future",
                    "name": "Future 系列",
                    "theme": "AI 教程",
                    "cadence_days": 3,
                    "total": 10,
                    "published": 0,
                    "next_due": future,
                    "topic_queue": ["未到期"],
                },
                {
                    "id": "done",
                    "name": "Done 系列",
                    "theme": "AI 赚钱",
                    "cadence_days": 1,
                    "total": 3,
                    "published": 3,
                    "next_due": today,
                    "topic_queue": [],
                },
            ],
        }
        self.config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

        # 切换 SERIES_FILE
        import series_picker
        self._orig_file = series_picker.SERIES_FILE
        series_picker.SERIES_FILE = self.config
        self.sp = series_picker

    def tearDown(self):
        self.sp.SERIES_FILE = self._orig_file
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pick_returns_due_series(self):
        pick = self.sp.pick_due_today(dry_run=True)
        self.assertIsNotNone(pick)
        self.assertEqual(pick["series_id"], "due-now")
        self.assertEqual(pick["title"], "第 1 篇")
        self.assertEqual(pick["episode"], 1)
        self.assertEqual(pick["theme"], "AI 干货")

    def test_pick_advances_queue(self):
        pick1 = self.sp.pick_due_today()
        self.assertEqual(pick1["title"], "第 1 篇")

        # 模拟下一个周期到期
        data = yaml.safe_load(self.config.read_text(encoding="utf-8"))
        data["series"][0]["next_due"] = date.today().isoformat()  # 强制再到期
        self.config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

        pick2 = self.sp.pick_due_today()
        self.assertEqual(pick2["title"], "第 2 篇")
        self.assertEqual(pick2["episode"], 2)

    def test_pick_skips_done_series(self):
        # 把 due-now 推进到完成 + 让 future 也到期
        data = yaml.safe_load(self.config.read_text(encoding="utf-8"))
        data["series"][0]["published"] = data["series"][0]["total"]
        data["series"][1]["next_due"] = date.today().isoformat()
        self.config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

        pick = self.sp.pick_due_today(dry_run=True)
        self.assertEqual(pick["series_id"], "future")

    def test_no_due_returns_none(self):
        # 把所有都推到未来
        data = yaml.safe_load(self.config.read_text(encoding="utf-8"))
        future = (date.today() + timedelta(days=30)).isoformat()
        for s in data["series"]:
            s["next_due"] = future
            s["published"] = 0
        self.config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

        pick = self.sp.pick_due_today()
        self.assertIsNone(pick)

    def test_status_lists_all(self):
        statuses = self.sp.list_series_status()
        self.assertEqual(len(statuses), 3)
        names = {s["name"] for s in statuses}
        self.assertIn("Due 系列", names)
        self.assertIn("Future 系列", names)


class TestStateDateReset(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="state-")
        self._sess = Path(self.tmp) / "session.yaml"
        self._orig = os.environ.get("WEWRITE_SESSION_FILE")
        os.environ["WEWRITE_SESSION_FILE"] = str(self._sess)
        # 强制 reload _state(它在 import 时读 env)
        import _state
        import importlib
        importlib.reload(_state)
        self.s = _state

    def tearDown(self):
        if self._orig:
            os.environ["WEWRITE_SESSION_FILE"] = self._orig
        else:
            del os.environ["WEWRITE_SESSION_FILE"]
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        import _state, importlib
        importlib.reload(_state)

    def test_reset_if_stale_yesterday_done(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.s.save({"state": "done", "article_date": yesterday})
        self.assertTrue(self.s.reset_if_stale())
        self.assertEqual(self.s.load().get("state"), "idle")

    def test_reset_if_stale_today_done_also_resets(self):
        # 今天 done 也允许 reset(允许补发)
        self.s.save({"state": "done", "article_date": date.today().isoformat()})
        self.assertTrue(self.s.reset_if_stale())
        self.assertEqual(self.s.load().get("state"), "idle")

    def test_no_reset_when_today_active(self):
        self.s.save({"state": "briefed", "article_date": date.today().isoformat()})
        self.assertFalse(self.s.reset_if_stale())
        self.assertEqual(self.s.load().get("state"), "briefed")

    def test_no_reset_when_idle(self):
        self.s.save({"state": "idle"})
        self.assertFalse(self.s.reset_if_stale())

    def test_is_today_published(self):
        today = date.today().isoformat()
        self.s.save({"state": "done", "article_date": today, "draft_media_id": "abc"})
        self.assertTrue(self.s.is_today_published())
        # 没 media_id
        self.s.save({"state": "done", "article_date": today, "draft_media_id": ""})
        self.assertFalse(self.s.is_today_published())


if __name__ == "__main__":
    unittest.main(verbosity=2)
