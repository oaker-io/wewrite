"""测试 sanitize · _add_utm_to_aipickgold(2026-04-23 加)。

跑法:
  venv/bin/python3 -m unittest tests.test_sanitize_utm -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "toolkit"))


class TestUtmAdd(unittest.TestCase):
    def setUp(self):
        if "sanitize" in sys.modules:
            del sys.modules["sanitize"]
        import sanitize
        self.s = sanitize

    def test_adds_utm_to_plain_link(self):
        md = "看这个 https://aipickgold.com 工具"
        out = self.s._add_utm_to_aipickgold(md, date_str="2026-04-23")
        self.assertIn("utm_source=mp", out)
        self.assertIn("utm_date=2026-04-23", out)

    def test_does_not_add_when_already_present(self):
        md = "https://aipickgold.com/?utm_source=existing"
        out = self.s._add_utm_to_aipickgold(md, date_str="2026-04-23")
        self.assertNotIn("utm_source=mp", out)
        self.assertIn("utm_source=existing", out)

    def test_appends_with_amp_when_query_exists(self):
        md = "https://aipickgold.com/?ref=mp"
        out = self.s._add_utm_to_aipickgold(md, date_str="2026-04-23")
        self.assertIn("ref=mp&utm_source=mp", out)

    def test_handles_path_and_query(self):
        md = "https://aipickgold.com/api/convert?lang=zh"
        out = self.s._add_utm_to_aipickgold(md, date_str="2026-04-23")
        self.assertIn("lang=zh&utm_source=mp", out)
        self.assertIn("/api/convert?", out)

    def test_works_inside_markdown_link(self):
        md = "[试试](https://aipickgold.com)"
        out = self.s._add_utm_to_aipickgold(md, date_str="2026-04-23")
        # 注意:正则会把 ) 之前的部分都吃进去 · 验证 ) 之外不动
        self.assertIn("utm_source=mp", out)

    def test_sanitize_for_publish_includes_utm(self):
        md = (
            "正文段。\n\n"
            "工具链接 https://aipickgold.com\n\n"
            ":::author-card\nname: 智辰老师\nmp_brand: x\n:::\n"
        )
        out = self.s.sanitize_for_publish(md)
        self.assertIn("utm_source=mp", out)
        self.assertIn("utm_date=", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
