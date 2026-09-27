# -*- coding: utf-8 -*-
"""回归验收：把 dashboard.json 的复算结果与作者截图逐项对照，按可信等级套用容差。

运行：cd index-valuation-board && python3 -m unittest discover -s tests -v
前提：已执行 python3 compute/run_all.py
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from compute.config import DASHBOARD_JSON, QUALITY, TOLERANCES  # noqa: E402

REFERENCE = os.path.join(ROOT, "data", "reference", "screenshots.json")
THRESHOLD_FIELDS = ("danger", "median", "opportunity")


def load():
    with open(DASHBOARD_JSON, encoding="utf-8") as fh:
        dashboard = json.load(fh)
    with open(REFERENCE, encoding="utf-8") as fh:
        reference = json.load(fh)
    return {i["key"]: i for i in dashboard["indices"]}, dashboard, reference


class TestDatasetComplete(unittest.TestCase):
    def setUp(self):
        self.by_key, self.dashboard, self.reference = load()

    def test_five_indices_present(self):
        for key in ("nasdaq100", "sp500", "dividend_low_vol", "csi_a500", "csi_dividend"):
            self.assertIn(key, self.by_key, "缺少指数 %s" % key)

    def test_metric_regression_dividend_low_vol_is_dividend_yield(self):
        """回归护栏：红利低波必须是「股息率」（作者 09-23 图误用市净率，09-27 已改）。"""
        idx = self.by_key["dividend_low_vol"]
        self.assertEqual(idx["metric"], "dy")
        self.assertEqual(idx["direction"], "inverse")

    def test_inverse_direction_for_yield_indices(self):
        for key in ("dividend_low_vol", "csi_dividend"):
            self.assertEqual(self.by_key[key]["direction"], "inverse")

    def test_all_windows_have_twelve_fields(self):
        fields = ("current", "percentile", "danger", "median", "opportunity", "level",
                  "max", "mean", "min", "std_plus", "std_minus", "zscore")
        for key, idx in self.by_key.items():
            for window in self.dashboard["windows"]:
                st = idx["stats"].get(window)
                self.assertIsNotNone(st, "%s 缺少 %s 窗口统计" % (key, window))
                for field in fields:
                    self.assertIsNotNone(st.get(field), "%s/%s 缺字段 %s" % (key, window, field))


class TestReplicationAgainstScreenshots(unittest.TestCase):
    def setUp(self):
        self.by_key, self.dashboard, self.reference = load()
        self.window = self.dashboard["default_window"]

    def _observations(self, key):
        """取最新一期、且口径与当前配置一致的对照记录。"""
        idx = self.by_key[key]
        obs = [o for o in self.reference["observations"]
               if o["index_key"] == key and o["metric"] == idx["metric"] and o.get("stats")]
        return sorted(obs, key=lambda o: o["article"])[-1] if obs else None

    def test_real_indices_within_tolerance(self):
        for key in ("nasdaq100", "sp500"):
            obs = self._observations(key)
            self.assertIsNotNone(obs, "%s 无对照记录" % key)
            stats = self.by_key[key]["stats"][self.window]
            tol = TOLERANCES["real"]
            for field in THRESHOLD_FIELDS:
                rel = abs(stats[field] - obs["stats"][field]) / abs(obs["stats"][field]) * 100
                self.assertLessEqual(rel, tol["threshold_pct"],
                                     "%s %s 偏差 %.2f%% 超出" % (key, field, rel))
            rel_current = abs(stats["current"] - obs["stats"]["current"]) / abs(obs["stats"]["current"]) * 100
            self.assertLessEqual(rel_current, tol["current_pct"], "%s 当前值偏差 %.2f%%" % (key, rel_current))
            self.assertLessEqual(abs(stats["zscore"] - obs["stats"]["zscore"]), tol["zscore_abs"])
            self.assertLessEqual(abs(stats["percentile"] - obs["stats"]["percentile"]),
                                 tol["percentile_pp"])

    def test_derived_yield_current_matches_official(self):
        """股息率的当前值必须与官方/截图一致（硬约束），历史阈值放宽到 5%。"""
        tol = TOLERANCES["derived"]
        for key in ("dividend_low_vol", "csi_dividend"):
            obs = self._observations(key)
            self.assertIsNotNone(obs)
            stats = self.by_key[key]["stats"][self.window]
            self.assertLessEqual(abs(stats["current"] - obs["stats"]["current"]), tol["current_abs"],
                                 "%s 当前股息率偏差过大" % key)
            for field in THRESHOLD_FIELDS:
                rel = abs(stats[field] - obs["stats"][field]) / abs(obs["stats"][field]) * 100
                self.assertLessEqual(rel, tol["threshold_pct"],
                                     "%s %s 偏差 %.2f%% 超出推导容差" % (key, field, rel))

    def test_a500_real_range_is_declared(self):
        idx = self.by_key["csi_a500"]
        self.assertEqual(idx["flag"], "partial")
        self.assertTrue(idx["series"][0]["date"] >= "2024-09-01",
                        "中证A500 不应出现发布日之前的推算值")
        self.assertTrue(any("2024-09-03" in n or "发布日" in n for n in idx["notes"]),
                        "中证A500 必须显式标注真实区间起点")

    def test_levels_match_screenshots(self):
        for obs in self.reference["observations"]:
            idx = self.by_key.get(obs["index_key"])
            if not idx or not obs.get("level"):
                continue
            rel = abs(idx["level"] - obs["level"]) / obs["level"] * 100
            self.assertLessEqual(rel, 3.0, "%s 点位偏差 %.2f%%" % (obs["index_key"], rel))


if __name__ == "__main__":
    unittest.main(verbosity=2)
