"""check_poe_quota · 汇总 + 趋势 + 报告测试。

跑法:
  venv/bin/python3 -m unittest tests.test_check_poe_quota -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


class TestLoadQuota(unittest.TestCase):
    def setUp(self):
        if "check_poe_quota" in sys.modules:
            del sys.modules["check_poe_quota"]
        import check_poe_quota
        self.cq = check_poe_quota

    def test_returns_empty_when_missing(self):
        result = self.cq.load_quota(Path("/nonexistent/path/quota.json"))
        self.assertEqual(result, {})

    def test_returns_empty_on_corrupt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            tmp = Path(f.name)
        try:
            result = self.cq.load_quota(tmp)
            self.assertEqual(result, {})
        finally:
            tmp.unlink()

    def test_loads_valid(self):
        data = {"poe:2026-04-23": {"success": 5, "fail": 1}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp = Path(f.name)
        try:
            result = self.cq.load_quota(tmp)
            self.assertEqual(result, data)
        finally:
            tmp.unlink()


class TestParseKey(unittest.TestCase):
    def setUp(self):
        if "check_poe_quota" in sys.modules:
            del sys.modules["check_poe_quota"]
        import check_poe_quota
        self.cq = check_poe_quota

    def test_valid_key(self):
        out = self.cq._parse_key("poe:2026-04-23")
        self.assertEqual(out, ("poe", date(2026, 4, 23)))

    def test_no_colon(self):
        self.assertIsNone(self.cq._parse_key("invalid"))

    def test_bad_date(self):
        self.assertIsNone(self.cq._parse_key("poe:not-a-date"))


class TestAggregate(unittest.TestCase):
    def setUp(self):
        if "check_poe_quota" in sys.modules:
            del sys.modules["check_poe_quota"]
        import check_poe_quota
        self.cq = check_poe_quota
        self.today = date(2026, 4, 23)  # 周四
        # 上周一 = 2026-04-13 · 上周日 = 2026-04-19
        # 本周一 = 2026-04-20 · 周四 = 2026-04-23

    def test_today_bucket(self):
        quota = {
            f"poe:{self.today}": {"success": 6, "fail": 1},
            f"gemini:{self.today}": {"success": 0, "fail": 2},
        }
        agg = self.cq.aggregate(quota, today=self.today)
        self.assertEqual(agg["today"]["poe"], {"success": 6, "fail": 1})
        self.assertEqual(agg["today"]["gemini"], {"success": 0, "fail": 2})

    def test_week_aggregates_mon_to_today(self):
        quota = {
            "poe:2026-04-20": {"success": 3, "fail": 0},  # 周一
            "poe:2026-04-21": {"success": 5, "fail": 1},  # 周二
            "poe:2026-04-23": {"success": 6, "fail": 0},  # 周四
        }
        agg = self.cq.aggregate(quota, today=self.today)
        # 本周累计 = 3 + 5 + 6 = 14 success
        self.assertEqual(agg["week"]["poe"]["success"], 14)
        self.assertEqual(agg["week"]["poe"]["fail"], 1)

    def test_last_week_separated(self):
        quota = {
            "poe:2026-04-15": {"success": 4, "fail": 0},  # 上周三
            "poe:2026-04-23": {"success": 6, "fail": 0},  # 本周四
        }
        agg = self.cq.aggregate(quota, today=self.today)
        self.assertEqual(agg["last_week"]["poe"]["success"], 4)
        self.assertEqual(agg["week"]["poe"]["success"], 6)

    def test_month_includes_all_april(self):
        quota = {
            "poe:2026-04-01": {"success": 2},
            "poe:2026-04-15": {"success": 4},
            "poe:2026-04-23": {"success": 6},
            "poe:2026-03-30": {"success": 99},  # 上月 · 不算
        }
        agg = self.cq.aggregate(quota, today=self.today)
        self.assertEqual(agg["month"]["poe"]["success"], 12)

    def test_by_day_14_days(self):
        quota = {f"poe:{self.today}": {"success": 3}}
        agg = self.cq.aggregate(quota, today=self.today)
        self.assertEqual(len(agg["by_day"]), 14)
        # 最后一天是 today
        self.assertEqual(agg["by_day"][-1]["date"], self.today.isoformat())
        self.assertEqual(agg["by_day"][-1].get("poe"), 3)

    def test_invalid_keys_skipped(self):
        quota = {
            "garbage": {"success": 999},
            "poe:bad-date": {"success": 999},
            f"poe:{self.today}": {"success": 1},
        }
        agg = self.cq.aggregate(quota, today=self.today)
        self.assertEqual(agg["today"]["poe"]["success"], 1)


class TestTrendArrow(unittest.TestCase):
    def setUp(self):
        if "check_poe_quota" in sys.modules:
            del sys.modules["check_poe_quota"]
        import check_poe_quota
        self.cq = check_poe_quota

    def test_new_when_prev_zero_now_positive(self):
        self.assertEqual(self.cq._trend_arrow(5, 0), "🆕")

    def test_dot_when_both_zero(self):
        self.assertEqual(self.cq._trend_arrow(0, 0), "·")

    def test_up_arrow_when_30pct_up(self):
        out = self.cq._trend_arrow(13, 10)
        self.assertIn("🔺", out)

    def test_down_arrow_when_30pct_down(self):
        out = self.cq._trend_arrow(7, 10)
        self.assertIn("🔻", out)

    def test_dot_when_small_change(self):
        out = self.cq._trend_arrow(11, 10)
        self.assertTrue(out.startswith("·"))


class TestFormatReport(unittest.TestCase):
    def setUp(self):
        if "check_poe_quota" in sys.modules:
            del sys.modules["check_poe_quota"]
        import check_poe_quota
        self.cq = check_poe_quota

    def test_empty_message(self):
        agg = self.cq.aggregate({}, today=date(2026, 4, 23))
        report = self.cq.format_report(agg)
        self.assertIn("暂无数据", report)

    def test_full_report_structure(self):
        quota = {
            "poe:2026-04-23": {"success": 6, "fail": 0},
            "poe:2026-04-22": {"success": 5, "fail": 1},
            "poe:2026-04-15": {"success": 4, "fail": 0},  # 上周
            "gemini:2026-04-23": {"success": 0, "fail": 2},
        }
        agg = self.cq.aggregate(quota, today=date(2026, 4, 23))
        report = self.cq.format_report(agg)
        # 关键内容存在
        self.assertIn("配额周报", report)
        self.assertIn("poe", report)
        self.assertIn("gemini", report)
        self.assertIn("最近 14 天", report)
        self.assertIn("POE 自动续费", report)
        self.assertIn("poe.com/settings", report)

    def test_high_fail_warning(self):
        # POE 失败率 > 30%
        quota = {
            "poe:2026-04-23": {"success": 5, "fail": 10},
        }
        agg = self.cq.aggregate(quota, today=date(2026, 4, 23))
        report = self.cq.format_report(agg)
        self.assertIn("失败率", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
