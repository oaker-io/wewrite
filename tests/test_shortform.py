"""短文(副推位)+ mini author-card + cover-square 引用 测试。

跑法:
  venv/bin/python3 -m unittest tests.test_shortform -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))
sys.path.insert(0, str(REPO_ROOT / "toolkit"))


class TestBuildPromptShortform(unittest.TestCase):
    def setUp(self):
        for mod in ("write",):
            if mod in sys.modules:
                del sys.modules[mod]
        import write
        self.write = write
        self.topic = {"title": "Claude 4.7 价格变了"}
        self.out = REPO_ROOT / "output" / "test-shortform.md"

    def test_prompt_mentions_shortform_keywords(self):
        prompt = self.write._build_prompt_shortform(self.topic, self.out)
        self.assertIn("副推短文", prompt)
        self.assertIn("800-1500 字", prompt)
        self.assertIn("shortform-frameworks.md", prompt)
        self.assertIn("shortform-writer", prompt)

    def test_prompt_explicitly_forbids_long_form_things(self):
        prompt = self.write._build_prompt_shortform(self.topic, self.out)
        # 明确禁止
        self.assertIn("不要写", prompt)
        self.assertIn("cover.png", prompt)  # 提到不要写 cover
        # 不许写 chart-3 / chart-4
        self.assertIn("chart-3", prompt)
        self.assertIn("chart-4", prompt)

    def test_prompt_with_explicit_framework(self):
        prompt = self.write._build_prompt_shortform(
            self.topic, self.out, shortform_type="S2",
        )
        self.assertIn("强制使用框架", prompt)
        self.assertIn("S2", prompt)

    def test_style_shortform_routes_to_shortform_prompt(self):
        # 通过 _parse_argv 测试 --style shortform 是否被接受
        original_argv = sys.argv
        try:
            sys.argv = ["write.py", "--style", "shortform", "--idea", "Test"]
            idx, idea, style = self.write._parse_argv()
            self.assertEqual(style, "shortform")
        finally:
            sys.argv = original_argv


class TestSanitizeMiniCard(unittest.TestCase):
    def setUp(self):
        if "sanitize" in sys.modules:
            del sys.modules["sanitize"]
        import sanitize
        self.s = sanitize

    def test_default_full_card_when_long_form(self):
        md = "正文段。"
        out = self.s.sanitize_for_publish(md, shortform=False)
        # 完整卡有 bio + tags
        self.assertIn("bio:", out)
        self.assertIn("tags:", out)
        self.assertIn("openclaw 武汉创业群", out)

    def test_mini_card_when_shortform(self):
        md = "短文正文。\n\n你的看法?评论区。"
        out = self.s.sanitize_for_publish(md, shortform=True)
        # mini 卡 · 有 mp_brand 和 footer · 但没 bio + 复杂 tags
        self.assertIn("mp_brand: 宸的 AI 掘金笔记", out)
        self.assertIn("footer:", out)
        # 不应有完整版的 bio
        self.assertNotIn("不追热搜情绪", out)
        # 不应有 openclaw 群码字样(短文不放第二个 QR)
        self.assertNotIn("openclaw 武汉创业群", out)

    def test_prepare_for_publish_shortform_param(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("短文正文。")
            md_path = Path(f.name)
        try:
            out_path = self.s.prepare_for_publish(md_path, shortform=True)
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("mp_brand", content)
            self.assertNotIn("不追热搜情绪", content)
            # 清理临时副本
            if out_path != md_path and out_path.exists():
                out_path.unlink()
        finally:
            md_path.unlink(missing_ok=True)

    def test_mini_card_idempotent(self):
        md = "短文。"
        once = self.s.sanitize_for_publish(md, shortform=True)
        twice = self.s.sanitize_for_publish(once, shortform=True)
        self.assertEqual(once, twice)


class TestImagesShortformStyle(unittest.TestCase):
    def setUp(self):
        if "images" in sys.modules:
            del sys.modules["images"]
        import images
        self.imgs = images

    def test_resolve_style_shortform_explicit(self):
        with mock.patch.object(self.imgs._state, "load", return_value={}):
            self.assertEqual(self.imgs._resolve_style("shortform"), "shortform")

    def test_resolve_style_session_shortform(self):
        with mock.patch.object(self.imgs._state, "load",
                                  return_value={"auto_schedule": {"image_style": "shortform"}}):
            self.assertEqual(self.imgs._resolve_style("default"), "shortform")

    def test_shortform_prompt_constraints(self):
        out_path = REPO_ROOT / "output" / "test-short.md"
        prompt = self.imgs._build_prompt_shortform(out_path, "Claude 4.7 价格变了")
        self.assertIn("副推短文", prompt)
        self.assertIn("cover-square.png", prompt)
        self.assertIn("不生 cover.png", prompt)
        self.assertIn("只生 1-3 张图", prompt)
        self.assertIn("超过 chart-2 的占位忽略", prompt)


class TestPicpostFrameworks(unittest.TestCase):
    """picpost.py 框架清单 + slug + framework 范围。"""

    def setUp(self):
        if "picpost" in sys.modules:
            del sys.modules["picpost"]
        import picpost
        self.pp = picpost

    def test_frameworks_constants(self):
        self.assertIn("P1", self.pp.FRAMEWORKS)
        self.assertIn("P5", self.pp.FRAMEWORKS)
        self.assertIn("auto", self.pp.FRAMEWORKS)

    def test_framework_post_ranges(self):
        # P1 时间线 5-7 张
        self.assertEqual(self.pp.FRAMEWORK_POSTS["P1"], (5, 7))
        # P4 数据爆点 3-5(最少)
        self.assertEqual(self.pp.FRAMEWORK_POSTS["P4"], (3, 5))

    def test_slugify_handles_chinese(self):
        s = self.pp._slugify("30 天 Cursor 复盘")
        self.assertIn("cursor", s.lower())
        # 30 也应保留
        self.assertIn("30", s)

    def test_build_prompt_includes_framework_hint(self):
        out_dir = REPO_ROOT / "output" / "picpost" / "test"
        prompt = self.pp._build_prompt(
            "Test 主题", out_dir, "P1",
            companion_of=None, no_images=False,
        )
        self.assertIn("P1", prompt)
        self.assertIn("强制使用框架", prompt)
        self.assertIn("5-7", prompt)
        self.assertIn("picpost-frameworks.md", prompt)
        self.assertIn("caption-wechat.txt", prompt)
        self.assertIn("caption-xhs.txt", prompt)
        self.assertIn("meta.yaml", prompt)

    def test_build_prompt_companion_block(self):
        out_dir = REPO_ROOT / "output" / "picpost" / "test"
        # 用一个真实存在的文件 · README.md 一定在
        companion = REPO_ROOT / "CLAUDE.md"
        prompt = self.pp._build_prompt(
            "Test", out_dir, "P1",
            companion_of=companion, no_images=False,
        )
        self.assertIn("视觉伴生版", prompt)
        self.assertIn("CLAUDE.md", prompt)

    def test_build_prompt_no_images_mode(self):
        out_dir = REPO_ROOT / "output" / "picpost" / "test"
        prompt = self.pp._build_prompt(
            "Test", out_dir, "P5",
            companion_of=None, no_images=True,
        )
        self.assertIn("--no-images 模式", prompt)
        # caption + meta 仍要写
        self.assertIn("caption-wechat.txt", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
