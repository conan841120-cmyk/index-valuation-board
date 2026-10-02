# -*- coding: utf-8 -*-
"""当前锚值下的股息率历史估算，用于当前窗口回顾，不是历史择时信号。

全收益法累计252个共同交易日（近似一年）的分红点位；PE法使用当前
蛋卷 DY×PE 估算历史派息关系；默认取两者几何平均。历史会随锚值修订。
只有锚值与估算末点同一数据日才做近端校准，不将官方不同口径混入主序列。
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _index(rows, field="value"):
    return {r["date"]: float(r[field]) for r in rows if r.get(field) is not None}


def full_return(price_rows, tr_rows, window=252):
    """全收益法：返回 [{date, value}]（单位 %）。"""
    price = _index(price_rows)
    tr = _index(tr_rows)
    days = sorted(set(price) & set(tr))
    if len(days) <= window:
        return []
    out = []
    contrib = [0.0] * len(days)
    for i in range(1, len(days)):
        p0, p1 = price[days[i - 1]], price[days[i]]
        t0, t1 = tr[days[i - 1]], tr[days[i]]
        if not p0 or not t0:
            continue
        div_yield = (t1 / t0 - 1.0) - (p1 / p0 - 1.0)
        contrib[i] = div_yield * p0      # 日收益率的基数是前日点位
    for i in range(window, len(days)):
        total = sum(contrib[i - window + 1: i + 1])
        out.append({"date": days[i], "value": total / price[days[i]] * 100.0})
    return out


def pe_anchored(pe_rows, dy_anchor, pe_anchor):
    """PE 锚定倒数法：返回 [{date, value}]（单位 %）。"""
    if not pe_anchor or not dy_anchor:
        return []
    out = []
    for row in pe_rows:
        pe = row.get("value")
        if not pe:
            continue
        out.append({"date": row["date"], "value": dy_anchor * pe_anchor / float(pe)})
    return sorted(out, key=lambda r: r["date"])


def blend(series_a, series_b, weight=0.5):
    """两条序列的几何平均（按日期对齐）。weight 为 A 的权重。"""
    a = _index(series_a)
    b = _index(series_b)
    out = []
    for date in sorted(set(a) & set(b)):
        if a[date] <= 0 or b[date] <= 0:
            continue
        value = (a[date] ** weight) * (b[date] ** (1.0 - weight))
        out.append({"date": date, "value": value})
    return out


def official_current(official_rows, field="dy1"):
    """官方估值文件里最新一期的股息率（默认取 股息率1=总股本口径）。"""
    rows = [r for r in official_rows if r.get(field) is not None]
    if not rows:
        return None, None
    last = max(rows, key=lambda r: r["date"])
    return last["date"], float(last[field])


def calibrate(points, target_last, days, target_date=None):
    """仅同数据日做近端校准；窗口是历史截图拟合参数，不是误差保证。"""
    if not points or target_last is None or days <= 0:
        return points
    items = sorted(points, key=lambda r: r["date"])
    if target_date != items[-1]["date"]:
        return points
    k_end = float(target_last) / items[-1]["value"] if items[-1]["value"] else 1.0
    end = date.fromisoformat(items[-1]["date"])
    out = []
    for row in items:
        age = (end - date.fromisoformat(row["date"])).days
        weight = max(0.0, 1.0 - age / float(days))
        out.append({"date": row["date"], "value": row["value"] * (1.0 - (1.0 - k_end) * weight)})
    out[-1]["value"] = float(target_last)
    return out


def calibration_ratio(derived, official_rows, field="dy1"):
    """推导序列在官方窗口内的平均比例（1.0 表示推导与官方同量级）。"""
    derived_index = _index(derived)
    ratios = []
    for row in official_rows:
        value = row.get(field)
        if value is None:
            continue
        base = derived_index.get(row["date"])
        if base:
            ratios.append(float(value) / base)
    if not ratios:
        return None, 0
    return sum(ratios) / len(ratios), len(ratios)


def derive(index_cfg, pe_rows, price_rows, tr_rows, official_rows, danjuan_current, method=None,
           calib_days=None):
    """返回估算序列和来源/日期元信息；官方真实历史由装配层独立展示。"""
    from compute.config import YIELD_CALIBRATION_DAYS, YIELD_METHOD

    method = method or os.environ.get("DIVIDEND_METHOD", YIELD_METHOD)
    if method not in ("full_return", "pe_anchored", "blend"):
        raise ValueError("未知股息率推导方法: %s" % method)
    calib_days = YIELD_CALIBRATION_DAYS if calib_days is None else calib_days
    official_rows = sorted(official_rows or [], key=lambda r: r["date"])
    meta = {"method": method, "anchor": None, "anchor_observation": None,
            "retrospective": True, "notes": []}

    dy_anchor = pe_anchor = None
    anchor_date = current_date(danjuan_current or {})
    if anchor_date and danjuan_current.get("dy") is not None and danjuan_current.get("pe"):
        dy_anchor = float(danjuan_current["dy"])
        pe_anchor = float(danjuan_current["pe"])
        meta["anchor"] = "蛋卷第三方 %.2f%% / PE %.2f (%s)" % (dy_anchor, pe_anchor, anchor_date)
        meta["anchor_observation"] = {"source": "danjuan", "date": anchor_date, "value": dy_anchor}

    series_a = full_return(price_rows, tr_rows)
    series_b = pe_anchored([p for p in pe_rows if anchor_date and p["date"] <= anchor_date],
                          dy_anchor, pe_anchor)

    if method == "full_return":
        series = series_a
    elif method == "pe_anchored":
        series = series_b
    else:
        series = blend(series_a, series_b)
    if not series and series_a:
        series = series_a
        meta["method"] = "full_return"
        meta["notes"].append("缺少同口径可用蛋卷锚值或共同日期，降级为未锚定全收益估算；官方股息率独立对照")

    # 不把较新的当前值写到较早日期；保留观测日期供页面明确展示。
    raw_last = series[-1]["value"] if series else None
    applied = bool(series and dy_anchor is not None and calib_days > 0
                   and series[-1]["date"] == anchor_date)
    series = calibrate(series, dy_anchor, calib_days, anchor_date)
    meta["calibration"] = {
        "type": "near_end_ramp",
        "days": calib_days,
        "target": dy_anchor,
        "target_date": anchor_date,
        "applied": applied,
        "raw_last_before": round(raw_last, 4) if raw_last is not None else None,
        "k_end": round(dy_anchor / raw_last, 4) if applied and raw_last else None,
    }
    meta["current_is_observed"] = bool(series and meta["anchor_observation"]
                                      and series[-1]["date"] == anchor_date
                                      and abs(series[-1]["value"] - dy_anchor) < 1e-9)

    ratio, n = calibration_ratio(series_a, official_rows)
    if ratio is not None:
        meta["official_check"] = {
            "full_return_vs_official_ratio": round(ratio, 4),
            "overlap_days": n,
            "official_window": [official_rows[0]["date"], official_rows[-1]["date"]] if official_rows else None,
        }
    meta["full_return_points"] = len(series_a)
    meta["pe_anchored_points"] = len(series_b)
    meta["real_window_start"] = official_rows[0]["date"] if official_rows else None
    return series, meta


def current_date(current):
    """蛋卷 MM-DD 需用该响应抓取日补全年份，跨年取不晚于抓取日的一次。"""
    value = current.get("date") or ""
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat()
        if len(value) == 5 and current.get("fetched_at"):
            fetched = date.fromisoformat(current["fetched_at"][:10])
            candidate = date.fromisoformat("%d-%s" % (fetched.year, value))
            if candidate > fetched:
                candidate = date.fromisoformat("%d-%s" % (fetched.year - 1, value))
            return candidate.isoformat()
    except (ValueError, TypeError):
        pass
    return None
