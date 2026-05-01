"""tests for _topic_guard · 7 大主题守门 · 2026-04-26 锁。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))

from _topic_guard import (  # noqa: E402
    THEMES_7, classify_topic, is_ai_topic, reject_reason,
)


class TestIsAITopic(unittest.TestCase):

    def test_accept_real_evaluation(self):
        self.assertTrue(is_ai_topic("我用 Claude Opus 4.7 跑了 5 个 task · 速度比 4.6 快 30%"))

    def test_accept_skill_practice(self):
        self.assertTrue(is_ai_topic("我跑了 3 个月 Claude Skills · 这 3 个真改变了工作流"))

    def test_accept_pitfall(self):
        self.assertTrue(is_ai_topic("用 Claude 写代码踩了 5 个坑 · 教训复盘"))

    def test_accept_money(self):
        self.assertTrue(is_ai_topic("我用 Claude 月入 3 万的拆解"))

    def test_accept_tutorial(self):
        self.assertTrue(is_ai_topic("5 分钟用 GPT 做海报"))

    def test_accept_startup(self):
        self.assertTrue(is_ai_topic("Day 0 到 Day 30 用 AI 搭建 SaaS"))

    def test_accept_review(self):
        self.assertTrue(is_ai_topic("Cursor 实测 30 天 · 比 Copilot 强在哪"))

    def test_reject_news_release(self):
        self.assertFalse(is_ai_topic("刚刚 Claude Opus 4.7 发布了!三个变化"))
        self.assertIn("新闻", reject_reason("刚刚 Claude Opus 4.7 发布了!三个变化") or "")

    def test_reject_news_valuation(self):
        self.assertFalse(is_ai_topic("Cursor 估值 100 亿背后 3 个真相"))

    def test_reject_news_breaking(self):
        self.assertFalse(is_ai_topic("GPT-5 重磅发布 · 速看"))

    def test_reject_no_ai(self):
        self.assertFalse(is_ai_topic("男人一定要外向 · 越社牛越好"))
        self.assertFalse(is_ai_topic("40 岁副业月入 3w · 读书是最好的对冲"))

    def test_reject_emotional_chicken_soup(self):
        self.assertFalse(is_ai_topic("跟伴侣倾诉委屈 · 对方反应不是心疼"))

    def test_reject_health(self):
        self.assertFalse(is_ai_topic("AI 时代如何修身养性"))

    def test_reject_crypto(self):
        self.assertFalse(is_ai_topic("用 AI 玩比特币矿池"))

    def test_summary_can_save(self):
        # 标题没 AI · 但摘要有 → 接受
        self.assertTrue(is_ai_topic(
            "5 分钟跑通这个新工具",
            "用 Claude Code 一行命令搞定",
        ))

    def test_news_can_be_saved_by_substance(self):
        # 命中 news 词「发布」但有「实测」赦免词 → 接受
        self.assertTrue(is_ai_topic("Claude 4.7 发布速看 · 我实测了一晚上"))


class TestClassify(unittest.TestCase):

    def test_pitfall_first(self):
        self.assertEqual(classify_topic("Claude 写代码 5 个坑"), "AI 踩坑")

    def test_money(self):
        self.assertEqual(classify_topic("用 GPT 月入 3 万"), "AI 赚钱")

    def test_startup(self):
        self.assertEqual(classify_topic("Day 0 到 Day 30 用 AI 搭建 SaaS · 0 到 1 创业"), "AI 创业")

    def test_review(self):
        self.assertEqual(classify_topic("Cursor 实测 30 天"), "AI 真实测评")

    def test_tutorial(self):
        self.assertEqual(classify_topic("5 分钟用 GPT 做海报"), "AI 教程")

    def test_insight(self):
        self.assertEqual(classify_topic("AI 时代你该怎么活 · 我的 3 个反思"), "AI 感悟")

    def test_default_dry_goods(self):
        self.assertEqual(classify_topic("Claude Skills 工作流改造"), "AI 干货")

    def test_reject_returns_none(self):
        self.assertIsNone(classify_topic("男人外向社牛"))
        self.assertIsNone(classify_topic("Claude 4.7 重磅发布速看"))

    def test_themes_count(self):
        self.assertEqual(len(THEMES_7), 7)
        self.assertIn("AI 干货", THEMES_7)
        self.assertIn("AI 踩坑", THEMES_7)
        self.assertNotIn("AI 咨询", THEMES_7)  # 旧主题已删
        self.assertNotIn("AI 新闻", THEMES_7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
