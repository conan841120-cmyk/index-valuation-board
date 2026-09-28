# -*- coding: utf-8 -*-
"""回归护栏：页面上的「口径核对」必须用最新一次的核对结论。

背景（2026-09-28 修复）：工作流里「口径变化监控」跑在「抓取 + 重算」之后，
装配时读到的结论总是上一次的；渲染时不重读，页面就会落后一次运行
（作者当天改口径时，红条会晚一天出现）。

运行：cd index-valuation-board && python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from compute.build_dataset import rule_watch_payload  # noqa: E402
from web.render import with_fresh_rule_watch  # noqa: E402


def write_check(path, checked_at):
    """造一份口径核对结果：1 个本项目指数 + 1 个不相关指数。"""
    data = {
        "checked_at": checked_at,
        "article": {"title": "【2026-09-28】A股+美股+港股 核心指数估值", "date": "2026-09-28"},
        "images": 21,
        "matched": 1,
        "mismatched": 0,
        "rows": [
            {"index_key": "dividend_low_vol", "index_name": "红利低波", "author_metric": "股息率",
             "our_metric": "dy", "our_metric_label": "股息率", "match": True},
            {"index_key": None, "index_name": "日经225", "author_metric": "市净率LF",
             "our_metric": None, "our_metric_label": None, "match": None},
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


class TestRuleWatchProjection(unittest.TestCase):
    def test_projects_fields_and_drops_other_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rule_check.json")
            write_check(path, "2026-09-28 05:46:20")
            out = rule_watch_payload(path)
        self.assertEqual(out["checked_at"], "2026-09-28 05:46:20")
        self.assertEqual(out["article_date"], "2026-09-28")
        self.assertEqual(out["matched"], 1)
        # 只保留本项目 5 个指数（index_key 为空的图不进页面）
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["our_metric"], "股息率")

    def test_missing_file_returns_none(self):
        self.assertIsNone(rule_watch_payload("/nonexistent/rule_check.json"))


class TestRenderFreshness(unittest.TestCase):
    def test_prefers_fresh_check_over_dashboard_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rule_check.json")
            write_check(path, "2026-09-28 05:46:20")
            stale = {"generated_at": "2026-09-28 05:45:56",
                     "rule_watch": {"checked_at": "2026-09-27 13:44:02"}}
            out = with_fresh_rule_watch(stale, path)
        self.assertEqual(out["rule_watch"]["checked_at"], "2026-09-28 05:46:20")

    def test_keeps_dashboard_copy_when_no_check_file(self):
        stale = {"rule_watch": {"checked_at": "2026-09-27 13:44:02"}}
        out = with_fresh_rule_watch(stale, "/nonexistent/rule_check.json")
        self.assertEqual(out["rule_watch"]["checked_at"], "2026-09-27 13:44:02")
