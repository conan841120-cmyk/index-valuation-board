# -*- coding: utf-8 -*-
"""腾讯行情适配器（美股指数点位：纳指100 = usNDX，标普500 = us.INX）。

实测：周线 600 根回到 2015-03；日线可用。中证指数走官方 perf 接口，不用腾讯。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch.common import get_json, save_raw  # noqa: E402

URL = "https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get"


def fetch_kline(code, period="week", count=600):
    """period: week | day。返回 [{date, close}] 升序。"""
    url = "%s?param=%s,%s,,,%d,qfq" % (URL, code, period, count)
    data = get_json(url, referer="https://gu.qq.com/")
    save_raw("tencent_%s_%s.json" % (code.replace(".", ""), period), data)
    block = (data.get("data") or {}).get(code) or {}
    rows = block.get(period) or block.get("qfq" + period) or []
    out = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        try:
            out.append({"date": row[0], "close": float(row[2])})
        except (TypeError, ValueError):
            continue
    return sorted(out, key=lambda r: r["date"])


if __name__ == "__main__":
    for c in ("usNDX", "us.INX"):
        wk = fetch_kline(c, "week", 600)
        print(c, "周线", len(wk), wk[0] if wk else None, wk[-1] if wk else None)
