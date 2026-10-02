"""Calendar gate, catch-up and next-round alarms. --plan needs only stdlib."""
import argparse
import calendar
import csv
from datetime import datetime
import json
import math
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
BOARD = ROOT.parents[1]
STATE_PATH = BOARD / 'data/hsi_macro_monitor.json'


def month_add(month, offset):
    year, number = map(int, month.split('-'))
    ordinal = year * 12 + number - 1 + offset
    return f'{ordinal // 12:04d}-{ordinal % 12 + 1:02d}'


def read_rows(name):
    with (ROOT / f'data/processed/{name}.csv').open() as stream:
        return list(csv.DictReader(stream))


def values(rows):
    out = {}
    for row in rows:
        try:
            value = float(row['value'])
        except (ValueError, TypeError):
            continue
        if math.isfinite(value):
            out[row['observation_period']] = value
    return out


def next_release_month(month, rule):
    while True:
        month = month_add(month, 1)
        number = int(month[-2:])
        if number not in rule.get('skip_release_months', []) and number in rule.get('release_months', range(1, 13)):
            return month


def rounds(name, rule, start, current):
    result = []
    month = start
    while month <= current:
        year, number = map(int, month.split('-'))
        if number not in rule.get('skip_release_months', []) and number in rule.get('release_months', range(1, 13)):
            observation = month_add(month, -1)
            if name == 'gdp':
                observation = observation[:4] + f'-Q{(int(observation[-2:]) - 1) // 3 + 1}'
            result.append({'release_month': month, 'observation_period': observation,
                'window_start': f"{month}-{rule['start_day']:02d}",
                'window_end': f"{month}-{min(rule['end_day'], calendar.monthrange(year, number)[1]):02d}",
                'next_window_start': f"{next_release_month(month, rule)}-{rule['start_day']:02d}"})
        month = month_add(month, 1)
    return result


def acquired(name, period, data):
    if period in values(data[name]):
        return True
    # A verified combined announcement closes the release round, while the
    # official independent monthly value remains NaN in the indicator.
    if name == 'retail' and period.endswith('-02'):
        return any(r['observation_period'] == period and r.get('release_date') and
            re.search(r'1[—－–-]2月', r.get('release_title') or '') for r in data[name])
    return False


def round_status(name, round_, today, data):
    return {**round_, 'status': 'acquired' if acquired(name, round_['observation_period'], data)
        else 'scheduled' if today < round_['window_start']
        else 'awaiting' if today <= round_['window_end'] else 'catch_up'}


def evaluate(today, data, previous=None, policy=None):
    previous = previous or {}
    policy = policy or json.loads((ROOT / 'release_policy.json').read_text())
    current = today.strftime('%Y-%m')
    # Bootstrap from the previous quarter, not from decades of missing dates.
    quarter_start = f'{today.year:04d}-{((today.month - 1) // 3) * 3 + 1:02d}'
    start = previous.get('monitoring_start_month', month_add(quarter_start, -3))
    date_text = today.isoformat()
    old_sources = {r['dataset']: r for r in previous.get('sources', [])}
    old_alerts = {r['id']: r for r in previous.get('alerts', [])}
    sources, alerts, due = [], [], []
    for name, rule in policy['sources'].items():
        schedule = rounds(name, rule, start, next_release_month(current, rule))
        started = [r for r in schedule if r['window_start'] <= date_text]
        current_round = started[-1] if started else schedule[0]
        next_round = next(r for r in schedule if r['window_start'] > current_round['window_start'])
        pending = [r for r in schedule if r['window_start'] <= date_text and not acquired(name, r['observation_period'], data)]
        inside = any(r['window_start'] <= date_text <= r['window_end'] for r in schedule)
        catch_up = any(r['window_end'] < date_text for r in pending)
        late = [r for r in pending if r['next_window_start'] <= date_text]
        if inside or catch_up:
            due.append(name)
        for r in late:
            identity = name + ':' + r['observation_period']
            alerts.append({'id': identity, 'dataset': name, 'observation_period': r['observation_period'],
                'first_detected_date': old_alerts.get(identity, {}).get('first_detected_date', date_text),
                'message': f"{rule['label']}仍未取得{r['observation_period']}数据，已进入下一轮发布窗口；将继续每日检查。"})
        old = old_sources.get(name, {})
        sources.append({'dataset': name, 'label': rule['label'], 'window': f"{rule['start_day']}—{rule['end_day']}日" if name != 'hk_m2' else '26日至月底',
            'target_observation': current_round['observation_period'],
            'current_round': round_status(name, current_round, date_text, data),
            'next_round': next_round,
            'backlog_rounds': [round_status(name, r, date_text, data) for r in pending if r['window_start'] < current_round['window_start']],
            'phase': 'alarm' if late else 'catch_up' if catch_up else 'window' if inside else 'idle',
            'missing_periods': [r['observation_period'] for r in pending],
            'last_checked_at': old.get('last_checked_at'), 'last_probe_error': old.get('last_probe_error')})
    return {'schema_version': 1, 'monitoring_start_month': start, 'evaluated_date': date_text,
        'policy': policy, 'sources': sources, 'due_sources': due, 'alerts': alerts,
        'new_alerts': [r for r in alerts if r['id'] not in old_alerts]}


def load_data():
    return {name: read_rows(name) for name in json.loads((ROOT / 'release_policy.json').read_text())['sources']}


def write_state(state):
    temporary = STATE_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(STATE_PATH)


def check(today, previous, force=False, probe=None, refresh=None):
    data = load_data()
    state = evaluate(today, data, previous)
    refreshed = []
    if force:
        from update import run
        (refresh or run)(refresh=True)
        refreshed = list(state['policy']['sources']) + ['hsi']
    else:
        if probe is None:
            from release_probe import inspect_source
            probe = inspect_source
        for row in state['sources']:
            name = row['dataset']
            if name not in state['due_sources']:
                continue
            row['last_checked_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
            try:
                if probe(name, today, data, row['missing_periods']):
                    refreshed.append(name)
                row['last_probe_error'] = None
            except Exception as error:
                row['last_probe_error'] = str(error)[:400]
                print(f'::warning::{name}轻量检查失败：{error}', flush=True)
        if refreshed:
            from update import run
            (refresh or run)(refresh=True, selected=refreshed + ['hsi'])
    final = evaluate(today, load_data(), state)
    # Compare alarm transitions against the saved state, after all refresh attempts.
    old_ids = {r['id'] for r in previous.get('alerts', [])}
    final['new_alerts'] = [r for r in final['alerts'] if r['id'] not in old_ids]
    final['refreshed_sources'] = refreshed
    final['last_run_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    write_state(final)
    return final


def output(name, value):
    print(f'{name}={str(value).lower() if isinstance(value, bool) else value}', flush=True)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(f'{name}={str(value).lower() if isinstance(value, bool) else value}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--force-refresh', action='store_true')
    args = parser.parse_args()
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    previous = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    if args.plan:
        state = evaluate(today, load_data(), previous)
        output('needs_check', bool(state['due_sources']) or args.force_refresh)
        print(json.dumps(state, ensure_ascii=False), flush=True)
        return
    state = check(today, previous, args.force_refresh)
    output('refreshed', bool(state['refreshed_sources']))
    output('new_alarm', bool(state['new_alerts']))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('## 恒生宏观发布监测\n\n')
            stream.write('|来源|状态|仍缺观察期|最近轻量检查|\n|---|---|---|---|\n')
            for r in state['sources']:
                stream.write(f"|{r['label']}|{r['phase']}|{', '.join(r['missing_periods']) or '无'}|{r['last_checked_at'] or '未检查'}|\n")
            for alert in state['alerts']:
                stream.write('\n**报警：' + alert['message'] + '**\n')


if __name__ == '__main__':
    main()
