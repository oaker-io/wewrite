"""analyze_kol.py 测试 · 4 层 metadata 抽取。

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_analyze_kol -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def _old_iso(days: int) -> str:
    return (datetime.now(CST) - timedelta(days=days)).isoformat(timespec="seconds")


class TestExtractHook(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_first_paragraph_extracted(self):
        md = "## 标题\n\n第一段是钩子。\n\n第二段。"
        self.assertEqual(self.ak.extract_hook(md), "第一段是钩子。")

    def test_skips_h1_h2(self):
        md = "# H1\n## H2\n\n真正的开头。"
        self.assertEqual(self.ak.extract_hook(md), "真正的开头。")

    def test_skips_image(self):
        md = "![cover](img.png)\n\n这才是首段。"
        self.assertEqual(self.ak.extract_hook(md), "这才是首段。")

    def test_truncates_at_80(self):
        long = "这是一段很长的文字" * 20
        out = self.ak.extract_hook(long)
        self.assertLessEqual(len(out), 80)

    def test_empty_returns_empty(self):
        self.assertEqual(self.ak.extract_hook(""), "")
        self.assertEqual(self.ak.extract_hook("## 只标题"), "")


class TestExtractKeywords(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_chinese_words_extracted(self):
        kw = self.ak.extract_keywords("Cursor 估值 500 亿 · 反共识")
        self.assertIn("Cursor", kw)
        self.assertIn("反共识", kw)

    def test_stopwords_filtered(self):
        kw = self.ak.extract_keywords("我们今天聊聊 Cursor")
        self.assertNotIn("我们", kw)
        self.assertNotIn("今天", kw)

    def test_top_n_limit(self):
        text = "Cursor Cursor Cursor Claude Claude Gemini"
        kw = self.ak.extract_keywords(text, top_n=2)
        self.assertEqual(len(kw), 2)
        self.assertEqual(kw[0], "Cursor")  # 出现最多


class TestAnalyzeStructure(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_h2_count(self):
        md = "## A\n\ntext\n\n## B\n\ntext"
        s = self.ak.analyze_structure(md)
        self.assertEqual(s["h2_count"], 2)

    def test_paragraph_count(self):
        md = "段一。\n\n段二。\n\n段三。"
        s = self.ak.analyze_structure(md)
        self.assertEqual(s["paragraph_count"], 3)

    def test_image_count(self):
        md = "正文\n\n![](a.png)\n\n更多正文\n\n![alt](b.png)"
        s = self.ak.analyze_structure(md)
        self.assertEqual(s["image_count"], 2)

    def test_avg_para_chars(self):
        md = "1234567890\n\n1234567890\n\n1234567890"
        s = self.ak.analyze_structure(md)
        self.assertEqual(s["avg_para_chars"], 10)

    def test_empty_md_returns_zeros(self):
        s = self.ak.analyze_structure("")
        self.assertEqual(s["h2_count"], 0)
        self.assertEqual(s["paragraph_count"], 0)


class TestAnalyzeStyle(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_emoji_count(self):
        md = "🔥 火 💡 灯 📈 涨"
        s = self.ak.analyze_style(md)
        self.assertGreaterEqual(s["emoji_count"], 3)

    def test_bold_count(self):
        md = "正文 **关键** 更多 **重点**"
        s = self.ak.analyze_style(md)
        self.assertEqual(s["bold_count"], 2)

    def test_number_count(self):
        md = "Cursor 估值 500 亿 · 用户 100 万 · 增长 20%"
        s = self.ak.analyze_style(md)
        self.assertGreaterEqual(s["number_count"], 3)

    def test_per_100_normalized(self):
        # 100 字内有 5 个 emoji → emoji_per_100 = 5.0
        md = "🔥" * 5 + "x" * 95
        s = self.ak.analyze_style(md)
        # 注意 emoji 是多字节 · 直接长度=100 + emoji
        self.assertGreater(s["emoji_per_100"], 0)


class TestFilterRecent(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_recent_articles_kept(self):
        articles = [
            {"title": "新", "fetched_at": _now_iso()},
            {"title": "旧", "fetched_at": _old_iso(10)},
        ]
        out = self.ak.filter_recent(articles, days=7)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "新")

    def test_invalid_iso_skipped(self):
        articles = [{"title": "a", "fetched_at": "not-iso"}]
        out = self.ak.filter_recent(articles, days=7)
        self.assertEqual(len(out), 0)


class TestAggregate(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol

    def test_aggregate_produces_top_hooks(self):
        per = [
            self.ak.analyze_one({
                "kol": "K1", "title": "T1", "weight": 90,
                "url": "https://x/1",
                "content_md": "## H\n\n钩子 1\n\n更多。",
                "fetched_at": _now_iso(),
            }),
            self.ak.analyze_one({
                "kol": "K2", "title": "T2", "weight": 70,
                "url": "https://x/2",
                "content_md": "## H\n\n钩子 2\n\n更多。",
                "fetched_at": _now_iso(),
            }),
        ]
        result = self.ak.aggregate(per)
        self.assertEqual(result["total_articles"], 2)
        self.assertEqual(len(result["top_hooks"]), 2)
        # 按 weight 排 · K1 应在前
        self.assertEqual(result["top_hooks"][0]["kol"], "K1")
        # structural_norms 存在
        self.assertIn("median_h2_count", result["structural_norms"])

    def test_aggregate_empty(self):
        self.assertEqual(self.ak.aggregate([]), {})


class TestEndToEnd(unittest.TestCase):
    """完整流程:写 corpus → 跑 main → 校验 patterns.yaml。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="ana-kol-")
        self._corpus = Path(self._tmpdir) / "kol_corpus.yaml"
        self._patterns = Path(self._tmpdir) / "kol_patterns.yaml"
        sys.modules.pop("analyze_kol", None)
        import analyze_kol
        self.ak = analyze_kol
        self.ak.KOL_CORPUS = self._corpus
        self.ak.KOL_PATTERNS = self._patterns

    def tearDown(self):
        sys.modules.pop("analyze_kol", None)

    def test_main_writes_patterns_yaml(self):
        import yaml
        corpus = {
            "articles": [
                {
                    "kol": "刘润", "title": "5 个商业洞察",
                    "url": "https://x/a",
                    "weight": 90,
                    "tags": ["商业"],
                    "content_md": "## 框架\n\n核心钩子在这。\n\n更多 100 万 内容!!",
                    "fetched_at": _now_iso(),
                    "pub_date": "2026-04-25",
                },
            ],
        }
        self._corpus.write_text(
            yaml.safe_dump(corpus, allow_unicode=True), encoding="utf-8",
        )
        with mock.patch.object(self.ak, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["analyze_kol.py", "--no-push"]):
            rc = self.ak.main()
        self.assertEqual(rc, 0)
        self.assertTrue(self._patterns.exists())
        data = yaml.safe_load(self._patterns.read_text(encoding="utf-8"))
        self.assertEqual(data["total_articles"], 1)
        self.assertEqual(data["top_hooks"][0]["kol"], "刘润")
        self.assertEqual(data["top_hooks"][0]["hook"], "核心钩子在这。")


if __name__ == "__main__":
    unittest.main()
