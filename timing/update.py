"""Run once in Actions, preserve each index's last successful snapshot on failure."""
import argparse
import datetime as dt
import json
from pathlib import Path
import requests
import os
import hashlib
from timing.history import history_payload
from timing.data import SYMBOLS, validate_rows, freshness
from timing.strategy import signals, VERSION


def update(destination, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    destination = Path(destination)
    old = json.loads(destination.read_text()) if destination.exists() else {'indices':{}}
    result = dict(schema_version=1, strategy=VERSION, checked_at=now.isoformat(), **freshness(now), indices={})
    for key,symbol in SYMBOLS.items():
        previous = old['indices'].get(key, {})
        try:
            # Feed is configured only after the operator has verified automated and public-display rights.
            url = os.environ.get('TIMING_'+symbol+'_URL')
            if not url or os.environ.get('TIMING_PUBLIC_DISPLAY_LICENSED') != 'true':
                raise ValueError('数据源尚未配置或自动采集与公开展示许可未确认')
            response = requests.get(url,timeout=45)
            response.raise_for_status()
            payload = response.json()
            if payload['symbol'] != symbol or payload['instrument_type'] != 'price_index':
                raise ValueError('Index identity mismatch')
            rows = validate_rows(payload['rows'], now)
            series = signals(rows)
            last = series[-1]
            if not last['eligible']:raise ValueError('Fewer than 220 complete sessions')
            if last['date'] != result['expected_date']:raise ValueError('Expected latest completed session missing')
            result['indices'][key] = dict(symbol=symbol, latest=last, successful_at=now.isoformat(), error=None,
                history=history_payload(series,symbol,payload.get('source','已配置的价格指数数据源'),hashlib.sha256(response.content).hexdigest(),now.isoformat()))
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
            result['indices'][key] = dict(previous, symbol=symbol, error='最新数据未到／更新失败（'+type(error).__name__+'）')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    return result

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='data/timing/latest.json')
    update(p.parse_args().out)
