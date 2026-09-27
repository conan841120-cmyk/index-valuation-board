# -*- coding: utf-8 -*-
"""中证指数官方数据适配器（免费、权威）。

两个接口：
1) 历史行情/估值：/csindex-home/perf/index-perf  —— 日频收盘价 + 每日 PE 字段（实测最早回到 2010，A500 的 PE 自 2024-09-03 起）
2) 估值指标文件：oss-ch.csindex.com.cn/.../{code}indicator.xls —— 市盈率1/2、股息率1/2，**只有最近约 20 个交易日**
   → 每次运行都把该窗口落盘累积，逐步形成"官方真实历史"。
"""

import datetime
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.config import SNAPSHOTS  # noqa: E402
from fetch.common import fetch, get_json, save_raw, today_str  # noqa: E402

PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
INDICATOR = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/"
    "autofile/indicator/{code}indicator.xls"
)
INDICATOR_COLS = ["date", "pe1", "pe2", "dy1", "dy2"]


def fetch_perf(code, start="20100101", end=None):
    """日频行情：返回 [{date, close, pe_official, change_pct, name}] 升序。"""
    end = end or today_str().replace("-", "")
    url = "%s?indexCode=%s&startDate=%s&endDate=%s" % (PERF, code, start, end)
    data = get_json(url, referer="https://www.csindex.com.cn/")
    save_raw("csindex_perf_%s.json" % code, data)
    rows = []
    for item in data.get("data") or []:
        close = item.get("close")
        if close is None:
            continue
        rows.append(
            {
                "date": _iso(item["tradeDate"]),   # 统一为 YYYY-MM-DD
                "close": float(close),
                "pe_official": item.get("peg"),
                "change_pct": item.get("changePct"),
                "name": item.get("indexNameCn"),
            }
        )
    return sorted(rows, key=lambda r: r["date"])


def _iso(d):
    s = str(d)
    return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8])


def fetch_indicator(code):
    """下载官方 20 日估值窗口 → 落盘 xls + 追加到累积 CSV。返回本次窗口行列表。"""
    url = INDICATOR.format(code=code)
    resp = fetch(url, referer="https://www.csindex.com.cn/")
    os.makedirs(SNAPSHOTS, exist_ok=True)
    xls_path = os.path.join(SNAPSHOTS, "indicator_%s_%s.xls" % (code, today_str()))
    with open(xls_path, "wb") as fh:
        fh.write(resp.content)

    df = pd.read_excel(xls_path)
    cols = df.columns
    if len(cols) < 10:
        raise RuntimeError("官方估值文件列数异常: %s" % list(cols))
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "date": _iso(r.iloc[0]),
                "pe1": _num(r.iloc[6]),
                "pe2": _num(r.iloc[7]),
                "dy1": _num(r.iloc[8]),
                "dy2": _num(r.iloc[9]),
                "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    rows = [r for r in rows if r["date"]]
    _append_csv(code, rows)
    return sorted(rows, key=lambda r: r["date"])   # 统一升序（xls 原始顺序是最新在前）


def _num(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:  # noqa: BLE001
        return None


def _append_csv(code, rows):
    path = os.path.join(SNAPSHOTS, "indicator_%s.csv" % code)
    old = pd.read_csv(path, dtype=str) if os.path.exists(path) else pd.DataFrame(columns=INDICATOR_COLS + ["fetched_at"])
    merged = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    merged = merged.drop_duplicates(subset=["date"], keep="last")
    merged = merged.sort_values("date")
    merged.to_csv(path, index=False)
    return path


def load_indicator_csv(code):
    path = os.path.join(SNAPSHOTS, "indicator_%s.csv" % code)
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path, dtype=str)
    out = []
    for _, r in df.iterrows():
        out.append(
            {
                "date": r["date"],
                "pe1": _num(r.get("pe1")),
                "pe2": _num(r.get("pe2")),
                "dy1": _num(r.get("dy1")),
                "dy2": _num(r.get("dy2")),
            }
        )
    return sorted(out, key=lambda r: r["date"])


if __name__ == "__main__":
    rows = fetch_perf("H30269", start="20260801")
    print("行情尾部:", rows[-2:])
    ind = fetch_indicator("H30269")
    print("官方估值窗口:", len(ind), ind[0], ind[-1])
