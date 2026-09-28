# -*- coding: utf-8 -*-
"""把各数据源抓取结果装配成 data/series/*.json 与 data/dashboard.json。"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute import normalize  # noqa: E402
from compute.config import (  # noqa: E402
    DATA,
    DASHBOARD_JSON,
    DEFAULT_WINDOW,
    INDEX_BY_KEY,
    INDICES,
    INVERSE_METRICS,
    METRICS,
    QUALITY,
    THRESHOLD_UNCERTAINTY,
    SERIES,
    WINDOWS,
    is_inverse,
)
from compute.stats import compute, views as stats_views  # noqa: E402
from fetch.derive_yield import derive  # noqa: E402


# ------------------------------------------------------------------ 调仓标志

def second_friday(year, month):
    """某年某月的第二个星期五。"""
    day = datetime.date(year, month, 1)
    fridays = []
    while day.month == month:
        if day.weekday() == 4:
            fridays.append(day)
        day += datetime.timedelta(days=1)
    return fridays[1] if len(fridays) > 1 else None


def rebalance_dates(rule, first_date, last_date):
    """按中证规则生成调仓日（第二个星期五之后的第一个交易日）。"""
    if not rule or not first_date or not last_date:
        return []
    months = [12] if rule == "annual_dec" else [6, 12]
    start_year = int(first_date[:4])
    end_year = int(last_date[:4])
    out = []
    for year in range(start_year, end_year + 1):
        for month in months:
            d = second_friday(year, month)
            if d and first_date <= d.isoformat() <= last_date:
                out.append(d.isoformat())
    return out


def snap_rebalance_to_trading(dates, trading_days):
    """把调仓日吸附到之后的第一个交易日（与作者图上三角位置一致）。"""
    if not trading_days:
        return dates
    out = []
    for d in dates:
        forward = [t for t in trading_days if t >= d]
        out.append(forward[0] if forward else d)
    return sorted(set(out))


# ------------------------------------------------------------------ 装配

def build_index(cfg, raw):
    """raw 由 fetch 层提供：{'danjuan','csindex_perf','csindex_tr','official','tencent_week','tencent_day'}"""
    key = cfg["key"]
    metric = cfg["metric"]
    direction = "inverse" if is_inverse(cfg) else "normal"

    notes = []
    level_rows = []
    change_pct = None

    # ---- 指数点位
    tencent_day = raw.get("tencent_day") or []
    if cfg["level_source"] == "csindex" and raw.get("csindex_perf"):
        level_rows = [{"date": r["date"], "value": r["close"], "change_pct": r.get("change_pct")}
                      for r in raw["csindex_perf"]]
    elif tencent_day:
        level_rows = [{"date": r["date"], "value": r["close"]} for r in tencent_day]
    if level_rows:
        change_pct = None
        if cfg["level_source"] == "csindex" and raw.get("csindex_perf"):
            change_pct = raw["csindex_perf"][-1].get("change_pct")
        elif len(level_rows) >= 2:
            prev, last = level_rows[-2]["value"], level_rows[-1]["value"]
            change_pct = round((last / prev - 1.0) * 100, 2) if prev else None
    level_weekly = normalize.to_weekly(level_rows)
    level_map = {p["date"]: p["value"] for p in level_rows}

    # ---- 估值指标序列
    value_weekly = []
    flag = "real"
    if metric == "dy":
        pe_rows = (raw.get("danjuan") or {}).get("pe") or []
        pe_weekly = normalize.to_weekly([{"date": d, "value": v} for d, v in pe_rows])
        series, meta = derive(
            cfg,
            pe_weekly,
            [{"date": r["date"], "value": r["close"]} for r in (raw.get("csindex_perf") or [])],
            [{"date": r["date"], "value": r["close"]} for r in (raw.get("csindex_tr") or [])],
            raw.get("official") or [],
            (raw.get("danjuan") or {}).get("current") or {},
        )
        value_weekly = normalize.to_weekly(series)
        anchor_value = ((raw.get("danjuan") or {}).get("current") or {}).get("dy")
        if anchor_value is None:
            from fetch.derive_yield import official_current
            _d, anchor_value = official_current(raw.get("official") or [])
        # 序列已由 derive() 做近端衰减校准，末点即官方真实值；这里只做一致性断言
        if value_weekly and anchor_value is not None and abs(value_weekly[-1]["value"] - anchor_value) > 1e-6:
            value_weekly[-1] = {"date": value_weekly[-1]["date"], "value": float(anchor_value)}
        flag = "derived"
        notes.append("股息率历史为推导序列（%s + 近端衰减校准），当前值为官方真实值" % meta.get("method"))
    else:
        source = (raw.get("danjuan") or {}).get(metric) or []
        if source:
            value_weekly = normalize.to_weekly([{"date": d, "value": v} for d, v in source])
            notes.append("估值序列来自蛋卷（第三方口径）")
        elif metric == "pe" and raw.get("csindex_perf"):
            rows = [(r["date"], r["pe_official"]) for r in raw["csindex_perf"] if r.get("pe_official")]
            value_weekly = normalize.to_weekly([{"date": d, "value": v} for d, v in rows])
            flag = "partial"
            notes.append(
                "估值序列来自中证官方 perf 接口的每日市盈率（TTM 口径，字段名 peg），"
                "官方估值字段自 %s 起（指数 2024-09-23 正式发布，行情按基日回溯、估值指标不回溯），更早无公开真实数据" % (rows[0][0] if rows else "?")
            )

    if not value_weekly:
        return None

    points = normalize.attach_level(value_weekly, level_map)
    trading_days = [r["date"] for r in level_rows]
    reb = snap_rebalance_to_trading(
        rebalance_dates(cfg.get("rebalance"), points[0]["date"], points[-1]["date"]), trading_days
    )

    # ---- 各时间范围统计量 + 「分位点 / 标准差」视图序列
    stats = {}
    views = {}
    for label, years in WINDOWS:
        window_points = normalize.window_slice(points, years)
        stats[label] = compute(window_points, direction) if window_points else None
        views[label] = stats_views(points, years)

    # ---- 并排对照序列（例如股息率口径下同时提供市盈率TTM 真实曲线）
    alternates = {}
    dj = raw.get("danjuan") or {}
    for alt in ("pe", "pb"):
        if alt == metric:
            continue
        alt_rows = dj.get(alt) or []
        if not alt_rows:
            continue
        alt_weekly = normalize.to_weekly([{"date": d, "value": v} for d, v in alt_rows])
        alt_points = normalize.attach_level(alt_weekly, level_map)
        alternates[alt] = {
            "metric": alt,
            "metric_label": METRICS[alt]["label"],
            "digits": METRICS[alt]["digits"],
            "direction": "inverse" if alt in INVERSE_METRICS else "normal",
            "flag": "real",
            "series": alt_points,
            "stats": {label: compute(normalize.window_slice(alt_points, years),
                                     "inverse" if alt in INVERSE_METRICS else "normal")
                      for label, years in WINDOWS},
            "views": {label: stats_views(alt_points, years) for label, years in WINDOWS},
        }

    # ---- 涨跌幅（美股用日线，中证用官方字段）
    last_level = level_weekly[-1]["value"] if level_weekly else None

    value_meta = {"source": "danjuan", "basis": "第三方（雪球/蛋卷）口径"}
    if metric == "dy":
        official_rows = sorted(raw.get("official") or [], key=lambda r: r["date"])
        value_meta = {
            "source": "derived",
            "method": meta.get("method"),
            "anchor": meta.get("anchor"),
            "calibration": meta.get("calibration"),
            "real_window_start": official_rows[0]["date"] if official_rows else None,
            "official_snapshot_days": len(official_rows),
            "note": "历史为推导序列；官方真实股息率自 %s 起逐日累积"
                    % (official_rows[0]["date"] if official_rows else "—"),
        }
    elif flag == "partial":
        daily = [r for r in (raw.get("csindex_perf") or []) if r.get("pe_official")]
        value_meta = {
            "source": "csindex-perf",
            "basis": "中证官方每日市盈率（TTM 口径，字段名 peg）",
            "real_window_start": daily[0]["date"] if daily else points[0]["date"],
            "index_launch_date": "2024-09-23",
            "daily_first_date": daily[0]["date"] if daily else None,
            "weekly_first_date": points[0]["date"],
            "note": "中证官方估值字段自 %s 起；指数于 2024-09-23 发布（行情按基日回溯，估值不回溯），更早无公开真实数据，本页不做推算" % (daily[0]["date"] if daily else "—"),
        }

    return {
        "key": key,
        "name": cfg["name"],
        "code": cfg["code"],
        "metric": metric,
        "metric_label": METRICS[metric]["label"],
        "digits": METRICS[metric]["digits"],
        "direction": direction,
        "flag": flag,
        "quality": QUALITY.get(key, "real"),
        "threshold_uncertainty": THRESHOLD_UNCERTAINTY.get(QUALITY.get(key, "real")),
        "recommended_window": "ALL" if flag == "partial" else DEFAULT_WINDOW,
        "value_meta": value_meta,
        "data_date": points[-1]["date"],
        "level": last_level,
        "change_pct": change_pct,
        "series": points,
        "views": views,
        "alternates": alternates,
        "stats": stats,
        "sources": cfg["sources"],
        "rebalance_dates": reb,
        "notes": notes + ([cfg["note"]] if cfg.get("note") else []),
    }


def rule_watch_payload(path=None):
    """口径监控（tools/watch_rule.py）结论 → 页面需要的字段；没有就返回 None。

    装配（run_all）与渲染（web/render.py）都走这里：渲染时重读一次，页面显示的才是
    最新一次的核对结论（工作流里口径监控跑在装配之后，只读 dashboard.json 会落后一次运行）。
    """
    path = path or os.path.join(DATA, "watch", "rule_check.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            w = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print("口径监控结果读取失败：%s" % exc)
        return None
    return {
        "checked_at": w.get("checked_at"),
        "article": (w.get("article") or {}).get("title"),
        "article_date": (w.get("article") or {}).get("date"),
        "images": w.get("images"),
        "matched": w.get("matched"),
        "mismatched": w.get("mismatched"),
        "rows": [
            {"index_name": r.get("index_name"), "author_metric": r.get("author_metric"),
             "our_metric": r.get("our_metric_label") or r.get("our_metric"), "match": r.get("match")}
            for r in (w.get("rows") or []) if r.get("index_key")
        ],
    }


def main():
    os.makedirs(SERIES, exist_ok=True)
    with open(os.path.join(SERIES, "raw_inputs.json"), encoding="utf-8") as fh:
        raw_all = json.load(fh)

    indices = []
    # 按 config.INDICES 的顺序装配（而不是抓取缓存的键序），保证展示顺序由配置决定
    for cfg in INDICES:
        raw = raw_all.get(cfg["key"])
        if not raw:
            continue
        built = build_index(cfg, raw)
        if built:
            indices.append(built)
            path = os.path.join(SERIES, "%s.json" % cfg["key"])
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(built, fh, ensure_ascii=False, indent=1)

    dashboard = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "default_window": DEFAULT_WINDOW,
        "windows": [w[0] for w in WINDOWS],
        "indices": indices,
    }
    # 口径变化监控结论（tools/watch_rule.py 产出；没有就忽略）
    watch = rule_watch_payload()
    if watch:
        dashboard["rule_watch"] = watch
    with open(DASHBOARD_JSON, "w", encoding="utf-8") as fh:
        json.dump(dashboard, fh, ensure_ascii=False, indent=1)
    print("已生成 %s（%d 个指数）" % (DASHBOARD_JSON, len(indices)))
    return dashboard


if __name__ == "__main__":
    main()
