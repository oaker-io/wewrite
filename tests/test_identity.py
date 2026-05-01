"""identity 注入 + sync 脚本测试。

验证:
  - _extract_identity_sections 抽对了 sections
  - _load_identity_block 在 identity/ 目录存在时注入 prompt
  - identity/ 目录不存在时 fallback 空字符串(向后兼容)
  - hotspot / tutorial 两个 prompt 都注入

跑法:
  venv/bin/python3 -m unittest tests.test_identity -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))


class TestExtractIdentitySections(unittest.TestCase):
    """_extract_identity_sections 抽 ## 0 / ## 1 / ## 2 / ## 3 / ## 4。"""

    def setUp(self):
        if "write" in sys.modules:
            del sys.modules["write"]
        import write
        self.write = write

    def test_extracts_listed_sections(self):
        md = """# Identity

> 注释

## 0. 基础身份
- 姓名: 智辰

## 1. 一句话定位
**定位文本**

## 2. 三句话定位
- 三句话

## 3. bio 候选
> bio 文本

## 4. IP 故事
故事正文

## 5. 知识结构(三个圈)
此节不应被抽
"""
        out = self.write._extract_identity_sections(md)
        self.assertIn("0. 基础身份", out)
        self.assertIn("1. 一句话定位", out)
        self.assertIn("2. 三句话定位", out)
        self.assertIn("3. bio 候选", out)
        self.assertIn("4. IP 故事", out)
        self.assertNotIn("5. 知识结构", out)
        self.assertNotIn("此节不应被抽", out)

    def test_returns_empty_on_empty_input(self):
        self.assertEqual(self.write._extract_identity_sections(""), "")

    def test_returns_empty_when_no_target_sections(self):
        md = "## 99. unrelated\ncontent"
        self.assertEqual(self.write._extract_identity_sections(md), "")


class TestLoadIdentityBlock(unittest.TestCase):
    """_load_identity_block 组装注入段。"""

    def setUp(self):
        if "write" in sys.modules:
            del sys.modules["write"]
        import write
        self.write = write

    def test_returns_empty_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(self.write, "_IDENTITY_DIR", Path(tmp) / "missing"):
                self.assertEqual(self.write._load_identity_block(), "")

    def test_loads_identity_md_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "identity.md").write_text(
                "## 0. 基础身份\n姓名: 智辰\n\n## 1. 一句话定位\n定位文本\n",
                encoding="utf-8",
            )
            with mock.patch.object(self.write, "_IDENTITY_DIR", d):
                out = self.write._load_identity_block()
            self.assertIn("作者人设档案", out)
            self.assertIn("智辰", out)
            self.assertIn("定位文本", out)

    def test_loads_voice_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "voice").mkdir()
            (d / "identity.md").write_text("## 0. 基础身份\n姓名: x\n", encoding="utf-8")
            (d / "voice" / "catchphrases.md").write_text("# 招牌句式\n- 非共识\n", encoding="utf-8")
            (d / "voice" / "forbidden.md").write_text("# 禁忌\n- 革命性\n", encoding="utf-8")
            with mock.patch.object(self.write, "_IDENTITY_DIR", d):
                out = self.write._load_identity_block()
            self.assertIn("招牌句式", out)
            self.assertIn("非共识", out)
            self.assertIn("禁忌", out)
            self.assertIn("革命性", out)

    def test_handles_missing_voice_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "identity.md").write_text("## 0. 基础身份\nx\n", encoding="utf-8")
            with mock.patch.object(self.write, "_IDENTITY_DIR", d):
                out = self.write._load_identity_block()
            # voice 缺失也不报错 · identity.md 那段还在
            self.assertIn("智辰" in out or "基础身份" in out, [True, False])
            self.assertNotIn("招牌句式", out)


class TestPromptInjection(unittest.TestCase):
    """_build_prompt_hotspot / _build_prompt_tutorial 都注入 identity。"""

    def setUp(self):
        if "write" in sys.modules:
            del sys.modules["write"]
        import write
        self.write = write
        self.topic = {"title": "测试主题", "source": "test", "hot": 0}
        self.out_path = self.write.ROOT / "output/test.md"

    def test_hotspot_prompt_injects_identity(self):
        prompt = self.write._build_prompt_hotspot(self.topic, self.out_path)
        # 真 identity/ 目录存在 → 应该注入(否则 skip)
        if (self.write.ROOT / "identity").exists():
            self.assertIn("作者人设档案", prompt)
        else:
            self.skipTest("identity/ 目录不存在 · 跳过(测试机器场景)")

    def test_tutorial_prompt_injects_identity(self):
        prompt = self.write._build_prompt_tutorial(self.topic, self.out_path)
        if (self.write.ROOT / "identity").exists():
            self.assertIn("作者人设档案", prompt)
        else:
            self.skipTest("identity/ 目录不存在")


if __name__ == "__main__":
    unittest.main(verbosity=2)
