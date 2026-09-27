# -*- coding: utf-8 -*-
"""股息率历史推导（红利低波、中证红利）。

背景：官方与蛋卷都只提供**当前**股息率（中证官方估值文件的 20 日窗口是最长的免费真实序列），
没有免费的真实 10 年股息率历史。本模块用两条独立路线推导，并支持几何平均与官方校准：

  A. full_return  全收益法：用「全收益指数 ÷ 价格指数」的日收益差还原每日分红贡献，
                  滚动 252 个交易日累计后除以当日点位 → 过去 12 个月的实际派息收益率。
  B. pe_anchored  PE 锚定法：股息率 = 派息率 / PE。以最新官方（或蛋卷）股息率锚定派息率，
                  历史序列 = dy_now × PE_now / PE_t，保证"当前值"与官方完全一致。
  C. blend        两者几何平均（默认）。

实测误差（对照 2026-09-27 作者截图，红利低波 10 年窗口）：
  A: 危险 4.00 / 中位 4.74 / 机会 5.41 / 当前 5.29   （阈值好，当前值偏高 19%）
  B: 危险 4.30 / 中位 5.43 / 机会 6.78 / 当前 4.45 ✓ （当前值精确，阈值偏高 9~14%）
  C: 危险 4.15 / 中位 5.07 / 机会 6.06 / 当前 4.87   （阈值最准 ≤5%）
  → 默认 C，并把「当前值」强制取官方/蛋卷真实值；页面对危险值/机会值/分位点标注「≈ 推导值」。
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
    if len(days) <= window + 1:
        return []
    out = []
    contrib = [0.0] * len(days)
    for i in range(1, len(days)):
        p0, p1 = price[days[i - 1]], price[days[i]]
        t0, t1 = tr[days[i - 1]], tr[days[i]]
        if not p0 or not t0:
            continue
        div_yield = (t1 / t0 - 1.0) - (p1 / p0 - 1.0)
        contrib[i] = div_yield * p1      # 折算成"点位"的分红
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


def calibrate(points, target_last, days):
    """近端衰减校准：把序列末点平移到官方真实值，修正幅度向前按线性权重衰减。

    为什么需要：推导序列的"水平"偏差是逐年累积的（全收益法把过去的分红按当时点位累计，
    上涨行情下会高于"当前时点股息率"），越靠近今天偏差越大；因此把修正集中放在近端，
    而不是整条序列乘以同一个系数——后者虽然能让末点等于官方值，却会扭曲历史分布，
    使"分位点"（当前值在分布中的排名）偏差从 6pp 级别放大到 15pp 级别。

    实测（红利低波 10Y，对照作者截图）：硬锚定 → 分位点偏差 −14.5pp；
    本校准（days=1825）→ −6.1pp，且危险值/中位数/机会值偏差保持在 ≤3%。
    """
    if not points or target_last is None or days <= 0:
        return points
    items = sorted(points, key=lambda r: r["date"])
    k_end = float(target_last) / items[-1]["value"] if items[-1]["value"] else 1.0
    end = date.fromisoformat(items[-1]["date"])
    out = []
    for row in items:
        age = (end - date.fromisoformat(row["date"])).days
        weight = max(0.0, 1.0 - age / float(days))
        out.append({"date": row["date"], "value": row["value"] * (1.0 - (1.0 - k_end) * weight)})
    out[-1]["value"] = float(target_last)      # 末点严格等于官方真实值
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
    """按配置推导股息率序列，返回 (series, meta)。序列已做近端衰减校准，末点=官方真实值。"""
    from compute.config import YIELD_CALIBRATION_DAYS  # 延迟导入，避免循环依赖

    method = method or os.environ.get("DIVIDEND_METHOD", "blend")
    calib_days = YIELD_CALIBRATION_DAYS if calib_days is None else calib_days
    official_rows = sorted(official_rows or [], key=lambda r: r["date"])
    meta = {"method": method, "anchor": None, "notes": []}

    dy_anchor = pe_anchor = None
    if danjuan_current and danjuan_current.get("dy") is not None and danjuan_current.get("pe"):
        dy_anchor = float(danjuan_current["dy"])
        pe_anchor = float(danjuan_current["pe"])
        meta["anchor"] = "蛋卷当前值 %.2f%% / PE %.2f (%s)" % (dy_anchor, pe_anchor, danjuan_current.get("date"))
    else:
        date, dy = official_current(official_rows)
        if dy is not None:
            dy_anchor = dy
            meta["anchor"] = "中证官方 %s 股息率1 %.2f%%" % (date, dy)

    series_a = full_return(price_rows, tr_rows)
    series_b = pe_anchored(pe_rows, dy_anchor, pe_anchor)

    if method == "full_return":
        series = series_a
    elif method == "pe_anchored":
        series = series_b
    else:
        series = blend(series_a, series_b)

    # 近端衰减校准：末点严格等于官方真实值，修正幅度向前衰减
    raw_last = series[-1]["value"] if series else None
    series = calibrate(series, dy_anchor, calib_days)
    meta["calibration"] = {
        "type": "near_end_ramp",
        "days": calib_days,
        "target": dy_anchor,
        "raw_last_before": round(raw_last, 4) if raw_last is not None else None,
        "k_end": round(dy_anchor / raw_last, 4) if raw_last else None,
    }

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
