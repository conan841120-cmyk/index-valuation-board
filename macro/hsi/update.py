"""Cloud refresh with per-source rollback; emit a reviewed monthly web snapshot."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.common import ROOT
from src.indicators.leading_indicator import build, load_config, FACTORS

BOARD = ROOT.parents[1]
DATASETS = ('retail', 'ppi', 'hk_m2', 'social_financing', 'gdp', 'hsi')
LABELS = dict(zip(DATASETS, ['社零同比', '出厂价格同比', '香港广义货币总额同比', '社融增量', '当季名义国内生产总值', '恒生指数']))
DESTINATION = BOARD / 'data/hsi_macro.json'


def load_data():
    return {name: pd.read_csv(ROOT / f'data/processed/{name}.csv') for name in DATASETS}


def validate_source(name, frame, previous=None):
    valid = frame.dropna(subset='value')
    if valid.empty or frame.observation_period.duplicated().any():
        raise ValueError(f'{name}: empty values or duplicate periods')
    unit = 'CNY_100million' if name in ('gdp', 'social_financing') else 'index_points' if name == 'hsi' else 'percent'
    if not frame.unit.eq(unit).all():
        raise ValueError(f'{name}: expected {unit}')
    if previous is not None:
        old = previous.dropna(subset='value')
        if valid.observation_period.max() < old.observation_period.max():
            raise ValueError(f'{name}: refreshed history ends earlier than cache')
        lost = set(old.observation_period) - set(valid.observation_period)
        if lost:
            raise ValueError(f'{name}: refreshed source lost {len(lost)} previously valid months')


def transactional_refresh(action, paths):
    """Restore processed inputs on download/parse/validation failure."""
    backup = {p: p.read_bytes() if p.exists() else None for p in paths}
    try:
        action()
    except Exception:
        for p, content in backup.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(content)
        raise


def refresh_sources():
    from src.data import download_nbs, download_pboc, download_hkma, download_hsi, download_release_dates
    actions = {'retail': lambda: download_nbs.download('retail', True),
        'ppi': lambda: download_nbs.download('ppi', True), 'gdp': lambda: download_nbs.download('gdp', True),
        'social_financing': lambda: download_pboc.download(True),
        'hk_m2': lambda: download_hkma.download(True), 'hsi': lambda: download_hsi.download(True)}
    prior = json.loads(DESTINATION.read_text()) if DESTINATION.exists() else {}
    previous_status = {r['dataset']: r for r in prior.get('sources', [])}
    status = {}
    for name in DATASETS:
        path = ROOT / f'data/processed/{name}.csv'
        old = pd.read_csv(path) if path.exists() else None
        def action(name=name, old=old):
            frame = actions[name]()
            validate_source(name, frame, old)
            # Keep documented dates until the release-list step adds newer ones.
            if old is not None:
                dates = old.set_index('observation_period')
                for column in ('release_date', 'release_source_url', 'release_title'):
                    if column in dates:
                        mapped = frame.observation_period.map(dates[column])
                        frame[column] = frame[column].fillna(mapped) if column in frame else mapped
            frame.to_csv(path, index=False)
        try:
            transactional_refresh(action, [path])
            status[name] = {'state': 'fresh', 'last_success_at': now(), 'error': None}
        except Exception as error:
            if old is None:
                raise
            validate_source(name, old)
            status[name] = {'state': 'cached', 'last_success_at': previous_status.get(name, {}).get('last_success_at'),
                'error': str(error)[:500]}
            print(f'CACHE FALLBACK {name}: {error}', flush=True)
    release_status = []
    for name, action, affected in [('nbs', download_release_dates.nbs, ['retail', 'ppi', 'gdp', 'nbs_release_dates']),
        ('pboc', download_release_dates.pboc, ['social_financing', 'pboc_release_dates'])]:
        try:
            transactional_refresh(lambda action=action: action(True), [ROOT / f'data/processed/{n}.csv' for n in affected])
            release_status.append({'source': name, 'state': 'fresh', 'error': None})
        except Exception as error:
            release_status.append({'source': name, 'state': 'cached', 'error': str(error)[:500]})
            print(f'RELEASE DATE FALLBACK {name}: {error}', flush=True)
    return status, release_status


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def make_snapshot(data, frame, config, status, release_status):
    rows = frame.loc[config['composite_start']:].reset_index()
    rows['date'] = rows.date.astype(str)
    for column in rows:
        if pd.api.types.is_datetime64_any_dtype(rows[column]):
            rows[column] = rows[column].dt.strftime('%Y-%m-%d')
    points = json.loads(rows.to_json(orient='records', double_precision=15))
    valid = [p for p in points if p['leading_indicator'] is not None]
    if not valid or valid[0]['date'] != '2012-07':
        raise ValueError('Composite must begin 2012-07')
    latest = valid[-1]
    prior_month = str(pd.Period(latest['date'], 'M') - 1)
    previous = next((p for p in points if p['date'] == prior_month), None)
    for p in valid:
        total = sum(p['contribution_' + factor] for factor in FACTORS)
        if abs(total - p['leading_indicator']) > 1e-12:
            raise ValueError('Contribution sum does not reconcile')
    sources = []
    for name, source in data.items():
        validate_source(name, source)
        good = source.dropna(subset='value');last = good.iloc[-1]
        sources.append({'dataset': name, 'label': LABELS[name], 'official_field': last.official_field if 'official_field' in last else {'social_financing':'社会融资规模增量（月度）','hsi':'恒生指数月末收盘价'}[name],
            'latest_observation': str(last.observation_period), 'release_date': None if pd.isna(last.release_date) else str(last.release_date),
            'url': last.source_url, 'unit': last.unit, 'valid_rows': len(good), 'missing_rows': int(source.value.isna().sum()),
            'sha256': hashlib.sha256((ROOT / f'data/processed/{name}.csv').read_bytes()).hexdigest(),
            **status[name]})
    return {'schema_version': 1, 'generated_at': now(), 'title': '恒生指数领先指标（实时标准化版）',
        'config': config, 'sources': sources, 'release_lookup_status': release_status, 'series': points,
        'latest': latest, 'previous': previous, 'missing_months': int(rows.leading_indicator.isna().sum()),
        'vintage_certified': False,
        'methods': ['四项分别按36个月半衰期加权标准化，使用显式无偏加权方差，再各乘0.25合成。',
            '信用脉冲＝（最近6个月社融增量－去年同期6个月社融增量）÷最近两个季度名义GDP，再取过去3个月均值。',
            'GDP在季度末月份更新并沿用；缺失值保留，历史图用虚线连接有效端点。',
            '月份表示经济观察期；可获得日期取决于所需数据公布时间，季度末值可能随后才公布。历史数据含修订，未认证真实历史数据版本。']}


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    for directory in ('data/raw', 'data/interim', 'output/diagnostics'):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    config = load_config()
    if config['gdp_alignment_mode'] != 'observation_period' or config['standardization_mode'] != 'explicit_unbiased':
        raise ValueError('User-confirmed production mapping and variance must remain fixed')
    if args.refresh:
        status, release_status = refresh_sources()
    else:
        prior = json.loads(DESTINATION.read_text()) if DESTINATION.exists() else {}
        status = {r['dataset']: {k: r.get(k) for k in ('state', 'last_success_at', 'error')} for r in prior.get('sources', [])}
        status = {n: status.get(n, {'state': 'snapshot', 'last_success_at': None, 'error': None}) for n in DATASETS}
        release_status = prior.get('release_lookup_status', [])
    data = load_data();frame = build(data, config['gdp_alignment_mode'], config['standardization_mode'], config)
    snapshot = make_snapshot(data, frame, config, status, release_status)
    frame.to_csv(ROOT / 'output/diagnostics/indicator_diagnostics.csv')
    frame.loc[config['composite_start']:].to_csv(ROOT / 'data/processed/historical_replication.csv')
    temporary = DESTINATION.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
    temporary.replace(DESTINATION)
    print(json.dumps({'latest': snapshot['latest']['date'], 'indicator': snapshot['latest']['leading_indicator'],
        'missing_months': snapshot['missing_months'], 'sources': status}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
