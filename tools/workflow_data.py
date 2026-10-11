"""Transfer only declared data files between isolated Actions jobs."""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORT = 'outputs/口径与误差报告.md'
DAILY = {'data/series/raw_inputs.json', 'data/watch/rule_check.json', REPORT}
MACRO = {'data/hsi_macro.json', 'data/hsi_macro_monitor.json', REPORT,
         'RELEASE_CALENDAR_REPORT.md'} | {
    'macro/hsi/data/processed/' + name + '.csv' for name in (
        'gdp', 'historical_replication', 'hk_m2', 'hsi', 'nbs_release_dates',
        'pboc_release_dates', 'ppi', 'retail', 'social_financing')
} | {'data/release_calendar/' + name + '.csv' for name in (
    'release_date_summary', 'release_day_counts', 'verified_release_dates')}
INDICATOR = re.compile(r'data/official_snapshots/indicator_(000300|000510|000922|H30269)(\.csv|_(\d{4}-\d{2}-\d{2})\.xls)\Z')
US_DATE = re.compile(r'data/us_market/(\d{4}-\d{2}-\d{2})\.json\Z')


def require_files(kind, names):
    required = DAILY | {'data/official_snapshots/indicator_' + code + '.csv'
                        for code in ('000300', '000510', '000922', 'H30269')} if kind == 'daily' else MACRO
    if kind == 'us-market':
        required = {'data/us_market/manifest.json'} if names else set()
    if not required.issubset(names):
        raise ValueError('Missing required snapshot files')


def allowed(kind, name):
    if not isinstance(name, str):
        return False
    match = None
    if kind == 'daily':
        if name in DAILY:
            return True
        match = INDICATOR.fullmatch(name)
        if match and not match[3]:
            return True
        day = match[3] if match else None
    elif kind == 'macro':
        return name in MACRO
    elif kind == 'us-market':
        if name in ('data/us_market/manifest.json', 'data/us_market/sp500.json'):
            return True
        match = US_DATE.fullmatch(name)
        day = match[1] if match else None
    else:
        return False
    if day:
        try:
            dt.date.fromisoformat(day)
            return True
        except ValueError:
            pass
    return False


def data_path(root, name):
    path = root
    for part in Path(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Data path must not contain links: ' + name)
    if path.exists() and not path.is_file():
        raise ValueError('Data path must be a regular file: ' + name)
    return path


def pack(root, kind, destination):
    names = DAILY if kind == 'daily' else MACRO if kind == 'macro' else set()
    names = set(names)
    directory = 'data/official_snapshots' if kind == 'daily' else 'data/us_market'
    if kind != 'macro':
        names.update(p.relative_to(root).as_posix() for p in (root / directory).glob('*'))
    files = []
    for name in sorted(names):
        if allowed(kind, name):
            path = data_path(root, name)
            if path.exists():
                files.append({'path': name, 'base64': base64.b64encode(path.read_bytes()).decode('ascii')})
    require_files(kind, {row['path'] for row in files})
    destination.write_text(json.dumps({'version': 1, 'kind': kind, 'files': files}), encoding='utf-8')


def unpack(root, kind, source, stage=False):
    bundle = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(bundle, dict) or set(bundle) != {'version', 'kind', 'files'}:
        raise ValueError('Invalid data bundle')
    if bundle['version'] != 1 or bundle['kind'] != kind or not isinstance(bundle['files'], list):
        raise ValueError('Invalid data bundle identity')
    decoded = {}
    for row in bundle['files']:
        if not isinstance(row, dict) or set(row) != {'path', 'base64'}:
            raise ValueError('Invalid data record')
        name = row['path']
        if not allowed(kind, name) or name in decoded:
            raise ValueError('Unexpected or duplicate data path')
        path = data_path(root, name)
        decoded[name] = (path, base64.b64decode(row['base64'], validate=True))
    require_files(kind, set(decoded))
    # Validate every record before modifying any checkout file.
    for path, content in decoded.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if stage and decoded:
        subprocess.run(['git', 'add', '--', *decoded], cwd=root, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('pack', 'unpack'))
    parser.add_argument('kind', choices=('daily', 'macro', 'us-market'))
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--stage', action='store_true')
    args = parser.parse_args()
    if args.operation == 'pack':
        if args.stage:
            parser.error('--stage is only valid for unpack')
        pack(ROOT, args.kind, args.bundle)
    else:
        unpack(ROOT, args.kind, args.bundle, args.stage)
