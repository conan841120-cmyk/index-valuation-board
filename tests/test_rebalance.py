import unittest

from compute.build_dataset import build_index, rebalance_dates, snap_rebalance_to_trading
from compute.config import INDEX_BY_KEY


class RebalanceTests(unittest.TestCase):
    def test_annual_and_semiannual_rule_anchors(self):
        self.assertEqual(rebalance_dates("semiannual", "2026-01-01", "2026-12-31"),
                         ["2026-06-12", "2026-12-11"])
        self.assertEqual(rebalance_dates("annual_dec", "2026-01-01", "2026-12-31"),
                         ["2026-12-11"])
        self.assertEqual(rebalance_dates([], "2026-01-01", "2026-12-31"), [])

    def test_friday_is_not_the_effective_session(self):
        self.assertEqual(snap_rebalance_to_trading(["2026-06-12"],
                         ["2026-06-11", "2026-06-12", "2026-06-15"]), ["2026-06-15"])

    def test_closed_monday_uses_next_available_session(self):
        self.assertEqual(snap_rebalance_to_trading(["2026-06-12"],
                         ["2026-06-11", "2026-06-12", "2026-06-16"]), ["2026-06-16"])

    def test_no_forward_session_does_not_invent_a_marker(self):
        for days in ([], ["2026-06-11", "2026-06-12"]):
            with self.subTest(days=days):
                self.assertEqual(snap_rebalance_to_trading(["2026-06-12"], days), [])

    def test_anchor_before_price_history_is_not_mapped_to_its_first_row(self):
        self.assertEqual(snap_rebalance_to_trading(["2025-12-12"],
                         ["2026-06-11", "2026-06-12", "2026-06-15"]), [])

    def test_dataset_keeps_effective_date_and_valuation_statistics(self):
        cfg = INDEX_BY_KEY["csi_a500"]
        raw = {"csindex_perf": [{"date": day, "close": 100 + i, "pe_official": 20 + i}
               for i, day in enumerate(["2026-06-05", "2026-06-12", "2026-06-15"])]}
        index = build_index(cfg, raw)
        self.assertEqual(index["rebalance_dates"], ["2026-06-15"])
        no_markers = build_index({**cfg, "rebalance": []}, raw)
        self.assertEqual(index["stats"], no_markers["stats"])
        self.assertEqual(index["series"], no_markers["series"])
        raw["csindex_perf"] = raw["csindex_perf"][:-1]
        self.assertEqual(build_index(cfg, raw)["rebalance_dates"], [])
