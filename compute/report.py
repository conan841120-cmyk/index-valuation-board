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
    derive,
)
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
EPS = 1e-9


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
            return "✅" if abs_dev <= tol["current_abs"] + EPS else "❌"
        limit = tol.get("current_pct")
        if limit is None:
            return "仅记录"
        return "✅" if (rel_dev is not None and abs(rel_dev) <= limit + EPS) else "❌"
    if field == "percentile":
        limit = tol.get("percentile_pp")
        if limit is None:
            return "近似（不设限）"
        return "✅" if abs_dev <= limit + EPS else "❌"
    if field == "zscore":
        return "✅" if abs_dev <= tol.get("zscore_abs", 9) + EPS else "❌"
    if field in THRESHOLD_FIELDS:
        limit = tol.get("threshold_pct")
        if limit is None:
            return "仅记录"
        if rel_dev is None:
            return "—"
        value = abs(rel_dev)
        return "✅" if value <= limit + EPS else ("⚠️" if value <= limit * 1.5 + EPS else "❌")
    # 极值、平均值、标准差等：真实序列按阈值容差，推导序列只记录
    if quality == "derived":
        return "近似（仅记录）"
    limit = tol.get("threshold_pct")
    if limit is None or rel_dev is None:
        return "仅记录"
    return "✅" if abs(rel_dev) <= limit * 1.5 + EPS else "⚠️"


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
        cur = dict(dj.get("current") or {})
        cur["fetched_at"] = dj.get("fetched_at")
        out = {}
        anchor = None
        for name in ("full_return", "pe_anchored", "blend"):
            points, meta = derive(cfg, pe_rows, price, tr, official, cur, method=name)
            anchor = meta.get("anchor")
            weekly = normalize.to_weekly(points)
            window = normalize.window_slice(weekly, 10)
            st = compute(window, "inverse")
            if st:
                out[name] = st
        rows[cfg["key"]] = {"name": cfg["name"], "methods": out, "anchor": anchor}
    return rows


def comparison_summary(dashboard, reference):
    """只统计同日、同口径且未作废的截图；仅记录字段不计入通过数。"""
    by_key = {i["key"]: i for i in dashboard["indices"]}
    result = {}
    for key, idx in by_key.items():
        result[key] = {"observations": 0, "checked": 0, "failed": 0}
    for obs in reference["observations"]:
        idx = by_key.get(obs["index_key"])
        if (not idx or not obs.get("stats") or obs.get("obsolete")
                or obs.get("metric") != idx["metric"]
                or not obs.get("data_date")
                or obs["data_date"] != idx.get("data_date")):
            continue
        summary = result[idx["key"]]
        summary["observations"] += 1
        stats = idx["stats"].get(dashboard["default_window"]) or {}
        for field, _label, kind in FIELDS:
            _text, abs_dev, rel_dev = deviation(obs["stats"].get(field), stats.get(field), field, kind)
            verdict = judge(QUALITY.get(idx["key"], "real"), field, abs_dev, rel_dev, idx)
            if verdict in ("✅", "❌", "⚠️"):
                summary["checked"] += 1
                summary["failed"] += verdict != "✅"
        if obs.get("level") and idx.get("level"):
            summary["checked"] += 1
            rel = abs(idx["level"] - obs["level"]) / abs(obs["level"]) * 100
            summary["failed"] += rel > 3.0 + 1e-9
    return result


def conclusion_lines(dashboard, reference):
    summaries = comparison_summary(dashboard, reference)
    lines = []
    for idx in dashboard["indices"]:
        summary = summaries[idx["key"]]
        if not summary["checked"]:
            status = "本期未验证（无可判定的同期同口径字段）"
        else:
            status = "同期基准 %d 条，实测判定 %d 个字段；通过 %d，失败/超出容差 %d" % (
                summary["observations"], summary["checked"],
                summary["checked"] - summary["failed"], summary["failed"])
        lines.append("- **%s · %s**：%s。" % (idx["name"], idx["data_date"], status))
        if idx.get("metric") == "dy":
            meta = idx.get("value_meta") or {}
            anchor = meta.get("anchor_observation") or {}
            current_kind = "同期第三方观测" if meta.get("current_is_observed") else "模型推导值（未证实为本期真实观测）"
            lines.append("  当前值性质：%s；锚点来源 %s，锚点日期 %s。同期截图比对只核验显示数值的拟合，不验证其真实历史。" % (
                current_kind, anchor.get("source") or "未标注", anchor.get("date") or "未标注"))
    lines.extend([
        "- 蛋卷 PE/PB 与主指标股息率的当前锚点采用第三方口径；中证官方股息率1/2为独立口径，不互相替代。实际来源与日期以数据元信息为准。",
        "- 股息率历史使用 current_anchor 模型作事后估算：以本期锚点校准过去的分布，不能当作当时可知的择时信号或用于声称历史择时收益。",
        "- derived 的容差仅用于特定截图的拟合诊断，不是对真实历史、未来数据或投资结果的误差保证；分位点无准确性保证。",
        "- 中证A500 只展示已有真实区间；短区间的 10Y 标签不代表具备完整十年估值历史。",
        "- 官方估值 CSV 会逐次累积，作为独立 alternate 序列保留，不能把不同股息率口径拼进主指标历史。",
        "- 无同期截图时，结构、公式和自洽性测试通过也不能证明本期数字与作者截图一致。"
    ])
    return lines


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
        qlabel = {"real": "真实", "derived": "历史推导 / 当前性质见结论", "partial": "真实但区间不足"}[quality]
        lines.append("| %s | %s | %s | %s | %s | %s | %s ~ %s | %s |" % (
            idx["name"], idx["metric_label"], "越高越便宜（反向）" if idx["direction"] == "inverse" else "越高越贵",
            idx["data_date"], "%.2f" % idx["level"] if idx["level"] else "—",
            (idx.get("value_meta") or {}).get("basis") or idx.get("source") or "未标注",
            first, idx["series"][-1]["date"], qlabel))

    # ---------- 2. 与截图逐项对照
    lines.append("\n## 2. 与作者截图逐项对照（10Y 窗口，复算值 vs 截图值）\n")
    lines.append("> 作者的数字每天也在重算，所以只有「基准数据日 = 本期数据日」的对照才作判定；"
                 "过期基准仅记录偏差，不作判定（拿过期快照比数字是刻舟求剑）。\n")
    summary = []
    for obs in reference["observations"]:
        key = obs["index_key"]
        idx = by_key.get(key)
        if not idx or obs.get("stats") is None or obs.get("obsolete"):
            continue
        if obs.get("metric") != idx["metric"]:
            lines.append("### %s（截图口径 %s，已作废）\n" % (idx["name"], obs["metric"].upper()))
            lines.append("> %s\n" % obs.get("note", ""))
            continue
        quality = QUALITY.get(key, "real")
        stats = idx["stats"].get(window)
        # 作者的数字每天也在重算：只有同一数据日的基准才有资格判定，过期基准只记录
        same_period = bool(obs.get("data_date")) and obs.get("data_date") == idx.get("data_date")
        lines.append("### %s · %s · %s（截图 %s）\n"
                     % (idx["name"], idx["metric_label"], window, obs["article"]))
        lines.append("> 基准数据日：%s ｜ 本期数据日：%s ｜ %s\n"
                     % (obs.get("data_date") or "未标注", idx.get("data_date"),
                        "**同期，逐项判定**" if same_period else "**过期基准，仅记录不判定**"))
        if stats:
            lines.append("> 有效窗口：%s ~ %s（n=%d 个周频点）\n"
                         % (stats["start"], stats["end"], stats["n"]))
        lines.append("| 指标 | 截图值 | 复算值 | 偏差 | 判定 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for field, label, kind in FIELDS:
            shot = obs["stats"].get(field)
            ours = (stats or {}).get(field)
            dev_text, abs_dev, rel_dev = deviation(shot, ours, field, kind)
            verdict = judge(quality, field, abs_dev, rel_dev, idx) if same_period else "—（过期基准）"
            lines.append("| %s | %s | %s | %s | %s |" % (
                label, fmt(shot, kind), fmt(ours, kind), dev_text, verdict))
        shot_level, our_level = obs.get("level"), idx.get("level")
        if shot_level and our_level:
            rel_level = (our_level - shot_level) / shot_level * 100
            level_verdict = "✅" if (same_period and abs(rel_level) <= 3.0) else (
                "❌" if same_period else "—（过期基准）")
            lines.append("| 指数点位 | %.2f | %.2f | %+.2f%% | %s |"
                         % (shot_level, our_level, rel_level, level_verdict))
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
        lines.append("| %s | **截图（比对基准）** | 见第 2 节 | | | | | | | |" % data["name"])

    # ---------- 4. 结论与限制
    lines.append("\n## 4. 结论与已知限制\n")
    lines.extend(conclusion_lines(dashboard, reference))

    os.makedirs(OUTPUTS, exist_ok=True)
    path = os.path.join(OUTPUTS, "口径与误差报告.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已生成 %s（%d 个指数对照）" % (path, len(summary)))
    return path


if __name__ == "__main__":
    main()
