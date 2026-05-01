"""sync_from_xhs.py 测试 · xhs publish 事件 → wewrite idea_bank。

跑法:
  venv/bin/python3 -m unittest tests.test_sync_from_xhs -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


class TestFindNewPublishEvents(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("sync_from_xhs", None)
        import sync_from_xhs
        self.sx = sync_from_xhs

    def test_filters_only_publish_done(self):
        events = [
            {"agent": "images", "kind": "generated", "ts": "2026-04-25T01:00:00+00:00"},
            {"agent": "publish", "kind": "failed", "ts": "2026-04-25T02:00:00+00:00"},
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T03:00:00+00:00", "title": "A"},
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T04:00:00+00:00", "title": "B"},
        ]
        new = self.sx.find_new_publish_events(events, last_ts=None)
        self.assertEqual(len(new), 2)
        self.assertEqual(new[0]["title"], "A")
        self.assertEqual(new[1]["title"], "B")

    def test_dedupes_via_last_ts(self):
        events = [
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T03:00:00+00:00", "title": "A"},
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T04:00:00+00:00", "title": "B"},
        ]
        new = self.sx.find_new_publish_events(events, last_ts="2026-04-25T03:00:00+00:00")
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["title"], "B")

    def test_skips_publish_done_without_title(self):
        events = [
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T03:00:00+00:00"},
        ]
        new = self.sx.find_new_publish_events(events, last_ts=None)
        self.assertEqual(len(new), 0)


class TestEndToEnd(unittest.TestCase):
    """完整流程:写 events.jsonl → 跑 main → 校验 idea_bank + sync state。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="xhs-sync-")
        self._events = Path(self._tmpdir) / "events.jsonl"
        self._sync_state = Path(self._tmpdir) / "xhs_sync_state.yaml"
        self._bank = Path(self._tmpdir) / "idea_bank.yaml"

        self._prev_bank = os.environ.get("WEWRITE_IDEA_BANK")
        os.environ["WEWRITE_IDEA_BANK"] = str(self._bank)
        for mod in ("_idea_bank", "sync_from_xhs"):
            sys.modules.pop(mod, None)
        import sync_from_xhs
        self.sx = sync_from_xhs
        self.sx.XHS_EVENTS = self._events
        self.sx.SYNC_STATE = self._sync_state

    def tearDown(self):
        if self._prev_bank is None:
            os.environ.pop("WEWRITE_IDEA_BANK", None)
        else:
            os.environ["WEWRITE_IDEA_BANK"] = self._prev_bank
        sys.modules.pop("_idea_bank", None)
        sys.modules.pop("sync_from_xhs", None)

    def _write_events(self, lines: list[dict]) -> None:
        self._events.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in lines) + "\n",
            encoding="utf-8",
        )

    def test_first_run_imports_all_publish_done(self):
        self._write_events([
            {"agent": "images", "kind": "generated", "ts": "2026-04-25T01:00:00+00:00"},
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T05:00:00+00:00",
             "title": "GPT-5.5 上线", "images": 6},
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T06:00:00+00:00",
             "title": "Cursor 估值真相", "images": 5},
        ])

        with mock.patch.object(self.sx, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["sync_from_xhs.py", "--no-push"]):
            rc = self.sx.main()

        self.assertEqual(rc, 0)
        # idea_bank 应有 2 条
        import yaml
        bank = yaml.safe_load(self._bank.read_text(encoding="utf-8"))
        self.assertEqual(len(bank["ideas"]), 2)
        self.assertEqual(bank["ideas"][0]["title"], "GPT-5.5 上线")
        self.assertEqual(bank["ideas"][0]["source"], "xhs")
        self.assertEqual(bank["ideas"][0]["priority"], 80)
        # sync state 应有 last_ts 等于最新 event
        state = yaml.safe_load(self._sync_state.read_text(encoding="utf-8"))
        self.assertEqual(state["last_processed_ts"], "2026-04-25T06:00:00+00:00")

    def test_second_run_skips_already_processed(self):
        self._write_events([
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T05:00:00+00:00",
             "title": "A", "images": 6},
        ])
        with mock.patch.object(self.sx, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["sync_from_xhs.py", "--no-push"]):
            self.sx.main()

        # 第二次跑同 events · 应该全跳
        sys.modules.pop("sync_from_xhs", None)
        sys.modules.pop("_idea_bank", None)
        import sync_from_xhs as sx2
        sx2.XHS_EVENTS = self._events
        sx2.SYNC_STATE = self._sync_state
        with mock.patch.object(sx2, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["sync_from_xhs.py", "--no-push"]):
            sx2.main()

        import yaml
        bank = yaml.safe_load(self._bank.read_text(encoding="utf-8"))
        self.assertEqual(len(bank["ideas"]), 1)  # 还是 1 · 没增

    def test_no_xhs_events_file_returns_zero(self):
        # events.jsonl 不存在
        if self._events.exists():
            self._events.unlink()
        with mock.patch.object(self.sx, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["sync_from_xhs.py", "--no-push"]):
            rc = self.sx.main()
        self.assertEqual(rc, 0)

    def test_dry_run_does_not_write_state(self):
        self._write_events([
            {"agent": "publish", "kind": "done", "ts": "2026-04-25T05:00:00+00:00",
             "title": "A", "images": 6},
        ])
        with mock.patch.object(self.sx, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["sync_from_xhs.py", "--dry-run", "--no-push"]):
            self.sx.main()
        # state 文件不该被写
        self.assertFalse(self._sync_state.exists())


if __name__ == "__main__":
    unittest.main()
