"""publisher.create_draft_bundle + create_draft 评论开关 测试。

跑法:
  venv/bin/python3 -m unittest tests.test_publish_bundle -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "toolkit"))


class TestBuildArticleDict(unittest.TestCase):
    def setUp(self):
        if "publisher" in sys.modules:
            del sys.modules["publisher"]
        import publisher
        self.pub = publisher

    def test_default_open_comment_true(self):
        a = self.pub._build_article_dict("T", "<p>x</p>", "d")
        self.assertEqual(a["need_open_comment"], 1)
        self.assertEqual(a["only_fans_can_comment"], 0)

    def test_explicit_close_comment(self):
        a = self.pub._build_article_dict("T", "x", "d", open_comment=False)
        self.assertEqual(a["need_open_comment"], 0)

    def test_fans_only(self):
        a = self.pub._build_article_dict("T", "x", "d", fans_only_comment=True)
        self.assertEqual(a["only_fans_can_comment"], 1)

    def test_thumb_optional(self):
        a = self.pub._build_article_dict("T", "x", "d")
        self.assertNotIn("thumb_media_id", a)
        b = self.pub._build_article_dict("T", "x", "d", thumb_media_id="abc123")
        self.assertEqual(b["thumb_media_id"], "abc123")


class TestCreateDraftBundle(unittest.TestCase):
    def setUp(self):
        if "publisher" in sys.modules:
            del sys.modules["publisher"]
        import publisher
        self.pub = publisher

    def _make_articles(self, n: int) -> list[dict]:
        return [
            {"title": f"T{i}", "html": f"<p>body {i}</p>", "digest": f"d{i}"}
            for i in range(n)
        ]

    def test_empty_articles_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.pub.create_draft_bundle("token", [])
        self.assertIn("至少 1 篇", str(ctx.exception))

    def test_too_many_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.pub.create_draft_bundle("token", self._make_articles(9))
        self.assertIn("最多 8 篇", str(ctx.exception))

    def test_missing_required_field_raises(self):
        bad = [{"title": "T", "html": "x"}]  # 缺 digest
        with self.assertRaises(ValueError) as ctx:
            self.pub.create_draft_bundle("token", bad)
        self.assertIn("缺 title/html/digest", str(ctx.exception))

    def test_success_single_article(self):
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"media_id": "media-abc"}
            r = self.pub.create_draft_bundle("token", self._make_articles(1))
            self.assertEqual(r.media_id, "media-abc")
            # 验证 body articles 数组长 1
            kwargs = mp.call_args.kwargs
            body = json.loads(kwargs["data"].decode("utf-8"))
            self.assertEqual(len(body["articles"]), 1)
            self.assertEqual(body["articles"][0]["need_open_comment"], 1)

    def test_success_bundle_5(self):
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"media_id": "bundle-xyz"}
            r = self.pub.create_draft_bundle("token", self._make_articles(5))
            self.assertEqual(r.media_id, "bundle-xyz")
            kwargs = mp.call_args.kwargs
            body = json.loads(kwargs["data"].decode("utf-8"))
            self.assertEqual(len(body["articles"]), 5)
            # 全部默认开评论
            for a in body["articles"]:
                self.assertEqual(a["need_open_comment"], 1)

    def test_per_article_comment_override(self):
        articles = self._make_articles(2)
        articles[0]["open_comment"] = False  # 主推关评论
        articles[1]["fans_only_comment"] = True  # 副推只粉丝
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"media_id": "x"}
            self.pub.create_draft_bundle("token", articles)
            body = json.loads(mp.call_args.kwargs["data"].decode("utf-8"))
            self.assertEqual(body["articles"][0]["need_open_comment"], 0)
            self.assertEqual(body["articles"][1]["only_fans_can_comment"], 1)

    def test_api_error_raises(self):
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"errcode": 40001, "errmsg": "invalid token"}
            with self.assertRaises(ValueError) as ctx:
                self.pub.create_draft_bundle("token", self._make_articles(2))
            self.assertIn("40001", str(ctx.exception))
            self.assertIn("n_articles=2", str(ctx.exception))


class TestCreateDraftCommentDefaults(unittest.TestCase):
    """create_draft 默认开评论 + 接受 fans_only 参数。"""

    def setUp(self):
        if "publisher" in sys.modules:
            del sys.modules["publisher"]
        import publisher
        self.pub = publisher

    def test_default_open_comment_passed_to_api(self):
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"media_id": "x"}
            self.pub.create_draft("token", "T", "<p>x</p>", "d")
            body = json.loads(mp.call_args.kwargs["data"].decode("utf-8"))
            self.assertEqual(body["articles"][0]["need_open_comment"], 1)
            self.assertEqual(body["articles"][0]["only_fans_can_comment"], 0)

    def test_close_comment(self):
        with mock.patch.object(self.pub.requests, "post") as mp:
            mp.return_value.json.return_value = {"media_id": "x"}
            self.pub.create_draft("token", "T", "x", "d", open_comment=False)
            body = json.loads(mp.call_args.kwargs["data"].decode("utf-8"))
            self.assertEqual(body["articles"][0]["need_open_comment"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
