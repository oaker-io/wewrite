"""测试 _build_prompt_case + _auto_style_from_topic 案例分支。

跑法:
  venv/bin/python3 -m unittest tests.test_case_prompt -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestBuildPromptCase(unittest.TestCase):
    def setUp(self):
        for mod in ("write",):
            if mod in sys.modules:
                del sys.modules[mod]
        import write
        self.write = write
        self.topic = {"title": "Cursor 30 天写完 SaaS"}
        self.out = REPO_ROOT / "output" / "test-case.md"

    def test_prompt_mentions_case_keywords(self):
        prompt = self.write._build_prompt_case(self.topic, self.out)
        self.assertIn("AI 真实成功案例", prompt)
        self.assertIn("第一人称", prompt)
        self.assertIn("具体数字", prompt)
        self.assertIn("Day 0", prompt)
        # 5 张图占位都要提到
        for name in ("cover.png", "chart-1.png", "chart-2.png", "chart-3.png", "chart-4.png"):
            self.assertIn(name, prompt)
        # 拒绝凑数
        self.assertIn("不像是凑出来的整数", prompt)

    def test_prompt_includes_identity(self):
        # identity 注入(若 identity/ 存在)
        prompt = self.write._build_prompt_case(self.topic, self.out)
        if (REPO_ROOT / "identity").exists():
            self.assertIn("作者人设档案", prompt)


class TestAutoStyleCase(unittest.TestCase):
    def setUp(self):
        if "write" in sys.modules:
            del sys.modules["write"]
        import write
        self.write = write

    def test_cli_case_overrides_idea_category(self):
        # idea category=tutorial 但 cli 传 case · 应该走 case
        topic = {"from": "idea", "category": "tutorial", "idea_id": 1}
        style = self.write._auto_style_from_topic(topic, "case")
        self.assertEqual(style, "case")

    def test_cli_tutorial_with_idea_tutorial_stays_tutorial(self):
        topic = {"from": "idea", "category": "tutorial", "idea_id": 1}
        style = self.write._auto_style_from_topic(topic, "tutorial")
        self.assertEqual(style, "tutorial")

    def test_cli_hotspot_with_idea_tutorial_overrides_to_tutorial(self):
        # 老逻辑保留:idea category 在 cli=hotspot 时仍优先(只有 case 才反向覆盖)
        topic = {"from": "idea", "category": "tutorial", "idea_id": 1}
        style = self.write._auto_style_from_topic(topic, "hotspot")
        self.assertEqual(style, "tutorial")


class TestImagesStyleResolve(unittest.TestCase):
    """images.py · _resolve_style 读 session.auto_schedule.image_style"""

    def setUp(self):
        if "images" in sys.modules:
            del sys.modules["images"]
        import images
        self.imgs = images

    def test_case_realistic_resolves_to_case(self):
        with unittest.mock.patch.object(self.imgs._state, "load",
                                          return_value={"auto_schedule": {"image_style": "case-realistic"}}):
            self.assertEqual(self.imgs._resolve_style("default"), "case")

    def test_default_when_no_session(self):
        with unittest.mock.patch.object(self.imgs._state, "load",
                                          return_value={}):
            self.assertEqual(self.imgs._resolve_style("default"), "default")


import unittest.mock  # noqa: E402


if __name__ == "__main__":
    unittest.main(verbosity=2)
