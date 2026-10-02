# -*- coding: utf-8 -*-
"""阶段 0 主流程：抓取 → 规整 → 装配 → dashboard.json。

用法：
    cd index-valuation-board
    python3 compute/run_all.py            # 全量抓取 + 重新计算
    python3 compute/run_all.py --rebuild  # 只重算（复用 data/series/raw_inputs.json）
"""

import argparse
import datetime
import json
import math
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute import build_dataset  # noqa: E402
from compute.config import INDICES, SERIES  # noqa: E402
from fetch import fetch_csindex, fetch_danjuan, fetch_tencent  # noqa: E402

RAW_INPUTS = os.path.join(SERIES, "raw_inputs.json")


def _number(value):
    if isinstance(value, bool):
        raise ValueError("数值为布尔值")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("数值非有限正数")


def _date(value):
    return datetime.date.fromisoformat(value).isoformat()


def validate_snapshot(part, data, cfg):
    """验证适配器最终数据；空结果、业务错误与损坏行不能覆盖缓存。"""
    dates = []
    if part == "danjuan":
        if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
            raise ValueError("蛋卷响应缺少当前估值")
        current = data["current"]
        for field in ("pe", "pb", "dy"):
            _number(current.get(field))
        for field in ("pe", "pb"):
            rows = data.get(field)
            if not isinstance(rows, (list, tuple)) or not rows:
                raise ValueError("蛋卷 %s 历史为空" % field)
            series_dates = []
            for row in rows:
                day, value = row
                series_dates.append(_date(day))
                _number(value)
            if series_dates != sorted(set(series_dates)):
                raise ValueError("蛋卷历史日期重复或乱序")
            dates.extend(series_dates)
        day = current.get("date")
        if not isinstance(day, str):
            raise ValueError("蛋卷当前日期缺失")
        if len(day) == 5:
            _date(max(dates)[:4] + "-" + day)
        else:
            _date(day)
    else:
        if not isinstance(data, list) or not data:
            raise ValueError("%s 数据为空或格式非法" % part)
        for row in data:
            dates.append(_date(row["date"]))
            if part == "official":
                _number(row.get("pe1" if cfg["metric"] == "pe" else "dy1"))
            else:
                _number(row.get("close"))
        if dates != sorted(set(dates)):
            raise ValueError("%s 日期重复或乱序" % part)
        if part == "csindex_perf" and cfg["metric"] == "pe":
            _number(data[-1].get("pe_official"))
    return max(dates)


def fetch_all(previous=None):
    """每路先验证候选数据，再替换缓存；失败保留上次成功快照。"""
    raw_all = {k: dict(v) for k, v in (previous or {}).items()}
    for cfg in INDICES:
        key = cfg["key"]
        src = cfg.get("sources") or {}
        raw = dict(raw_all.get(key) or {})
        status = dict(raw.get("_status") or {})
        print("[抓取] %s %s" % (key, cfg["name"]))

        def attempt(part, loader):
            at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
            old_status = status.get(part) or {}
            fields = ("tencent_week", "tencent_day") if part == "tencent" else (part,)
            old_date = old_status.get("last_data_date")
            fallback = False
            try:
                old_dates = [validate_snapshot(f, raw.get(f), cfg) for f in fields]
                old_date = max(old_dates)
                fallback = True
            except (TypeError, ValueError, KeyError):
                pass
            try:
                candidate = loader()
                values = candidate if part == "tencent" else (candidate,)
                dates = [validate_snapshot(f, value, cfg) for f, value in zip(fields, values)]
                # 腾讯周线、日线全部有效后才一起替换。
                raw.update(dict(zip(fields, values)))
                status[part] = {"ok": True, "at": at, "last_success_at": at,
                                "last_data_date": max(dates), "fallback": False, "detail": ""}
                print("   %s: 已验证，最新 %s" % (part, max(dates)))
            except Exception as exc:  # noqa: BLE001
                status[part] = {"ok": False, "at": at,
                                "last_success_at": old_status.get("last_success_at") or
                                    (old_status.get("at") if old_status.get("ok") else None),
                                "last_data_date": old_date, "fallback": fallback, "detail": str(exc)}
                print("   %s 失败（%s），%s" % (part, exc, "沿用上次快照" if fallback else "无有效旧快照"))

        if src.get("danjuan"):
            attempt("danjuan", lambda: fetch_danjuan.fetch_index(cfg))
        if src.get("csindex"):
            attempt("csindex_perf", lambda: fetch_csindex.fetch_perf(src["csindex"]))
            attempt("official", lambda: fetch_csindex.fetch_indicator(src["csindex"]))
        if src.get("csindex_tr"):
            attempt("csindex_tr", lambda: fetch_csindex.fetch_perf(src["csindex_tr"]))
        if src.get("tencent"):
            attempt("tencent", lambda: (fetch_tencent.fetch_kline(src["tencent"], "week", 600),
                                        fetch_tencent.fetch_kline(src["tencent"], "day", 1200)))
        raw["_status"] = status
        raw_all[key] = raw

    os.makedirs(SERIES, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=SERIES,
                                         prefix="raw_inputs_", suffix=".json", delete=False) as fh:
            temporary = fh.name
            json.dump(raw_all, fh, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, RAW_INPUTS)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)
    return raw_all


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="跳过抓取，用现有 raw_inputs.json 重算")
    args = parser.parse_args()

    if args.rebuild:
        print("[重算] 复用 %s" % RAW_INPUTS)
    else:
        previous = None
        if os.path.exists(RAW_INPUTS):
            with open(RAW_INPUTS, encoding="utf-8") as fh:
                previous = json.load(fh)
            print("[抓取] 载入上一次快照作为失败兜底（%d 个指数）" % len(previous))
        fetch_all(previous)

    dashboard = build_dataset.main()
    print("\n%-12s %-10s %-6s %-10s %-8s %-9s %-9s %-9s %s"
          % ("指数", "指标", "窗口", "数据日期", "当前值", "分位点", "危险值", "机会值", "区间"))
    for idx in dashboard["indices"]:
        st = idx["stats"].get(dashboard["default_window"]) or {}
        print("%-12s %-10s %-6s %-10s %-8.2f %-8.2f%% %-9.2f %-9.2f %s"
              % (idx["name"], idx["metric_label"], dashboard["default_window"], idx["data_date"],
                 st.get("current", float("nan")), st.get("percentile", float("nan")),
                 st.get("danger", float("nan")), st.get("opportunity", float("nan")), st.get("zone", "")))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
