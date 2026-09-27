# -*- coding: utf-8 -*-
"""蛋卷（雪球系）指数估值适配器。

提供：PE 长历史（周频）、PB 长历史（周频）、当前 PE/PB/股息率与分位点。
实测覆盖（2026-09-27）：纳斯达克100=NDX、标普500=SP500、红利低波=CSIH30269、中证红利=SH000922。
中证A500 不在蛋卷覆盖范围内（返回空），由中证官方 perf 提供。
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch.common import get_json, save_raw, ts_to_date  # noqa: E402

BASE = "https://danjuanfunds.com/djapi/index_eva"


def _history(code, kind):
    """kind: pe | pb。返回 [(date, value)] 升序。"""
    url = "%s/%s_history/%s?day=all" % (BASE, kind, code)
    data = get_json(url, referer="https://danjuanfunds.com/")
    save_raw("danjuan_%s_%s.json" % (kind, code.replace(".", "")), data)
    payload = data.get("data") or {}
    key = "index_eva_%s_growths" % kind
    rows = payload.get(key) or []
    out = {}
    for row in rows:
        value = row.get(kind)
        ts = row.get("ts")
        if value is None or ts is None:
            continue
        out[ts_to_date(ts)] = float(value)
    return sorted(out.items())


def fetch_index(index_cfg):
    """抓取单个指数的蛋卷数据。"""
    code = (index_cfg.get("sources") or {}).get("danjuan")
    if not code:
        return None

    detail_raw = get_json("%s/detail/%s" % (BASE, code), referer="https://danjuanfunds.com/")
    save_raw("danjuan_detail_%s.json" % code.replace(".", ""), detail_raw)
    detail = detail_raw.get("data") or {}

    result = {
        "source": "danjuan",
        "code": code,
        "current": {
            "pe": detail.get("pe"),
            "pb": detail.get("pb"),
            "dy": (detail.get("yeild") or 0) * 100 if detail.get("yeild") is not None else None,
            "pe_percentile": detail.get("pe_percentile"),
            "pb_percentile": detail.get("pb_percentile"),
            "roe": detail.get("roe"),
            "date": detail.get("date"),
            "eva_type": detail.get("eva_type"),
            "begin_at": ts_to_date(detail["begin_at"]) if detail.get("begin_at") else None,
        },
        "pe": _history(code, "pe"),
        "pb": _history(code, "pb"),
    }
    result["fetched_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result


if __name__ == "__main__":
    cfg = {"sources": {"danjuan": "NDX"}}
    data = fetch_index(cfg)
    print("当前:", data["current"])
    print("PE 点数:", len(data["pe"]), data["pe"][0], data["pe"][-1])
    print("PB 点数:", len(data["pb"]), data["pb"][-1])
