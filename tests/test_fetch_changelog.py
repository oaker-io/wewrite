"""Tests for scripts/fetch_changelog.py · 3 个数据源 + 去重 + dry-run。

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_fetch_changelog -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
WORKFLOW_DIR = REPO_ROOT / "scripts" / "workflow"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(WORKFLOW_DIR))


# ============================================================
# Fixtures · static HTML 字符串
# ============================================================
ANTHROPIC_BLOG_HTML = """
<!DOCTYPE html>
<html><body>
  <main>
    <a href="/news/claude-4-7-launch">Introducing Claude 4.7 — smarter, faster</a>
    <a href="/news/research-collaboration">New research collaboration on alignment</a>
    <a href="/news/mcp-update">MCP gets official npm package support</a>
    <a href="/news">All news</a>
    <a href="/news/short">x</a>
    <a href="/careers">Careers</a>
  </main>
</body></html>
"""

ANTHROPIC_CHANGELOG_HTML = """
<!DOCTYPE html>
<html><body>
  <main>
    <h1>API release notes</h1>
    <h2>2026-04-15 · prompt caching for tool results</h2>
    <p>Cache tool result content for 5 minutes...</p>
    <h2>2026-04-08 · message batches API GA</h2>
    <p>Batch up to 10k requests for 50% off...</p>
    <h3>2026-04-01 · file uploads beta</h3>
    <p>Upload PDFs and reference them by id...</p>
    <h2>On this page</h2>
  </main>
</body></html>
"""

GITHUB_TRENDING_HTML = """
<!DOCTYPE html>
<html><body>
  <main>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/anthropics/claude-cookbook">claude-cookbook</a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">
        Recipes and demos for using Claude in production agents and RAG.
      </p>
      <span itemprop="programmingLanguage">Python</span>
    </article>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/some-org/css-framework">css-framework</a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">
        Atomic CSS framework for designers.
      </p>
      <span itemprop="programmingLanguage">CSS</span>
    </article>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/run-llama/agent-os">agent-os</a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">
        Operating system for LLM agents with tool use built in.
      </p>
      <span itemprop="programmingLanguage">TypeScript</span>
    </article>
  </main>
</body></html>
"""


# ============================================================
# helper · 隔离 idea_bank.yaml
# ============================================================
class _BankIsolationMixin:
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="wewrite-changelog-")
        self._bank_file = Path(self._tmpdir) / "idea_bank.yaml"
        self._prev_env = os.environ.get("WEWRITE_IDEA_BANK")
        os.environ["WEWRITE_IDEA_BANK"] = str(self._bank_file)
        # 强制 reload _idea_bank 和 fetch_changelog · 防跨测试缓存
        for mod in ("_idea_bank", "fetch_changelog"):
            if mod in sys.modules:
                del sys.modules[mod]
        import _idea_bank  # noqa: E402
        import fetch_changelog  # noqa: E402
        self._bank = _idea_bank
        self._fc = fetch_changelog

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("WEWRITE_IDEA_BANK", None)
        else:
            os.environ["WEWRITE_IDEA_BANK"] = self._prev_env
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


def _mock_get(html: str, status: int = 200):
    """生成一个返回固定 html 的 mock requests.get。"""
    def _fake(url, headers=None, timeout=None):
        m = mock.MagicMock()
        m.status_code = status
        m.text = html
        m.raise_for_status = mock.MagicMock()
        return m
    return _fake


# ============================================================
# 1. Source-level parsers
# ============================================================
class TestAnthropicBlog(_BankIsolationMixin, unittest.TestCase):
    def test_parses_at_least_one_news_item(self):
        with mock.patch("requests.get", side_effect=_mock_get(ANTHROPIC_BLOG_HTML)):
            items = self._fc.fetch_anthropic_blog(limit=5)
        self.assertGreaterEqual(len(items), 1)
        titles = [i["raw_title"] for i in items]
        # 取到了正经 news 链接
        self.assertTrue(any("Claude 4.7" in t for t in titles))
        # 跳过了 /news 自身和过短的 /news/short
        self.assertFalse(any(t.lower() == "all news" for t in titles))
        # 转化标题命中模板
        for i in items:
            self.assertTrue(i["transformed_title"].startswith("读懂 Anthropic"))

    def test_handles_http_failure(self):
        def _boom(*a, **kw):
            raise RuntimeError("network down")
        with mock.patch("requests.get", side_effect=_boom):
            items = self._fc.fetch_anthropic_blog(limit=5)
        self.assertEqual(items, [])


class TestAnthropicChangelog(_BankIsolationMixin, unittest.TestCase):
    def test_parses_at_least_one_entry(self):
        with mock.patch("requests.get", side_effect=_mock_get(ANTHROPIC_CHANGELOG_HTML)):
            items = self._fc.fetch_anthropic_changelog(limit=5)
        self.assertGreaterEqual(len(items), 1)
        # 跳过 "On this page"
        for i in items:
            self.assertNotIn("On this page", i["raw_title"])
            self.assertTrue(i["transformed_title"].startswith("Claude API 更新:"))


class TestGithubTrending(_BankIsolationMixin, unittest.TestCase):
    def test_parses_and_filters_ai_only(self):
        with mock.patch("requests.get", side_effect=_mock_get(GITHUB_TRENDING_HTML)):
            items = self._fc.fetch_github_trending(limit=10)
        repos = [i["repo"] for i in items]
        # AI 相关的 2 个进来
        self.assertIn("anthropics/claude-cookbook", repos)
        self.assertIn("run-llama/agent-os", repos)
        # CSS 框架被过滤
        self.assertNotIn("some-org/css-framework", repos)
        for i in items:
            self.assertTrue(i["transformed_title"].startswith("GitHub 今日热门 AI 项目:"))


# ============================================================
# 2. 去重
# ============================================================
class TestDedupe(_BankIsolationMixin, unittest.TestCase):
    def test_skips_existing_title_substring(self):
        # 预先塞一条几乎同 title
        self._bank.add("读懂 Anthropic 官方动态:Introducing Claude 4.7 — smarter, faster",
                       category="tutorial")
        before = len(self._bank.list_ideas(only_unused=False))

        with mock.patch("requests.get", side_effect=_mock_get(ANTHROPIC_BLOG_HTML)):
            stats = self._fc.run(source="anthropic-blog", limit=5, dry_run=False)

        # duplicates ≥ 1
        self.assertGreaterEqual(stats["duplicates"], 1)
        # 同名条目没有被重复添加
        all_after = self._bank.list_ideas(only_unused=False)
        c47_titles = [i for i in all_after if "Claude 4.7" in i["title"]]
        self.assertEqual(len(c47_titles), 1, msg=f"expected 1 Claude 4.7 entry, got {len(c47_titles)}: {[i['title'] for i in c47_titles]}")
        # 还应有其他新条目入库
        self.assertGreater(len(all_after), before)

    def test_is_duplicate_helper_substring_case_insensitive(self):
        existing = ["读懂 anthropic 官方动态:claude 4.7"]
        self.assertTrue(self._fc._is_duplicate(
            "读懂 Anthropic 官方动态:Claude 4.7", existing
        ))
        # 完全无关
        self.assertFalse(self._fc._is_duplicate(
            "GitHub 今日热门 AI 项目:foo/bar", existing
        ))


# ============================================================
# 3. dry-run
# ============================================================
class TestDryRun(_BankIsolationMixin, unittest.TestCase):
    def test_dry_run_does_not_write(self):
        before = len(self._bank.list_ideas(only_unused=False))
        with mock.patch("requests.get", side_effect=_mock_get(ANTHROPIC_BLOG_HTML)):
            stats = self._fc.run(source="anthropic-blog", limit=5, dry_run=True)
        # bank 没变
        after = len(self._bank.list_ideas(only_unused=False))
        self.assertEqual(after, before)
        # 但 stats 算了 added(规划值)
        self.assertGreater(stats["added"], 0)


# ============================================================
# 4. run() 容错 · 一个源失败不影响其他
# ============================================================
class TestRunFaultTolerance(_BankIsolationMixin, unittest.TestCase):
    def test_one_source_fails_others_still_work(self):
        # 只 mock 一个能成功的源(anthropic-blog) · 其他两个真实 fetch 但用一个会失败的 mock
        # 简化:让 requests.get 对 anthropic.com/news 返回 HTML · 其他 raise
        def _selective(url, headers=None, timeout=None):
            if "anthropic.com/news" in url:
                m = mock.MagicMock()
                m.text = ANTHROPIC_BLOG_HTML
                m.raise_for_status = mock.MagicMock()
                return m
            raise RuntimeError(f"forced fail for {url}")

        with mock.patch("requests.get", side_effect=_selective):
            stats = self._fc.run(source="all", limit=3, dry_run=True)

        # blog 有产出
        self.assertGreater(stats["fetched"], 0)
        # 其他两源失败也不抛
        self.assertIn("anthropic-changelog", stats["failed_sources"])
        self.assertIn("github-trending", stats["failed_sources"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
