"""_state.advance 终态保护测试。

Why: 04-25 故障 · 旧 daily-brief 在 wrote 状态后又跑 brief.py,把 state 打回
briefed + article_md 清空,导致 images/review/publish 全 skip。该测试锁住 guard 行为。

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_state_guard -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestStateGuard(unittest.TestCase):
    """_state.advance 拒绝把 wrote/imaged/done 打回 briefed/idle。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="wewrite-state-")
        self._tmp_session = Path(self._tmpdir) / "session.yaml"
        self._prev_env = os.environ.get("WEWRITE_SESSION_FILE")
        os.environ["WEWRITE_SESSION_FILE"] = str(self._tmp_session)
        sys.modules.pop("_state", None)
        import _state
        self._state = _state

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("WEWRITE_SESSION_FILE", None)
        else:
            os.environ["WEWRITE_SESSION_FILE"] = self._prev_env
        sys.modules.pop("_state", None)

    # ── 正向链路:idle → briefed → wrote → imaged → done 全通 ──
    def test_forward_progression_works(self):
        s = self._state.advance(self._state.STATE_BRIEFED, topics=["t1"])
        self.assertEqual(s["state"], "briefed")
        s = self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        self.assertEqual(s["state"], "wrote")
        s = self._state.advance(self._state.STATE_IMAGED, images_dir="output/images")
        self.assertEqual(s["state"], "imaged")
        s = self._state.advance(self._state.STATE_DONE, draft_media_id="m1")
        self.assertEqual(s["state"], "done")

    # ── 关键:wrote → briefed 必须被拒 ──
    def test_wrote_to_briefed_refused(self):
        self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        with self.assertRaises(self._state.StateGuardError):
            self._state.advance(self._state.STATE_BRIEFED, topics=["new"])
        # 抛错后 session 仍是 wrote · article_md 没被吃
        s = self._state.load()
        self.assertEqual(s["state"], "wrote")
        self.assertEqual(s["article_md"], "a.md")

    def test_imaged_to_briefed_refused(self):
        self._state.advance(self._state.STATE_BRIEFED)
        self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        self._state.advance(self._state.STATE_IMAGED)
        with self.assertRaises(self._state.StateGuardError):
            self._state.advance(self._state.STATE_BRIEFED)

    def test_done_to_briefed_refused(self):
        self._state.advance(self._state.STATE_DONE, draft_media_id="m1")
        with self.assertRaises(self._state.StateGuardError):
            self._state.advance(self._state.STATE_BRIEFED)

    def test_wrote_to_idle_refused(self):
        self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        with self.assertRaises(self._state.StateGuardError):
            self._state.advance(self._state.STATE_IDLE)

    # ── force=True 可以绕过 ──
    def test_force_overrides_guard(self):
        self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        s = self._state.advance(self._state.STATE_BRIEFED, force=True, topics=["new"])
        self.assertEqual(s["state"], "briefed")

    # ── reset() 始终能用(用户显式说重来) ──
    def test_reset_always_works(self):
        self._state.advance(self._state.STATE_DONE, draft_media_id="m1")
        s = self._state.reset()
        self.assertEqual(s["state"], "idle")
        self.assertIsNone(s["article_md"])

    # ── 同状态自循环不被拒(advance(WROTE) → advance(WROTE) OK) ──
    def test_same_state_advance_ok(self):
        self._state.advance(self._state.STATE_WROTE, article_md="a.md")
        s = self._state.advance(self._state.STATE_WROTE, article_md="b.md")
        self.assertEqual(s["state"], "wrote")
        self.assertEqual(s["article_md"], "b.md")


if __name__ == "__main__":
    unittest.main()
