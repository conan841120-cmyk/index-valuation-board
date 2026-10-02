# -*- coding: utf-8 -*-
"""回归验收：结构 / 口径 / 自洽性（与时间无关）+ 同期截图比对（仅同期生效）。

为什么这样分层（2026-09-28 修订）：
  作者的数字**每天也在重算**（自己的窗口在滚动、当天数据也不同），所以「拿今天的复算值
  去比几天前的截图」是刻舟求剑——只有**同一数据日**的基准才有资格判定。因此分三类：
    A. 结构 / 口径 / 自洽性：与时间无关，永远判定（发布闸门主体）；
    B. 同期截图比对：仅当基准 data_date == 本期 data_date 时判定；
       过期基准跳过（偏差仍由 compute/report.py 写进 outputs/口径与误差报告.md，供人查看）；
    C. 浮点边界用 EPS 兜底（0.03 <= 0.03 不该因二进制尾数失败）。

运行：cd index-valuation-board && python3 -m unittest discover -s tests -v
前提：已执行 python3 compute/run_all.py
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from compute.config import DASHBOARD_JSON, QUALITY, TOLERANCES  # noqa: E402
from compute.provenance import input_digest, code_digest  # noqa: E402

REFERENCE = os.path.join(ROOT, "data", "reference", "screenshots.json")
THRESHOLD_FIELDS = ("danger", "median", "opportunity")
EPS = 1e-9
LEVEL_TOL_PCT = 3.0        # 同期点位比对容差（%）
MIN_10Y_POINTS = 470       # 10 年周频 ≈ 500~520 个点；低于此说明序列被截断
MAX_10Y_POINTS = 560
FIRST_DATE = "2016-01-01"  # 蛋卷长历史起点为 2016-09


def load():
    with open(DASHBOARD_JSON, encoding="utf-8") as fh:
        dashboard = json.load(fh)
    provenance = dashboard.get("provenance") or {}
    if provenance.get("inputs_sha256") != input_digest():
        raise AssertionError("dashboard.json 与当前原始输入/官方 CSV 不一致；先运行 tools/verify_local.py 重建")
    if provenance.get("code_sha256") != code_digest():
        raise AssertionError("dashboard.json 与当前计算/渲染代码不一致；先运行 tools/verify_local.py 重建")
    with open(REFERENCE, encoding="utf-8") as fh:
        reference = json.load(fh)
    return {i["key"]: i for i in dashboard["indices"]}, dashboard, reference


class TestProvenanceGuard(unittest.TestCase):
    def test_stale_inputs_or_code_are_rejected_before_acceptance(self):
        for provenance, message in (
                ({"inputs_sha256": "old", "code_sha256": "code"}, "当前原始输入"),
                ({"inputs_sha256": "inputs", "code_sha256": "old"}, "当前计算/渲染代码")):
            with self.subTest(provenance=provenance), tempfile.TemporaryDirectory() as temp:
                path = os.path.join(temp, "dashboard.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"provenance": provenance}, fh)
                with patch.dict(load.__globals__, DASHBOARD_JSON=path), \
                        patch(__name__ + ".input_digest", return_value="inputs"), \
                        patch(__name__ + ".code_digest", return_value="code"):
                    with self.assertRaisesRegex(AssertionError, message):
                        load()


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


class TestInternalConsistency(unittest.TestCase):
    """与时间无关自洽性检查：替代「拿过期快照比数字」，永不因行情漂移误报。"""

    def setUp(self):
        self.by_key, self.dashboard, _ = load()

    def test_thresholds_ordered_by_direction(self):
        for key, idx in self.by_key.items():
            for window in self.dashboard["windows"]:
                st = idx["stats"][window]
                danger, median, oppo = st["danger"], st["median"], st["opportunity"]
                if idx["direction"] == "inverse":
                    self.assertGreaterEqual(oppo + EPS, median, "%s/%s 反向指标应 机会≥中位" % (key, window))
                    self.assertGreaterEqual(median + EPS, danger, "%s/%s 反向指标应 中位≥危险" % (key, window))
                else:
                    self.assertGreaterEqual(danger + EPS, median, "%s/%s 正向指标应 危险≥中位" % (key, window))
                    self.assertGreaterEqual(median + EPS, oppo, "%s/%s 正向指标应 中位≥机会" % (key, window))

    def test_ranges_and_dispersion(self):
        for key, idx in self.by_key.items():
            for window in self.dashboard["windows"]:
                st = idx["stats"][window]
                tag = "%s/%s" % (key, window)
                self.assertGreaterEqual(st["percentile"], 0.0, "%s 分位点 < 0" % tag)
                self.assertLessEqual(st["percentile"], 100.0, "%s 分位点 > 100" % tag)
                self.assertLessEqual(abs(st["zscore"]), 8.0, "%s z 分数异常" % tag)
                self.assertGreater(st["std"], 0.0, "%s 标准差应 > 0" % tag)
                self.assertGreater(st["n"], 0, "%s 样本数为 0" % tag)
                self.assertLessEqual(st["min"], st["max"], "%s 最小值 > 最大值" % tag)
                self.assertIsNotNone(st["current"], "%s 缺当前值" % tag)
                self.assertIsNotNone(st["level"], "%s 缺点位" % tag)

    def test_windows_end_at_data_date(self):
        for key, idx in self.by_key.items():
            for window in self.dashboard["windows"]:
                st = idx["stats"][window]
                self.assertEqual(st["end"], idx["data_date"],
                                 "%s/%s 末点 %s 应等于数据日期 %s" % (key, window, st["end"], idx["data_date"]))

    def test_window_lengths_and_start(self):
        for key, idx in self.by_key.items():
            n = {w: idx["stats"][w]["n"] for w in self.dashboard["windows"]}
            self.assertGreaterEqual(n["ALL"], n["10Y"], "%s 上市以来应不短于 10Y" % key)
            self.assertGreaterEqual(n["10Y"], n["5Y"], "%s 10Y 应不短于 5Y" % key)
            self.assertGreaterEqual(n["5Y"], n["3Y"], "%s 5Y 应不短于 3Y" % key)
            for window in self.dashboard["windows"]:
                self.assertGreaterEqual(idx["stats"][window]["start"], FIRST_DATE,
                                        "%s/%s 起点早于数据源覆盖范围" % (key, window))
            if QUALITY.get(key) != "partial":
                self.assertGreaterEqual(n["10Y"], MIN_10Y_POINTS, "%s 10Y 周频点数偏少（序列被截断？）" % key)
                self.assertLessEqual(n["10Y"], MAX_10Y_POINTS, "%s 10Y 周频点数偏多（窗口错？）" % key)


class TestReplicationAgainstScreenshots(unittest.TestCase):
    """与作者截图的数值比对：只有「同一数据日」的基准才判定，过期基准跳过。"""

    def setUp(self):
        self.by_key, self.dashboard, self.reference = load()
        self.window = self.dashboard["default_window"]
        self.same_period, self.expired = [], []
        for obs in self.reference["observations"]:
            idx = self.by_key.get(obs["index_key"])
            if not idx or obs.get("stats") is None or obs.get("obsolete"):
                continue
            if obs.get("metric") != idx["metric"]:
                continue
            bucket = self.same_period if obs.get("data_date") and obs.get("data_date") == idx.get("data_date") else self.expired
            bucket.append(obs)
        print("\n[口径比对] 同期基准 %d 条（参与判定）｜ 过期基准 %d 条（只记录，见 outputs/口径与误差报告.md）"
              % (len(self.same_period), len(self.expired)))

    def _same_period(self):
        if not self.same_period:
            self.skipTest("本期未验证截图数值（无同期同口径基准，示例数据日 %s）；只运行结构/公式/自洽性，过期偏差仅记录"
                          % self.by_key["sp500"]["data_date"])

    def test_numeric_match_in_same_period(self):
        self._same_period()
        checked = 0
        for obs in self.same_period:
            key = obs["index_key"]
            idx = self.by_key[key]
            stats = idx["stats"][self.window]
            tol = TOLERANCES.get(QUALITY.get(key, "real"), {})
            for field in THRESHOLD_FIELDS:
                limit = tol.get("threshold_pct")
                if limit is None:
                    continue
                rel = abs(stats[field] - obs["stats"][field]) / abs(obs["stats"][field]) * 100
                self.assertLessEqual(rel, limit + EPS, "%s %s 偏差 %.2f%% 超出" % (key, field, rel))
                checked += 1
            current_dev = abs(stats["current"] - obs["stats"]["current"])
            if "current_abs" in tol:
                self.assertLessEqual(current_dev, tol["current_abs"] + EPS,
                                     "%s 当前值绝对偏差 %.4f 超出" % (key, current_dev))
                checked += 1
            elif tol.get("current_pct") is not None:
                rel = current_dev / abs(obs["stats"]["current"]) * 100
                self.assertLessEqual(rel, tol["current_pct"] + EPS, "%s 当前值偏差 %.2f%% 超出" % (key, rel))
                checked += 1
            if tol.get("zscore_abs") is not None:
                self.assertLessEqual(abs(stats["zscore"] - obs["stats"]["zscore"]), tol["zscore_abs"] + EPS,
                                     "%s z 分数偏差超出" % key)
                checked += 1
            if tol.get("percentile_pp") is not None:
                self.assertLessEqual(abs(stats["percentile"] - obs["stats"]["percentile"]),
                                     tol["percentile_pp"] + EPS, "%s 分位点偏差超出" % key)
                checked += 1
        if not checked:
            self.skipTest("本期未验证截图数值：同期观察没有可判定的字段容差；结构/公式/自洽性范围仍执行")
        print("[口径比对] 本次同期判定字段数：%d" % checked)

    def test_levels_in_same_period(self):
        self._same_period()
        checked = 0
        for obs in self.same_period:
            idx = self.by_key[obs["index_key"]]
            if not obs.get("level") or not idx.get("level"):
                continue
            rel = abs(idx["level"] - obs["level"]) / obs["level"] * 100
            self.assertLessEqual(rel, LEVEL_TOL_PCT + EPS,
                                 "%s 点位偏差 %.2f%% 超出" % (obs["index_key"], rel))
            checked += 1
        if not checked:
            self.skipTest("本期未验证截图点位：同期观察没有双方都可用的点位；不影响结构/公式/自洽性范围")

    def test_a500_real_range_is_declared(self):
        idx = self.by_key["csi_a500"]
        self.assertEqual(idx["flag"], "partial")
        self.assertTrue(idx["series"][0]["date"] >= "2024-09-01",
                        "中证A500 不应出现发布日之前的推算值")
        self.assertTrue(any("2024-09-03" in n or "发布日" in n for n in idx["notes"]),
                        "中证A500 必须显式标注真实区间起点")


if __name__ == "__main__":
    unittest.main(verbosity=2)
