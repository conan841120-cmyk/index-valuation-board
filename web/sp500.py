"""Build a separate static dashboard with the site's existing editorial design."""
import json
import datetime as dt
import math
from pathlib import Path
import shutil
from web.navigation import CSS as NAV_STYLE, navigation

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent


def validate(value):
    if value.get('schema_version') != 1 or value.get('symbol') != '^GSPC':
        raise ValueError('Invalid S&P 500 snapshot')
    for key in ('daily', 'event_stats', 'state_stats', 'baselines', 'events'):
        if not isinstance(value['queries'][key]['rows'], list):
            raise ValueError('Invalid S&P 500 rows')
    rows = value['queries']['daily']['rows']
    if not rows or rows[0]['date'] < '1950-01-01' or rows[-1]['date'] != value['research']['data_end']:
        raise ValueError('Invalid S&P 500 date range')
    if any(a['date'] >= b['date'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Unordered daily history')
    def date(text):
        if dt.date.fromisoformat(text).isoformat() != text:
            raise ValueError('Invalid market date')
    for row in rows:
        date(row['date'])
        for key in ('close', 'sma60', 'sma200', 'bias60', 'bias200'):
            number = row[key]
            if not isinstance(number, (int, float)) or not math.isfinite(number):
                raise ValueError('Invalid market number')
        if min(row['close'], row['sma60'], row['sma200']) <= 0:
            raise ValueError('Nonpositive market number')
    for name in ('event_stats', 'state_stats', 'baselines'):
        for row in value['queries'][name]['rows']:
            if row['start_year'] not in (1950, 1970, 2000, 2010) or row['horizon'] not in (5, 20, 60):
                raise ValueError('Invalid statistics period')
            if not isinstance(row['n'], int) or row['n'] < 0:
                raise ValueError('Invalid statistics count')
            for key, number in row.items():
                if key == 'side':
                    if number not in ('bottom', 'top'): raise ValueError('Invalid event side')
                    continue
                if number is None: continue
                numbers = number if isinstance(number, list) else [number]
                if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in numbers):
                    raise ValueError('Invalid statistics number')
    for row in value['queries']['events']['rows']:
        date(row['signal_date']); date(row['reference_date'])
        if row['side'] not in ('bottom', 'top') or row['ma'] not in (60, 200):
            raise ValueError('Invalid historical event')
        for key in ('threshold_pct', 'deviation_pct', 'reference_close', 'return_5', 'return_20', 'return_60'):
            if not isinstance(row[key], (int, float)) or not math.isfinite(row[key]):
                raise ValueError('Invalid event number')
    return value


def build(source, out):
    source, out = Path(source), Path(out)
    if not source.exists():
        source = ROOT / 'data/sp500/bootstrap.json'
    data = validate(json.loads(source.read_text(encoding='utf-8')))
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    template = (WEB / 'sp500.html').read_text(encoding='utf-8')
    html = template.replace('<!--NAV-->', navigation('sp500')).replace('<!--STYLE-->',
             NAV_STYLE + (WEB / 'sp500.css').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(html, encoding='utf-8')
    (out / 'snapshot.json').write_text(encoded, encoding='utf-8')
    shutil.copy2(WEB / 'sp500.js', out / 'sp500.js')
    return out / 'index.html'
