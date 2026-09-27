# -*- coding: utf-8 -*-
"""序列规整：统一日期格式、按周聚合（每周最后一个交易日）、窗口切片。"""

import datetime

ONE_DAY = datetime.timedelta(days=1)


def to_iso(date_str):
    """'YYYYMMDD' 或 'YYYY-MM-DD' → 'YYYY-MM-DD'。"""
    if not date_str:
        return None
    s = str(date_str).strip()
    if "-" in s:
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8])
    return s


def to_weekly(rows, value_field="value"):
    """按 ISO 周聚合，取每周最后一个交易日的值。rows: [{date, ...}]。"""
    buckets = {}
    for row in rows:
        date = to_iso(row.get("date"))
        value = row.get(value_field)
        if date is None or value is None:
            continue
        try:
            key = datetime.date.fromisoformat(date).isocalendar()[:2]
        except ValueError:
            continue
        buckets[key] = {"date": date, "value": float(value)}
    return [buckets[k] for k in sorted(buckets)]


def attach_level(value_points, level_map):
    """把指数点位合并到估值序列上（按日期精确匹配，缺失则取最近的前一个交易日）。"""
    if not level_map:
        return [dict(p) for p in value_points]
    dates = sorted(level_map)
    out = []
    for point in value_points:
        level = level_map.get(point["date"])
        if level is None:
            prior = [d for d in dates if d <= point["date"]]
            level = level_map[prior[-1]] if prior else None
        item = dict(point)
        item["level"] = level
        out.append(item)
    return out


def window_slice(points, years, end_date=None):
    """取最近 years 年（years=None 表示全部）。"""
    if not points:
        return []
    if years is None:
        return list(points)
    end = end_date or points[-1]["date"]
    end_dt = datetime.date.fromisoformat(end)
    start_dt = end_dt - datetime.timedelta(days=int(round(365.25 * years)))
    return [p for p in points if datetime.date.fromisoformat(p["date"]) >= start_dt]


def last_date(*series):
    dates = [p["date"] for s in series if s for p in s]
    return max(dates) if dates else None
