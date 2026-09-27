# -*- coding: utf-8 -*-
"""抓取层公用工具：HTTP（带 UA/Referer/重试）、原始快照落盘、北京时间转换。"""

import datetime
import json
import os
import time

import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compute.config import RAW  # noqa: E402

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CST = datetime.timezone(datetime.timedelta(hours=8))


def now_cst():
    return datetime.datetime.now(CST)


def today_str():
    return now_cst().strftime("%Y-%m-%d")


def fetch(url, *, referer=None, timeout=40, retries=3, backoff=1.5):
    """GET 并返回 Response；失败重试，最终抛出 RuntimeError。"""
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and r.content:
                return r
            last = "HTTP %s" % r.status_code
        except Exception as exc:  # noqa: BLE001
            last = repr(exc)
        if i < retries - 1:
            time.sleep(backoff * (i + 1))
    raise RuntimeError("抓取失败: %s (%s)" % (url, last))


def get_json(url, **kw):
    return fetch(url, **kw).json()


def save_raw(name, data):
    """把原始响应落盘，便于复现与审计。name 可含子目录。"""
    path = os.path.join(RAW, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(data, (bytes, bytearray)):
        with open(path, "wb") as fh:
            fh.write(data)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    return path


def ts_to_date(ts_ms):
    """毫秒时间戳 → 北京日期 YYYY-MM-DD（蛋卷的 ts 为 UTC 16:00，即北京时间次日 0 点）。"""
    return datetime.datetime.fromtimestamp(ts_ms / 1000.0, CST).strftime("%Y-%m-%d")
