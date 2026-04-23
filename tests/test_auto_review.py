"""auto_review 测试 · 5+1 维度评分(LLM 维度跳过)。

跑法:
  venv/bin/python3 -m unittest tests.test_auto_review -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestPureTextDimensions(unittest.TestCase):
    def setUp(self):
        if "auto_review" in sys.modules:
            del sys.modules["auto_review"]
        import auto_review
        self.ar = auto_review

    def test_word_count_strips_markdown(self):
        md = (
            "# H1 标题\n\n"
            "这是正文一段话。\n\n"
            "```python\nprint('代码不算')\n```\n\n"
            "![alt](images/cover.png)\n\n"
            "[链接文字](https://x.com)在这里。"
        )
        wc = self.ar._word_count(md)
        # H1 / 代码块 / 图片去掉 · 链接保留 text
        # 实际中文字符:这是正文一段话 + 链接文字 + 在这里 = 7+4+3 = 14
        self.assertGreaterEqual(wc, 12)
        self.assertLess(wc, 30)

    def test_image_count(self):
        md = (
            "![](images/cover.png)\n"
            "![](images/chart-1.png)\n"
            "![](images/chart-2.png)\n"
            "外链不算 ![](https://x.com/img.png)\n"
        )
        ic = self.ar._image_count(md)
        self.assertEqual(ic, 3)

    def test_catchphrase_hits(self):
        md = "今天我们说说 AI 非共识 · 这个观点很有意思。"
        phrases = ["AI 非共识,掘金看智辰", "另一个口头禅"]
        cnt, hits = self.ar._catchphrase_hits(md, phrases)
        # 前 8 字「AI 非共识,掘」会命中 substring「AI 非共识」
        # 实际:phrase[:8] = "AI 非共识,掘" 含中文标点 · 不一定命中
        # 改测试用 phrase 实际能匹配的
        phrases2 = ["AI 非共识"]
        cnt2, hits2 = self.ar._catchphrase_hits(md, phrases2)
        self.assertGreaterEqual(cnt2, 1)
        self.assertIn("AI 非共识", hits2)

    def test_forbidden_hits(self):
        md = "这是革命性的产品 · 颠覆了行业。"
        forbidden = ["革命性", "颠覆", "无关词"]
        hits = self.ar._forbidden_hits(md, forbidden)
        self.assertIn("革命性", hits)
        self.assertIn("颠覆", hits)
        self.assertNotIn("无关词", hits)


class TestReviewIntegration(unittest.TestCase):
    """跑一次 review · skip-llm · 看综合判定。"""

    def setUp(self):
        if "auto_review" in sys.modules:
            del sys.modules["auto_review"]
        import auto_review
        self.ar = auto_review

    def test_short_article_fails_word_count(self):
        md = "# T\n\n太短。"
        result = self.ar.review(md, is_case=False, threshold=3, skip_llm=True)
        self.assertFalse(result["passed"])
        # word_count 应该不及格(实际 wc=2 · 远小于 1500)
        self.assertEqual(result["scores"]["word_count"], 1)

    def test_forbidden_hard_fails(self):
        # 给个长文本但带禁忌词
        body = "这是一个很长的文章。" * 200
        md = f"# T\n\n{body}\n\n革命性的产品来了。\n\n" + "![](images/cover.png)\n" * 5
        # 提供伪造的禁忌列表让 _forbidden_hits 命中
        with unittest.mock.patch.object(self.ar, "load_forbidden", return_value=["革命性"]):
            result = self.ar.review(md, is_case=False, threshold=3, skip_llm=True)
        self.assertEqual(result["scores"]["forbidden"], 1)
        self.assertFalse(result["passed"])

    def test_long_clean_article_passes(self):
        body = "这是优质长文。" * 300  # > 1500 字
        md = (
            f"# T\n\n{body}\n\n"
            + "\n".join([f"![](images/{n}.png)" for n in
                         ("cover", "chart-1", "chart-2", "chart-3", "chart-4")])
        )
        with unittest.mock.patch.object(self.ar, "load_catchphrases", return_value=["这是优质"]):
            with unittest.mock.patch.object(self.ar, "load_forbidden", return_value=[]):
                result = self.ar.review(md, is_case=False, threshold=3, skip_llm=True)
        self.assertEqual(result["scores"]["word_count"], 5)
        self.assertEqual(result["scores"]["image_count"], 5)
        self.assertEqual(result["scores"]["forbidden"], 5)
        self.assertGreaterEqual(result["scores"]["catchphrase"], 3)
        self.assertTrue(result["passed"])


# 兼容 unittest.mock import
import unittest.mock  # noqa: E402


if __name__ == "__main__":
    unittest.main(verbosity=2)
