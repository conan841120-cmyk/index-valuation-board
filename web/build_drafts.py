# -*- coding: utf-8 -*-
"""把三个设计方向的 HTML 模板打包成可离线双击的单文件（内联数据 + ECharts）。

用法：python3 web/build_drafts.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.config import DASHBOARD_JSON  # noqa: E402
from web.render import slim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS = os.path.join(ROOT, "design", "design-demos")
SRC = os.path.join(DEMOS, "_src")
VENDOR = os.path.join(ROOT, "web", "vendor", "echarts.min.js")

DRAFTS = [
    ("A-gallery-dark.html", True),
    ("B-editorial-data.html", True),
    ("C-data-humanism.html", False),
]


def main():
    with open(DASHBOARD_JSON, encoding="utf-8") as fh:
        payload = slim(json.load(fh))
    data_js = "window.DASHBOARD = " + json.dumps(payload, ensure_ascii=False) + ";"
    with open(VENDOR, encoding="utf-8") as fh:
        echarts_js = fh.read()

    for name, need_echarts in DRAFTS:
        tpl = os.path.join(SRC, name)
        out = os.path.join(DEMOS, name)
        if not os.path.exists(tpl):
            print("跳过（模板不存在）：%s" % name)
            continue
        with open(tpl, encoding="utf-8") as fh:
            html = fh.read()
        html = html.replace("<!--DATA-->", data_js)
        html = html.replace("<!--ECHARTS-->", echarts_js if need_echarts else "")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        print("打包完成 %s（%.2f MB）" % (out, os.path.getsize(out) / 1048576.0))


if __name__ == "__main__":
    main()
