# -*- coding: utf-8 -*-
"""统计口径：12 项统计量（与理杏仁「历史PE/PB」页面逐项对应）。

已用两份独立数据（蛋卷周频序列 / 中证官方日频序列）复算并与作者截图比对验证：
  中位数 = 升序序列第 ⌊0.50n⌋ 项     危险值 = 第 ⌊0.80n⌋ 项     机会值 = 第 ⌊0.20n⌋ 项
  （反向指标 股息率/风险溢价：危险值取 20 分位、机会值取 80 分位）
  分位点 = 小于当前值的样本占比；z 分数 = (当前值 − 平均值) / 样本标准差
"""

import bisect
import math

from compute.config import BUFFER_IN, BUFFER_NEAR, PCT_HIGH, PCT_LOW, PCT_MEDIAN


def quantile(sorted_values, pct):
    """理杏仁口径的分位取值：升序序列第 floor(pct × n) 项（不是线性插值）。"""
    n = len(sorted_values)
    if n == 0:
        return None
    idx = int(math.floor(pct * n))
    idx = max(0, min(idx, n - 1))
    return sorted_values[idx]


def _mean(values):
    return sum(values) / len(values)


def _stdev(values):
    n = len(values)
    if n < 2:
        return 0.0
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))


def compute(points, direction="normal"):
    """points: [{"date","value",...}]（升序）。返回 12 项统计量 + 元信息。"""
    values = [p["value"] for p in points]
    n = len(values)
    if n == 0:
        return None
    current = values[-1]
    sorted_values = sorted(values)
    mean = _mean(values)
    std = _stdev(values)

    q80 = quantile(sorted_values, PCT_HIGH)
    q50 = quantile(sorted_values, PCT_MEDIAN)
    q20 = quantile(sorted_values, PCT_LOW)
    if direction == "inverse":          # 股息率 / 风险溢价：越高越便宜
        danger, opportunity = q20, q80
    else:
        danger, opportunity = q80, q20

    below = sum(1 for v in values if v < current)
    percentile = below / n * 100.0

    level = None
    for point in reversed(points):
        if point.get("level") is not None:
            level = point["level"]
            break

    return {
        "current": current,
        "percentile": percentile,
        "danger": danger,
        "median": q50,
        "opportunity": opportunity,
        "level": level,
        "max": sorted_values[-1],
        "mean": mean,
        "min": sorted_values[0],
        "std_plus": mean + std,
        "std_minus": mean - std,
        "zscore": (current - mean) / std if std else 0.0,
        "std": std,
        "n": n,
        "start": points[0]["date"],
        "end": points[-1]["date"],
        "zone": zone_of(percentile, direction),
        "hint": hint_of(percentile, direction),
    }


ZONES = ("低估", "合理偏低", "合理偏高", "高估")


def zone_of(percentile, direction):
    """按 20/50/80 分位划分区间；反向指标方向对调。"""
    if direction == "inverse":
        if percentile >= 80:
            return "低估"
        if percentile >= 50:
            return "合理偏低"
        if percentile >= 20:
            return "合理偏高"
        return "高估"
    if percentile < 20:
        return "低估"
    if percentile < 50:
        return "合理偏低"
    if percentile < 80:
        return "合理偏高"
    return "高估"


def hint_of(percentile, direction):
    """带缓冲带的提示（避免分位点边界抖动造成单点误判）。"""
    pct = percentile if direction == "normal" else 100.0 - percentile
    if pct >= BUFFER_IN * 100:
        return "已进入危险区间"
    if pct >= BUFFER_NEAR * 100:
        return "接近危险区间"
    if pct <= 100 - BUFFER_IN * 100:
        return "已进入机会区间"
    if pct <= 100 - BUFFER_NEAR * 100:
        return "接近机会区间"
    return "区间中部"


def views(points, years):
    """「分位点」「标准差」两个视图的序列（与主序列同长度对齐）。

    返回 {"start": 窗口起点在主序列中的下标, "pct": [...], "z": [...]}，
    数组长度等于窗口内的点数（即主序列 start 之后的部分）。
    """
    if not points:
        return None
    n_all = len(points)
    window = [p for p in points if True]
    if years is not None:
        import datetime
        end = datetime.date.fromisoformat(points[-1]["date"])
        start = end - datetime.timedelta(days=int(round(365.25 * years)))
        window = [p for p in points if datetime.date.fromisoformat(p["date"]) >= start]
    values = [p["value"] for p in window]
    if not values:
        return None
    mean = _mean(values)
    std = _stdev(values)
    ordered = sorted(values)
    n = len(values)
    pct = [round(bisect.bisect_left(ordered, v) / n * 100.0, 2) for v in values]
    z = [round((v - mean) / std, 2) if std else 0.0 for v in values]
    return {"start": n_all - n, "pct": pct, "z": z}
