# -*- coding: utf-8 -*-
"""把 dashboard.json 渲染成单文件 HTML 看板（ECharts 与数据全部内联，可离线双击打开）。

用法：python3 web/render.py [--out outputs/估值看板.html]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.build_dataset import rule_watch_payload  # noqa: E402
from compute.config import DASHBOARD_JSON, OUTPUTS  # noqa: E402

WEB = os.path.dirname(os.path.abspath(__file__))


def current_macro_monitor(previous, today=None):
    """只读本地数据更新轮次显示，不访问宏观来源、不改写监测状态。"""
    sys.path.insert(0, os.path.join(os.path.dirname(WEB), 'macro', 'hsi'))
    from release_watch import evaluate, load_data
    return evaluate(today or datetime.now(ZoneInfo('Asia/Shanghai')).date(), load_data(), previous)


def with_fresh_rule_watch(dashboard, watch_path=None):
    """渲染前重读一次口径核对结论，覆盖 dashboard.json 里的旧副本。

    工作流里「口径变化监控」跑在「抓取 + 重算」之后，所以装配时读到的结论总是上一次的；
    页面上的口径核对行必须用最新一次的结论，否则作者改口径时红条会晚一天出现。
    """
    fresh = rule_watch_payload(watch_path)
    dashboard["rule_watch"] = fresh or {
        "state": "failed", "checked_at": None, "article_date": None,
        "matched": 0, "missing": 5, "rows": [],
    }
    return dashboard


def slim(dashboard):
    """去掉页面不需要的字段，控制单文件体积。"""
    out = {
        "generated_at": dashboard["generated_at"],
        "default_window": dashboard["default_window"],
        "windows": dashboard["windows"],
        "indices": [],
    }
    if "provenance" in dashboard:
        out["provenance"] = dashboard["provenance"]
    if dashboard.get("source_status"):
        out["source_status"] = dashboard["source_status"]
    if dashboard.get("rule_watch"):
        out["rule_watch"] = dashboard["rule_watch"]
    for idx in dashboard["indices"]:
        item = dict(idx)
        item["series"] = [
            {**p, "value": round(p["value"], 4), "level": p.get("level")}
            for p in idx["series"]
        ]
        item["stats"] = {
            w: ({k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()} if st else None)
            for w, st in idx["stats"].items()
        }
        alts = {}
        for k, alt in (idx.get("alternates") or {}).items():
            alt = dict(alt)
            alt["series"] = [
                {**p, "value": round(p["value"], 4), "level": p.get("level")}
                for p in alt["series"]
            ]
            alt["stats"] = {
                w: ({kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in st.items()} if st else None)
                for w, st in alt["stats"].items()
            }
            alts[k] = alt
        if alts:
            item["alternates"] = alts
        out["indices"].append(item)
    return out


def build(out_path):
    with open(DASHBOARD_JSON, encoding="utf-8") as fh:
        dashboard = with_fresh_rule_watch(json.load(fh))
    payload = slim(dashboard)

    with open(os.path.join(WEB, "template.html"), encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(WEB, "vendor", "echarts.min.js"), encoding="utf-8") as fh:
        echarts_js = fh.read()
    with open(os.path.join(WEB, "app.js"), encoding="utf-8") as fh:
        app_js = fh.read()

    html = html.replace("<!--ECHARTS-->", echarts_js)
    html = html.replace("<!--DATA-->", "window.DASHBOARD = " + json.dumps(payload, ensure_ascii=False) + ";")
    html = html.replace("<!--APPJS-->", app_js)
    macro_path = os.path.join(os.path.dirname(WEB), "data", "hsi_macro.json")
    macro = None
    if os.path.exists(macro_path):
        with open(macro_path, encoding="utf-8") as fh:
            macro = json.load(fh)
        monitor_path = os.path.join(os.path.dirname(WEB), "data", "hsi_macro_monitor.json")
        if os.path.exists(monitor_path):
            with open(monitor_path, encoding="utf-8") as fh:
                macro["monitor"] = current_macro_monitor(json.load(fh))
    for marker, name in [("MACROCSS", "macro.css"), ("MACROHTML", "macro.html"), ("MACROJS", "macro.js")]:
        with open(os.path.join(WEB, name), encoding="utf-8") as fh:
            html = html.replace("<!--" + marker + "-->", fh.read() if macro else "")
    macro_json = json.dumps(macro, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    html = html.replace("<!--MACRODATA-->", "window.HSI_MACRO = " + macro_json + ";")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    size_mb = os.path.getsize(out_path) / 1024.0 / 1024.0
    print("已生成 %s（%.2f MB）" % (out_path, size_mb))
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(OUTPUTS, "估值看板.html"))
    args = parser.parse_args()
    build(args.out)
