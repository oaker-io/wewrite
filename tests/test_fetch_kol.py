"""fetch_kol.py 测试 · RSS 抓取 + 去重 + idea_bank 入库。

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_fetch_kol -v
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
sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))

CST = timezone(timedelta(hours=8))


def _fake_entry(title: str, link: str, *, published: str = "2026-04-25") -> dict:
    """模拟 feedparser entry。"""
    return {
        "title": title,
        "link": link,
        "published": published,
        "summary": f"{title} 的摘要 ...",
    }


class _IsolatedFs:
    """测试 fixture · idea_bank + corpus + kol_list 都走 tmpdir。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="fetch-kol-")
        self._bank = Path(self._tmpdir) / "idea_bank.yaml"
        self._kol_list = Path(self._tmpdir) / "kol_list.yaml"
        self._corpus = Path(self._tmpdir) / "kol_corpus.yaml"

        self._prev_bank = os.environ.get("WEWRITE_IDEA_BANK")
        os.environ["WEWRITE_IDEA_BANK"] = str(self._bank)

        for mod in ("_idea_bank", "fetch_kol"):
            sys.modules.pop(mod, None)
        import fetch_kol
        self.fk = fetch_kol
        # 让 fetch_kol 的全局路径走 tmpdir
        self.fk.KOL_LIST = self._kol_list
        self.fk.KOL_CORPUS = self._corpus

    def tearDown(self):
        if self._prev_bank is None:
            os.environ.pop("WEWRITE_IDEA_BANK", None)
        else:
            os.environ["WEWRITE_IDEA_BANK"] = self._prev_bank
        sys.modules.pop("_idea_bank", None)
        sys.modules.pop("fetch_kol", None)


class TestFingerprint(unittest.TestCase):
    """指纹去重的稳定性。"""
    def setUp(self):
        sys.modules.pop("fetch_kol", None)
        import fetch_kol
        self.fk = fetch_kol

    def test_same_url_title_same_fingerprint(self):
        a = self.fk._fingerprint("https://x.com/a", "Hello")
        b = self.fk._fingerprint("https://x.com/a", "Hello")
        self.assertEqual(a, b)

    def test_diff_url_diff_fingerprint(self):
        a = self.fk._fingerprint("https://x.com/a", "Hello")
        b = self.fk._fingerprint("https://x.com/b", "Hello")
        self.assertNotEqual(a, b)


class TestKolCategory(unittest.TestCase):
    """KOL.tags → idea_bank category 映射。"""
    def setUp(self):
        sys.modules.pop("fetch_kol", None)
        import fetch_kol
        self.fk = fetch_kol

    def test_business_tag_maps_to_flexible(self):
        cat = self.fk._kol_category({"tags": ["商业", "案例"]})
        self.assertEqual(cat, "flexible")

    def test_ai_tool_tag_maps_to_tutorial(self):
        cat = self.fk._kol_category({"tags": ["AI 工具", "实战"]})
        self.assertEqual(cat, "tutorial")

    def test_unknown_tag_falls_back_to_flexible(self):
        cat = self.fk._kol_category({"tags": ["奇怪标签"]})
        self.assertEqual(cat, "flexible")

    def test_no_tags_falls_back(self):
        cat = self.fk._kol_category({})
        self.assertEqual(cat, "flexible")


class TestEndToEndFetch(_IsolatedFs, unittest.TestCase):
    """完整流程:KOL list → mock RSS → corpus + idea_bank。"""

    def _write_kol_list(self, kols: list[dict]) -> None:
        import yaml
        data = {
            "list": kols,
            "fetch": {
                "daily_limit_per_kol": 5,
                "dedupe_window_days": 30,
            },
        }
        self._kol_list.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_fetch_inserts_into_corpus_and_idea_bank(self):
        self._write_kol_list([{
            "name": "Test KOL",
            "handle": "test_kol",
            "biz_name": "MzITEST",
            "rss_url": "http://localhost:4000/feeds/MzITEST.rss",
            "status": "active",
            "weight": 75,
            "tags": ["商业", "案例"],
        }])

        fake_entries = [
            _fake_entry("文章 A", "https://mp.weixin.qq.com/s/a"),
            _fake_entry("文章 B", "https://mp.weixin.qq.com/s/b"),
        ]
        with mock.patch.object(self.fk, "fetch_rss", return_value=fake_entries), \
             mock.patch.object(self.fk, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["fetch_kol.py", "--no-push"]):
            rc = self.fk.main()

        self.assertEqual(rc, 0)
        # corpus 应有 2 条
        import yaml
        corpus = yaml.safe_load(self._corpus.read_text(encoding="utf-8"))
        self.assertEqual(len(corpus["articles"]), 2)
        self.assertEqual(corpus["articles"][0]["kol"], "Test KOL")
        # idea_bank 应有 2 条 · category=flexible(商业 → flexible) · source=kol
        bank = yaml.safe_load(self._bank.read_text(encoding="utf-8"))
        self.assertEqual(len(bank["ideas"]), 2)
        self.assertEqual(bank["ideas"][0]["category"], "flexible")
        self.assertEqual(bank["ideas"][0]["source"], "kol")
        self.assertEqual(bank["ideas"][0]["priority"], 75)

    def test_dedupe_skips_existing_articles(self):
        self._write_kol_list([{
            "name": "K",
            "handle": "k",
            "biz_name": "M",
            "rss_url": "http://x.com/rss",
            "status": "active",
            "weight": 50,
            "tags": ["AI 工具"],
        }])
        fake = [_fake_entry("Same Title", "https://x.com/s/same")]

        # 第一次跑 · 入库
        with mock.patch.object(self.fk, "fetch_rss", return_value=fake), \
             mock.patch.object(self.fk, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["fetch_kol.py", "--no-push"]):
            self.fk.main()

        # 第二次跑同 entry · 应该全去重
        sys.modules.pop("fetch_kol", None)
        sys.modules.pop("_idea_bank", None)
        import fetch_kol as fk2
        fk2.KOL_LIST = self._kol_list
        fk2.KOL_CORPUS = self._corpus
        with mock.patch.object(fk2, "fetch_rss", return_value=fake), \
             mock.patch.object(fk2, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["fetch_kol.py", "--no-push"]):
            fk2.main()

        import yaml
        corpus = yaml.safe_load(self._corpus.read_text(encoding="utf-8"))
        self.assertEqual(len(corpus["articles"]), 1)  # 还是 1 条 · 没增
        bank = yaml.safe_load(self._bank.read_text(encoding="utf-8"))
        self.assertEqual(len(bank["ideas"]), 1)

    def test_no_active_kols_returns_quietly(self):
        self._write_kol_list([{
            "name": "Pending",
            "handle": "p",
            "rss_url": "",
            "status": "pending",
            "weight": 50,
            "tags": [],
        }])
        with mock.patch.object(self.fk, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["fetch_kol.py", "--no-push"]):
            rc = self.fk.main()
        self.assertEqual(rc, 0)

    def test_dry_run_does_not_write(self):
        self._write_kol_list([{
            "name": "K",
            "handle": "k",
            "rss_url": "http://x.com/rss",
            "status": "active",
            "weight": 50,
            "tags": ["AI 工具"],
        }])
        fake = [_fake_entry("dry run title", "https://x.com/dry")]
        with mock.patch.object(self.fk, "fetch_rss", return_value=fake), \
             mock.patch.object(self.fk, "push_discord", return_value=None), \
             mock.patch.object(sys, "argv", ["fetch_kol.py", "--dry-run", "--no-push"]):
            self.fk.main()

        # corpus 文件不应被写
        self.assertFalse(self._corpus.exists())
        # idea_bank 也不应被写(只 add 调用真写 · dry-run 不调)
        # 注意:bank 文件可能在 setUp 没动过 · 这里检查没 idea
        if self._bank.exists():
            import yaml
            data = yaml.safe_load(self._bank.read_text(encoding="utf-8"))
            self.assertEqual(len(data.get("ideas") or []), 0)


if __name__ == "__main__":
    unittest.main()
