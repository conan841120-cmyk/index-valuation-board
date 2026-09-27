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
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute import build_dataset  # noqa: E402
from compute.config import INDICES, SERIES  # noqa: E402
from fetch import fetch_csindex, fetch_danjuan, fetch_tencent  # noqa: E402

RAW_INPUTS = os.path.join(SERIES, "raw_inputs.json")


def fetch_all(previous=None):
    """抓取全部数据源。任何一路失败都沿用上一次成功的快照（previous），并记录状态。

    云端每天运行，单个数据源被风控/超时不应该让整页数据消失——因此用「增量覆盖 + 状态标记」
    的方式：成功的部分覆盖，失败的保留旧值，并把状态写进 raw["_status"]，页面据此提示。
    """
    raw_all = {k: dict(v) for k, v in (previous or {}).items()}
    for cfg in INDICES:
        key = cfg["key"]
        src = cfg.get("sources") or {}
        raw = dict(raw_all.get(key) or {})
        status = dict(raw.get("_status") or {})
        print("[抓取] %s %s" % (key, cfg["name"]))

        def mark(part, ok, detail=""):
            status[part] = {"ok": bool(ok), "detail": detail,
                            "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}

        if src.get("danjuan"):
            try:
                raw["danjuan"] = fetch_danjuan.fetch_index(cfg)
                cur = raw["danjuan"]["current"]
                print("   蛋卷: PE=%s PB=%s 股息率=%s (%s) PE点数=%d"
                      % (cur.get("pe"), cur.get("pb"), cur.get("dy"), cur.get("date"),
                         len(raw["danjuan"]["pe"])))
                mark("danjuan", True)
            except Exception as exc:  # noqa: BLE001
                print("   蛋卷失败（%s），沿用上次快照" % exc)
                mark("danjuan", False, str(exc))

        if src.get("csindex"):
            try:
                raw["csindex_perf"] = fetch_csindex.fetch_perf(src["csindex"])
                print("   中证行情: %d 行, %s ~ %s" % (len(raw["csindex_perf"]),
                       raw["csindex_perf"][0]["date"], raw["csindex_perf"][-1]["date"]))
                mark("csindex_perf", True)
            except Exception as exc:  # noqa: BLE001
                print("   中证行情失败（%s），沿用上次快照" % exc)
                mark("csindex_perf", False, str(exc))
            try:
                raw["official"] = fetch_csindex.fetch_indicator(src["csindex"])
                first, last = raw["official"][0], raw["official"][-1]
                print("   官方估值窗口: %d 行, %s ~ %s (PE1=%s 股息率1=%s)"
                      % (len(raw["official"]), first["date"], last["date"], last["pe1"], last["dy1"]))
                mark("official", True)
            except Exception as exc:  # noqa: BLE001
                print("   官方估值文件失败（%s），沿用上次快照" % exc)
                mark("official", False, str(exc))

        if src.get("csindex_tr"):
            try:
                raw["csindex_tr"] = fetch_csindex.fetch_perf(src["csindex_tr"])
                print("   全收益指数: %d 行" % len(raw["csindex_tr"]))
                mark("csindex_tr", True)
            except Exception as exc:  # noqa: BLE001
                print("   全收益指数失败（%s），沿用上次快照" % exc)
                mark("csindex_tr", False, str(exc))

        if src.get("tencent"):
            try:
                raw["tencent_week"] = fetch_tencent.fetch_kline(src["tencent"], "week", 600)
                raw["tencent_day"] = fetch_tencent.fetch_kline(src["tencent"], "day", 1200)
                print("   腾讯: 周线 %d 根, 日线 %d 根, 最新 %s"
                      % (len(raw["tencent_week"]), len(raw["tencent_day"]),
                         raw["tencent_day"][-1] if raw["tencent_day"] else "-"))
                mark("tencent", True)
            except Exception as exc:  # noqa: BLE001
                print("   腾讯失败（%s），沿用上次快照" % exc)
                mark("tencent", False, str(exc))

        raw["_status"] = status
        raw_all[key] = raw

    os.makedirs(SERIES, exist_ok=True)
    with open(RAW_INPUTS, "w", encoding="utf-8") as fh:
        json.dump(raw_all, fh, ensure_ascii=False)
    failed = [(k, p) for k, v in raw_all.items() for p, s in (v.get("_status") or {}).items() if not s["ok"]]
    if failed:
        print("\n⚠️ 本次有 %d 个数据源沿用上次快照：%s"
              % (len(failed), ", ".join("%s/%s" % (k, p) for k, p in failed)))
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
