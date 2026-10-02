# -*- coding: utf-8 -*-
"""报告必须由当前可核验字段得出结论，不能复用旧截图的成功断言。"""

import copy
import unittest
from unittest.mock import patch

from compute import report
from tools import verify_local


class TestReportConclusions(unittest.TestCase):
    def setUp(self):
        self.stats = {field: 10.0 for field, _, _ in report.FIELDS}
        self.index = {"key": "sp500", "name": "标普500", "data_date": "2026-09-30",
                      "metric": "pe", "stats": {"10Y": self.stats}, "level": 100.0}
        self.dashboard = {"indices": [self.index], "default_window": "10Y"}
        self.observation = {"index_key": "sp500", "data_date": "2026-09-30",
                            "metric": "pe", "stats": copy.deepcopy(self.stats), "level": 100.0}

    def test_same_period_counts_pass_and_failure(self):
        self.observation["stats"]["current"] = 20.0
        summary = report.comparison_summary(self.dashboard, {"observations": [self.observation]})["sp500"]
        self.assertEqual(summary, {"observations": 1, "checked": 12, "failed": 1})
        text = "\n".join(report.conclusion_lines(self.dashboard, {"observations": [self.observation]}))
        self.assertIn("失败/超出容差 1", text)
        self.assertNotIn("与截图完全一致", text)
        self.assertIn("不能当作当时可知的择时信号", text)

    def test_expired_different_metric_obsolete_or_missing_date_are_unverified(self):
        for update in ({"data_date": "2026-09-29"}, {"metric": "pb"},
                       {"obsolete": True}, {"data_date": None}):
            with self.subTest(update=update):
                obs = dict(self.observation, **update)
                text = "\n".join(report.conclusion_lines(self.dashboard, {"observations": [obs]}))
                self.assertIn("本期未验证", text)
                self.assertEqual(report.comparison_summary(self.dashboard, {"observations": [obs]})["sp500"]["checked"], 0)

    def test_partial_record_only_fields_do_not_count_as_verified(self):
        self.index.update(key="csi_a500", name="中证A500", level=None)
        self.observation.update(index_key="csi_a500", level=None)
        self.assertEqual(report.comparison_summary(self.dashboard, {"observations": [self.observation]})["csi_a500"]["checked"], 0)

    def test_floating_tolerance_boundary_agrees_with_numeric_gate(self):
        self.assertEqual(report.judge("derived", "current", 0.030000000000000025, None, {}), "✅")

    def test_current_anchor_date_mismatch_is_labeled_as_model(self):
        self.index.update(key="dividend_low_vol", name="红利低波", metric="dy",
                          value_meta={"current_is_observed": False,
                                      "anchor_observation": {"source": "danjuan", "date": "2026-09-29"}})
        text = "\n".join(report.conclusion_lines(self.dashboard, {"observations": []}))
        self.assertIn("模型推导值", text)
        self.assertIn("锚点日期 2026-09-29", text)

    def test_method_comparison_uses_canonical_derive(self):
        with patch.object(report, "derive", return_value=([], {"anchor": "source"})) as derive:
            report.method_comparison({})
        self.assertEqual(derive.call_count, 6)
        self.assertEqual([call.kwargs["method"] for call in derive.call_args_list],
                         ["full_return", "pe_anchored", "blend"] * 2)

    def test_verification_rebuilds_before_report_render_and_tests(self):
        with patch("sys.argv", ["verify_local.py"]), patch.object(verify_local.subprocess, "run") as run:
            verify_local.main()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][1:], ["compute/run_all.py", "--rebuild"])
        self.assertEqual(commands[1][1:], ["compute/report.py"])
        self.assertEqual(commands[2][1], "macro/hsi/update.py")
        self.assertEqual(commands[3][1], "web/render.py")
        self.assertIn("unittest", commands[4])
        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
