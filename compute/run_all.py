# -*- coding: utf-8 -*-
"""阶段 0 主流程：抓取 → 规整 → 装配 → dashboard.json。

用法：
    cd index-valuation-board
    python3 compute/run_all.py            # 全量抓取 + 重新计算
    python3 compute/run_all.py --rebuild  # 只重算（复用 data/series/raw_inputs.json）
"""

import argparse
import datetime
import json
import math
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute import build_dataset  # noqa: E402
from compute import cache_commit  # noqa: E402
from compute.config import INDICES, SERIES  # noqa: E402
from fetch import fetch_csindex, fetch_danjuan, fetch_tencent  # noqa: E402

RAW_INPUTS = os.path.join(SERIES, "raw_inputs.json")


def _number(value):
    if isinstance(value, bool):
        raise ValueError("数值为布尔值")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("数值非有限正数")


def _date(value):
    normalized = datetime.date.fromisoformat(value).isoformat()
    if value != normalized:
        raise ValueError('日期必须为 YYYY-MM-DD')
    return normalized


def _current_date(data):
    day = data['current']['date']
    if len(day) != 5:
        return _date(day)
    anchor = datetime.date.fromisoformat(max(row[0] for field in ('pe', 'pb') for row in data[field]))
    choices = []
    for year in (anchor.year - 1, anchor.year, anchor.year + 1):
        try:
            choices.append(datetime.date.fromisoformat('%d-%s' % (year, day)))
        except ValueError:
            continue
    if not choices:
        raise ValueError('蛋卷当前日期非法')
    return min(choices, key=lambda value: abs((value - anchor).days)).isoformat()


def validate_snapshot(part, data, cfg):
    """验证适配器最终数据；空结果、业务错误与损坏行不能覆盖缓存。"""
    dates = []
    if part == "danjuan":
        if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
            raise ValueError("蛋卷响应缺少当前估值")
        current = data["current"]
        for field in ("pe", "pb", "dy"):
            _number(current.get(field))
        for field in ("pe", "pb"):
            rows = data.get(field)
            if not isinstance(rows, (list, tuple)) or not rows:
                raise ValueError("蛋卷 %s 历史为空" % field)
            series_dates = []
            for row in rows:
                day, value = row
                series_dates.append(_date(day))
                _number(value)
            if series_dates != sorted(set(series_dates)):
                raise ValueError("蛋卷历史日期重复或乱序")
            dates.extend(series_dates)
        day = current.get("date")
        if not isinstance(day, str):
            raise ValueError("蛋卷当前日期缺失")
        if len(day) == 5:
            dates.append(_current_date(data))
        else:
            dates.append(_date(day))
    else:
        if not isinstance(data, list) or not data:
            raise ValueError("%s 数据为空或格式非法" % part)
        for row in data:
            dates.append(_date(row["date"]))
            if part == "official":
                _number(row.get("pe1" if cfg["metric"] == "pe" else "dy1"))
            else:
                _number(row.get("close"))
        if dates != sorted(set(dates)):
            raise ValueError("%s 日期重复或乱序" % part)
        if part == "csindex_perf" and cfg["metric"] == "pe":
            _number(data[-1].get("pe_official"))
    return max(dates)


def validate_transition(part, previous, candidate):
    """Full-history sources retain all dates; bounded windows may roll their prefix.

Same-date numeric revisions are accepted after business validation. Removing
historical dates is not a revision. No calendar-based missing dates are invented.
"""
    if part == 'danjuan':
        if _current_date(candidate) < _current_date(previous):
            raise ValueError('蛋卷当前日期回退')
        window = previous.get('source_history') or previous
        pairs = [(window[field], candidate[field]) for field in ('pe', 'pb')]
        pairs = [([row[0] for row in old], [row[0] for row in new]) for old, new in pairs]
    else:
        pairs = [([row['date'] for row in previous], [row['date'] for row in candidate])]
    for old, new in pairs:
        if new[-1] < old[-1]:
            raise ValueError('%s 候选日期回退' % part)
        if part == 'tencent_week':
            # The unfinished weekly bar may change its date within the same week.
            identity = lambda day: datetime.date.fromisoformat(day).isocalendar()[:2]
        else:
            identity = lambda day: day
        old_ids, new_ids = set(map(identity, old)), set(map(identity, new))
        missing = old_ids - new_ids
        if not missing:
            continue
        if part == 'danjuan':
            # day=all is a rolling ten-year weekly sample plus a moving latest
            # observation, not an immutable full daily history. Check the last
            # provider window, while retaining every accepted observation below.
            if (new[-1] > old[-1] and len(new) >= len(old) - 1
                    and old_ids & new_ids
                    and all(day < new[0] or day == old[-1] for day in missing)):
                continue
            raise ValueError('danjuan 历史区间缺失或窗口异常')
        if part not in {'official', 'tencent_week', 'tencent_day'}:
            raise ValueError('%s 长历史日期缺失' % part)
        if (new[-1] <= old[-1] or len(new_ids) < len(old_ids)
                or any(day >= identity(new[0]) for day in missing)):
            raise ValueError('%s 窗口历史缺失' % part)


def _official_path(code):
    return os.path.join(fetch_csindex.SNAPSHOTS, 'indicator_%s.csv' % code)


def recover_cache():
    paths = [RAW_INPUTS] + [_official_path(cfg['sources']['csindex'])
                          for cfg in INDICES if cfg.get('sources', {}).get('csindex')]
    return cache_commit.recover(RAW_INPUTS, paths)


def fetch_all(previous=None):
    """每路先验证候选数据，再替换缓存；失败保留上次成功快照。"""
    if recover_cache():
        previous = None
        if os.path.exists(RAW_INPUTS):
            with open(RAW_INPUTS, encoding='utf-8') as fh:
                previous = json.load(fh)
    raw_all = {k: dict(v) for k, v in (previous or {}).items()}
    csv_updates = {}
    for cfg in INDICES:
        key = cfg["key"]
        src = cfg.get("sources") or {}
        raw = dict(raw_all.get(key) or {})
        status = dict(raw.get("_status") or {})
        print("[抓取] %s %s" % (key, cfg["name"]))

        def attempt(part, loader):
            at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
            old_status = status.get(part) or {}
            fields = ("tencent_week", "tencent_day") if part == "tencent" else (part,)
            old_date = old_status.get("last_data_date")
            fallback = False
            try:
                old_dates = [validate_snapshot(f, raw.get(f), cfg) for f in fields]
                old_date = max(old_dates)
                fallback = True
            except (TypeError, ValueError, KeyError):
                pass
            try:
                candidate = loader()
                values = candidate if part == "tencent" else (candidate,)
                if len(values) != len(fields):
                    raise ValueError('候选字段不完整')
                dates = [validate_snapshot(f, value, cfg) for f, value in zip(fields, values)]
                for field, value in zip(fields, values):
                    try:
                        validate_snapshot(field, raw.get(field), cfg)
                    except (TypeError, ValueError, KeyError):
                        continue
                    validate_transition(field, raw[field], value)
                if part == 'danjuan':
                    candidate = dict(candidate)
                    candidate['source_history'] = {f: candidate[f] for f in ('pe', 'pb')}
                    for field in ('pe', 'pb'):
                        merged = dict(raw['danjuan'][field]) if fallback else {}
                        merged.update(candidate[field])
                        candidate[field] = sorted(merged.items())
                    values = (candidate,)
                if part == 'official':
                    history = fetch_csindex.load_indicator_csv(src['csindex'])
                    if history:
                        validate_snapshot('official', history, cfg)
                        validate_transition('official', history[-20:], candidate)
                    csv_updates[_official_path(src['csindex'])] = fetch_csindex.indicator_csv_bytes(src['csindex'], candidate)
                # 腾讯周线、日线全部有效后才一起替换。
                raw.update(dict(zip(fields, values)))
                status[part] = {"ok": True, "at": at, "last_success_at": at,
                                "last_data_date": max(dates), "fallback": False, "detail": ""}
                print("   %s: 已验证，最新 %s" % (part, max(dates)))
            except Exception as exc:  # noqa: BLE001
                status[part] = {"ok": False, "at": at,
                                "last_success_at": old_status.get("last_success_at") or
                                    (old_status.get("at") if old_status.get("ok") else None),
                                "last_data_date": old_date, "fallback": fallback, "detail": str(exc)}
                print("   %s 失败（%s），%s" % (part, exc, "沿用上次快照" if fallback else "无有效旧快照"))

        if src.get("danjuan"):
            attempt("danjuan", lambda: fetch_danjuan.fetch_index(cfg))
        if src.get("csindex"):
            attempt("csindex_perf", lambda: fetch_csindex.fetch_perf(src["csindex"]))
            attempt("official", lambda: fetch_csindex.fetch_indicator(src["csindex"]))
        if src.get("csindex_tr"):
            attempt("csindex_tr", lambda: fetch_csindex.fetch_perf(src["csindex_tr"]))
        if src.get("tencent"):
            attempt("tencent", lambda: (fetch_tencent.fetch_kline(src["tencent"], "week", 600),
                                        fetch_tencent.fetch_kline(src["tencent"], "day", 1200)))
        raw["_status"] = status
        raw_all[key] = raw

    os.makedirs(SERIES, exist_ok=True)
    content = json.dumps(raw_all, ensure_ascii=False, allow_nan=False).encode('utf-8')
    cache_commit.commit(RAW_INPUTS, content, csv_updates)
    return raw_all


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="跳过抓取，用现有 raw_inputs.json 重算")
    args = parser.parse_args()
    recover_cache()

    if args.rebuild:
        print("[重算] 复用 %s" % RAW_INPUTS)
    else:
        previous = None
        if os.path.exists(RAW_INPUTS):
            with open(RAW_INPUTS, encoding="utf-8") as fh:
                previous = json.load(fh)
            print("[抓取] 载入上一次快照作为失败兜底（%d 个指数）" % len(previous))
        fetch_all(previous)

    dashboard = build_dataset.main()
    print("\n%-12s %-10s %-6s %-10s %-8s %-9s %-9s %-9s %s"
          % ("指数", "指标", "窗口", "数据日期", "当前值", "分位点", "危险值", "机会值", "区间"))
    for idx in dashboard["indices"]:
        st = idx["stats"].get(dashboard["default_window"]) or {}
        print("%-12s %-10s %-6s %-10s %-8.2f %-8.2f%% %-9.2f %-9.2f %s"
              % (idx["name"], idx["metric_label"], dashboard["default_window"], idx["data_date"],
                 st.get("current", float("nan")), st.get("percentile", float("nan")),
                 st.get("danger", float("nan")), st.get("opportunity", float("nan")), st.get("zone", "")))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
