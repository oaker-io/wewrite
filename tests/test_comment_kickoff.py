"""comment_kickoff · 模板渲染 + style 路由 + keyword 抽取 测试。

跑法:
  venv/bin/python3 -m unittest tests.test_comment_kickoff -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestKeywordExtract(unittest.TestCase):
    def setUp(self):
        if "comment_kickoff" in sys.modules:
            del sys.modules["comment_kickoff"]
        import comment_kickoff
        self.ck = comment_kickoff

    def test_extracts_english_product_name(self):
        self.assertEqual(self.ck._extract_keyword("Cursor 30 天复盘"), "Cursor")
        self.assertEqual(self.ck._extract_keyword("Claude Code 完整 SOP"), "Claude")

    def test_skips_common_short_words(self):
        # "Day" / "How" 应被跳过
        kw = self.ck._extract_keyword("Day 30 复盘 Cursor")
        self.assertEqual(kw, "Cursor")

    def test_falls_back_to_chinese(self):
        kw = self.ck._extract_keyword("如何用提示词工程做内容")
        # 应抽 chinese 第一段前 4 字
        self.assertEqual(kw, "如何用提")

    def test_default_AI_when_no_match(self):
        # 真的什么都没 · fallback "AI"(只有标点)
        kw = self.ck._extract_keyword("· · ·")
        self.assertEqual(kw, "AI")


class TestPickTemplates(unittest.TestCase):
    def setUp(self):
        if "comment_kickoff" in sys.modules:
            del sys.modules["comment_kickoff"]
        import comment_kickoff
        self.ck = comment_kickoff

    def test_tutorial_picks_AC(self):
        self.assertEqual(self.ck._pick_templates("tutorial", None), ["A", "C"])

    def test_case_picks_AD(self):
        self.assertEqual(self.ck._pick_templates("case", None), ["A", "D"])

    def test_hotspot_picks_EB(self):
        self.assertEqual(self.ck._pick_templates("hotspot", None), ["E", "B"])

    def test_unknown_falls_back_AB(self):
        self.assertEqual(self.ck._pick_templates("xxxxx", None), ["A", "B"])

    def test_override_filters_invalid(self):
        # X / Z 不存在 · 应被过滤 · 只留 A
        out = self.ck._pick_templates("tutorial", ["A", "X", "Z"])
        self.assertEqual(out, ["A"])

    def test_override_caps_at_3(self):
        out = self.ck._pick_templates("tutorial", ["A", "B", "C", "D", "E"])
        self.assertEqual(len(out), 3)


class TestRenderTemplate(unittest.TestCase):
    def setUp(self):
        if "comment_kickoff" in sys.modules:
            del sys.modules["comment_kickoff"]
        import comment_kickoff
        self.ck = comment_kickoff

    def test_render_A_substitutes_series(self):
        out = self.ck._render_template("A", series="干货教程", keyword="Cursor")
        self.assertIn("干货教程", out)
        self.assertIn("【下篇预告】", out)

    def test_render_B_substitutes_keyword(self):
        out = self.ck._render_template("B", series="x", keyword="Claude")
        self.assertIn("Claude", out)
        self.assertIn("最大的坑", out)

    def test_render_D_引流话术(self):
        out = self.ck._render_template("D", series="x", keyword="MCP")
        self.assertIn("MCP", out)
        self.assertIn("拉你进群", out)


class TestBuildMessage(unittest.TestCase):
    def setUp(self):
        if "comment_kickoff" in sys.modules:
            del sys.modules["comment_kickoff"]
        import comment_kickoff
        self.ck = comment_kickoff

    def test_message_includes_all_pieces(self):
        msg = self.ck.build_message(
            title="Test 文章", media_id="m_abc",
            series="案例复盘", keyword="Cursor",
            template_ids=["A", "D"],
        )
        self.assertIn("评论区 kickoff", msg)
        self.assertIn("Test 文章", msg)
        self.assertIn("m_abc", msg)
        self.assertIn("模板 A", msg)
        self.assertIn("模板 D", msg)
        self.assertIn("Cursor", msg)
        self.assertIn("自动回复速查", msg)
        self.assertIn("CES 算法", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
