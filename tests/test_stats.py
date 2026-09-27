# -*- coding: utf-8 -*-
"""统计口径单元测试：分位取值、分位点、z 分数、方向翻转、区间判定。

运行：cd index-valuation-board && python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.stats import compute, quantile, zone_of  # noqa: E402


def series(values, start_level=100.0):
    return [{"date": "2020-01-%02d" % (i + 1), "value": v, "level": start_level + i}
            for i, v in enumerate(values)]


class TestQuantile(unittest.TestCase):
    def test_floor_index_convention(self):
        # 理杏仁口径：升序第 floor(pct × n) 项（自 0 起），不是线性插值
        vals = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(quantile(vals, 0.2), 2.0)   # floor(0.2*5)=1 → 第 2 项
        self.assertEqual(quantile(vals, 0.5), 3.0)   # floor(2.5)=2 → 第 3 项
        self.assertEqual(quantile(vals, 0.8), 5.0)   # floor(4.0)=4 → 第 5 项

    def test_clamped_for_short_series(self):
        self.assertEqual(quantile([1.0, 2.0], 0.8), 2.0)


class TestStats(unittest.TestCase):
    def test_percentile_and_zscore(self):
        values = [float(v) for v in range(1, 101)]     # 1..100
        st = compute(series(values), "normal")
        self.assertEqual(st["current"], 100.0)
        self.assertEqual(st["min"], 1.0)
        self.assertEqual(st["max"], 100.0)
        self.assertAlmostEqual(st["percentile"], 99.0, places=6)   # 99 个样本小于当前值
        # 均值 50.5、样本标准差 29.0115（ddof=1）→ z = 49.5 / 29.0115
        self.assertAlmostEqual(st["zscore"], 1.7062, places=3)
        self.assertEqual(st["n"], 100)

    def test_danger_and_opportunity_normal(self):
        values = [float(v) for v in range(1, 101)]
        st = compute(series(values), "normal")
        self.assertEqual(st["median"], 51.0)      # floor(0.5*100)=50 → 第 51 项
        self.assertEqual(st["danger"], 81.0)      # floor(0.8*100)=80 → 第 81 项
        self.assertEqual(st["opportunity"], 21.0)  # floor(0.2*100)=20 → 第 21 项
        self.assertTrue(st["danger"] > st["median"] > st["opportunity"])

    def test_inverse_metric_swaps_thresholds(self):
        values = [float(v) for v in range(1, 101)]
        normal = compute(series(values), "normal")
        inverse = compute(series(values), "inverse")
        # 股息率越高越便宜 → 危险值取 20 分位、机会值取 80 分位
        self.assertEqual(inverse["danger"], normal["opportunity"])
        self.assertEqual(inverse["opportunity"], normal["danger"])
        self.assertLess(inverse["danger"], inverse["median"])
        self.assertGreater(inverse["opportunity"], inverse["median"])

    def test_level_taken_from_last_point(self):
        st = compute(series([1.0, 2.0, 3.0]), "normal")
        self.assertEqual(st["level"], 102.0)


class TestZones(unittest.TestCase):
    def test_normal_direction(self):
        self.assertEqual(zone_of(10, "normal"), "低估")
        self.assertEqual(zone_of(30, "normal"), "合理偏低")
        self.assertEqual(zone_of(60, "normal"), "合理偏高")
        self.assertEqual(zone_of(90, "normal"), "高估")

    def test_inverse_direction(self):
        self.assertEqual(zone_of(90, "inverse"), "低估")
        self.assertEqual(zone_of(60, "inverse"), "合理偏低")
        self.assertEqual(zone_of(30, "inverse"), "合理偏高")
        self.assertEqual(zone_of(10, "inverse"), "高估")


if __name__ == "__main__":
    unittest.main(verbosity=2)
