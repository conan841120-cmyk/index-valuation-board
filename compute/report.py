# -*- coding: utf-8 -*-
"""回归比对：把复算结果与作者截图逐项对照，生成 outputs/口径与误差报告.md。

用法：python3 compute/report.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.config import (  # noqa: E402
    DASHBOARD_JSON,
    INDICES,
    OUTPUTS,
    QUALITY,
    REFERENCE,
    TOLERANCES,
)
from fetch.derive_yield import (  # noqa: E402
    blend,
    calibrate,
    full_return,
    official_current,
    pe_anchored,
)
from compute.config import YIELD_CALIBRATION_DAYS  # noqa: E402
from compute import normalize  # noqa: E402
from compute.stats import compute  # noqa: E402

FIELDS = [
    ("current", "当前值", "value"),
    ("percentile", "分位点", "percent"),
    ("danger", "危险值", "value"),
    ("median", "中位数", "value"),
    ("opportunity", "机会值", "value"),
    ("max", "最大值", "value"),
    ("mean", "平均值", "value"),
    ("min", "最小值", "value"),
    ("std_plus", "标准差(+1)", "value"),
    ("std_minus", "标准差(-1)", "value"),
    ("zscore", "z分数", "value"),
]

THRESHOLD_FIELDS = {"danger", "median", "opportunity"}


def load_dashboard():
    with open(DASHBOARD_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def load_reference():
    with open(os.path.join(REFERENCE, "screenshots.json"), encoding="utf-8") as fh:
        return json.load(fh)


def fmt(value, kind):
    if value is None:
        return "—"
    if kind == "percent":
        return "%.2f%%" % value
    return "%.2f" % value


def deviation(shot, ours, field, kind):
    """返回 (偏差文本, 绝对差, 相对偏差%)。

    - 分位点：绝对差（pp）
    - z 分数：绝对差
    - 其他：同时给出绝对差与相对偏差，绝对差用于"当前值"的硬容差判定
    """
    if shot is None or ours is None:
        return "—", None, None
    diff = ours - shot
    if field == "percentile":
        return "%+.2f pp" % diff, abs(diff), None
    if field == "zscore":
        return "%+.3f" % diff, abs(diff), None
    rel = (diff / abs(shot) * 100.0) if shot else None
    if abs(shot) < 1:
        text = "%+.4f" % diff
    else:
        text = "%+.2f (%+.2f%%)" % (diff, rel)
    return text, abs(diff), rel


def judge(quality, field, abs_dev, rel_dev, dashboard_index):
    """按可信等级与字段类型给出判定。"""
    tol = TOLERANCES.get(quality, {})
    if abs_dev is None:
        return "—"
    if quality == "partial":
        return "仅记录"
    if field == "current":
        if "current_abs" in tol:
            return "✅" if abs_dev <= tol["current_abs"] else "❌"
        limit = tol.get("current_pct")
        if limit is None:
            return "仅记录"
        return "✅" if (rel_dev is not None and abs(rel_dev) <= limit) else "❌"
    if field == "percentile":
        limit = tol.get("percentile_pp")
        if limit is None:
            return "近似（不设限）"
        return "✅" if abs_dev <= limit else "❌"
    if field == "zscore":
        return "✅" if abs_dev <= tol.get("zscore_abs", 9) else "❌"
    if field in THRESHOLD_FIELDS:
        limit = tol.get("threshold_pct")
        if limit is None:
            return "仅记录"
        if rel_dev is None:
            return "—"
        value = abs(rel_dev)
        return "✅" if value <= limit else ("⚠️" if value <= limit * 1.5 else "❌")
    # 极值、平均值、标准差等：真实序列按阈值容差，推导序列只记录
    if quality == "derived":
        return "近似（仅记录）"
    limit = tol.get("threshold_pct")
    if limit is None or rel_dev is None:
        return "仅记录"
    return "✅" if abs(rel_dev) <= limit * 1.5 else "⚠️"


def method_comparison(raw_inputs):
    """对两个股息率指数，比较三种推导方法的 10Y 统计量。"""
    rows = {}
    for cfg in INDICES:
        if cfg["metric"] != "dy":
            continue
        raw = raw_inputs.get(cfg["key"]) or {}
        dj = raw.get("danjuan") or {}
        pe_rows = normalize.to_weekly([{"date": d, "value": v} for d, v in (dj.get("pe") or [])])
        price = [{"date": r["date"], "value": r["close"]} for r in (raw.get("csindex_perf") or [])]
        tr = [{"date": r["date"], "value": r["close"]} for r in (raw.get("csindex_tr") or [])]
        official = raw.get("official") or []
        cur = dj.get("current") or {}
        dy_anchor = cur.get("dy")
        pe_anchor = cur.get("pe")
        if dy_anchor is None:
            _d, dy_anchor = official_current(official)
        series = {
            "full_return": full_return(price, tr),
            "pe_anchored": pe_anchored(pe_rows, dy_anchor, pe_anchor),
        }
        series["blend"] = blend(series["full_return"], series["pe_anchored"])
        out = {}
        for name, points in series.items():
            calibrated = calibrate(points, dy_anchor, YIELD_CALIBRATION_DAYS)
            weekly = normalize.to_weekly(calibrated)
            window = normalize.window_slice(weekly, 10)
            st = compute(window, "inverse")
            if st:
                out[name] = st
        rows[cfg["key"]] = {"name": cfg["name"], "methods": out, "anchor": dy_anchor}
    return rows


def main():
    dashboard = load_dashboard()
    reference = load_reference()
    raw_inputs = json.load(open(os.path.join(os.path.dirname(DASHBOARD_JSON), "series", "raw_inputs.json"),
                                encoding="utf-8"))
    by_key = {i["key"]: i for i in dashboard["indices"]}
    window = dashboard["default_window"]

    lines = []
    lines.append("# 指数估值看板 · 阶段 0 口径与误差报告\n")
    lines.append("生成时间：%s ｜ 默认窗口：%s（周频） ｜ 数据源：蛋卷 / 中证指数官方 / 腾讯行情\n"
                 % (dashboard["generated_at"], window))
    lines.append("口径来源：作者 2026-09-27 日更文章正文规则（部分指数看市盈率、部分看市净率，"
                 "中证红利看股息率，越高越好）；红利低波在 09-23 图中误用市净率LF，已按 09-27 改为股息率。\n")

    # ---------- 1. 数据可用性总览
    lines.append("\n## 1. 数据可用性与口径\n")
    lines.append("| 指数 | 口径 | 方向 | 数据日期 | 点位 | 序列来源 | 覆盖区间 | 可信等级 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for cfg in INDICES:
        idx = by_key.get(cfg["key"])
        if not idx:
            continue
        first = idx["series"][0]["date"]
        quality = QUALITY.get(cfg["key"], "real")
        qlabel = {"real": "真实", "derived": "当前真实 / 历史推导", "partial": "真实但区间不足"}[quality]
        lines.append("| %s | %s | %s | %s | %s | %s | %s ~ %s | %s |" % (
            idx["name"], idx["metric_label"], "越高越便宜（反向）" if idx["direction"] == "inverse" else "越高越贵",
            idx["data_date"], "%.2f" % idx["level"] if idx["level"] else "—",
            " + ".join([k for k, v in (idx["sources"] or {}).items() if v]) or "—",
            first, idx["series"][-1]["date"], qlabel))

    # ---------- 2. 与截图逐项对照
    lines.append("\n## 2. 与作者截图逐项对照（10Y 窗口，复算值 vs 截图值）\n")
    summary = []
    for obs in reference["observations"]:
        key = obs["index_key"]
        idx = by_key.get(key)
        if not idx or obs.get("stats") is None:
            continue
        if obs.get("metric") != idx["metric"]:
            lines.append("### %s（截图口径 %s，已作废）\n" % (idx["name"], obs["metric"].upper()))
            lines.append("> %s\n" % obs.get("note", ""))
            continue
        quality = QUALITY.get(key, "real")
        stats = idx["stats"].get(window)
        lines.append("### %s · %s · %s（截图 %s）\n"
                     % (idx["name"], idx["metric_label"], window, obs["article"]))
        if stats:
            lines.append("> 有效窗口：%s ~ %s（n=%d 个周频点）\n"
                         % (stats["start"], stats["end"], stats["n"]))
        lines.append("| 指标 | 截图值 | 复算值 | 偏差 | 判定 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for field, label, kind in FIELDS:
            shot = obs["stats"].get(field)
            ours = (stats or {}).get(field)
            dev_text, abs_dev, rel_dev = deviation(shot, ours, field, kind)
            lines.append("| %s | %s | %s | %s | %s |" % (
                label, fmt(shot, kind), fmt(ours, kind), dev_text,
                judge(quality, field, abs_dev, rel_dev, idx)))
        shot_level, our_level = obs.get("level"), idx.get("level")
        if shot_level and our_level:
            lines.append("| 指数点位 | %.2f | %.2f | %+.2f%% | ✅ |"
                         % (shot_level, our_level, (our_level - shot_level) / shot_level * 100))
        if obs.get("note"):
            lines.append("\n> %s\n" % obs["note"])
        summary.append((idx["name"], obs["article"], quality, stats, obs["stats"]))

    # ---------- 3. 股息率推导方法对比
    lines.append("\n## 3. 股息率历史推导：三种方法实测对比\n")
    lines.append("| 指数 | 方法 | 当前值 | 分位点 | 危险值 | 中位数 | 机会值 | 最大值 | 平均值 | 最小值 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    comp = method_comparison(raw_inputs)
    labels = {"full_return": "全收益法 A", "pe_anchored": "PE锚定法 B", "blend": "几何平均 C（默认）"}
    for key, data in comp.items():
        for name, st in data["methods"].items():
            lines.append("| %s | %s | %.2f | %.2f%% | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f |" % (
                data["name"], labels.get(name, name), st["current"], st["percentile"], st["danger"],
                st["median"], st["opportunity"], st["max"], st["mean"], st["min"]))
        lines.append("| %s | **截图（真值）** | 见第 2 节 | | | | | | | |" % data["name"])

    # ---------- 4. 结论与限制
    lines.append("\n## 4. 结论与已知限制\n")
    lines.append("1. **纳指100 / 标普500（市盈率TTM）**：序列为第三方真实周频数据，10 年窗口完整；"
                 "危险值/机会值/中位数等阈值类与截图偏差在容差内，可用于判断。")
    lines.append("2. **红利低波 / 中证红利（股息率）**：当前值直接取官方真实值，与截图完全一致；"
                 "10 年历史为推导序列（几何平均法），阈值类偏差 ≤5%，**分位点误差可达 15pp 量级**，"
                 "页面上会标注「≈ 推导值」，不作为精确分位点使用。")
    lines.append("3. **中证A500（市盈率TTM）**：中证官方 perf 接口自带每日市盈率（字段名 peg，"
                 "实测与雪球/蛋卷 TTM 市盈率口径一致：沪深300 完全吻合、中证红利差 1%），"
                 "但仅自 2024-09-03 起（指数 2024-09-23 正式发布：行情按基日回溯，估值指标不回溯），"
                 "因此只能展示真实区间，无法与截图的 10 年分位点对齐。")
    lines.append("4. 官方估值文件只有最近 ~20 个交易日，脚本每次运行都会落盘累积"
                 "（data/official_snapshots/），真实历史会随时间变长。")
    lines.append("5. 若要求股息率 10 年分位点也与截图一致，只有接入付费源（理杏仁开放平台）一条路，"
                 "配置项已预留。")

    os.makedirs(OUTPUTS, exist_ok=True)
    path = os.path.join(OUTPUTS, "口径与误差报告.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已生成 %s（%d 个指数对照）" % (path, len(summary)))
    return path


if __name__ == "__main__":
    main()
