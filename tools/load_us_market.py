"""只读取公开数据分支的 manifest 与日期 JSON，不执行该分支代码。"""
import datetime as dt
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATE = re.compile(r'\d{4}-\d{2}-\d{2}\Z')


def load(root=ROOT):
    probe = subprocess.run(['git', 'ls-remote', '--exit-code', '--heads', 'origin', 'us-market-data'],
                           cwd=root, capture_output=True, text=True)
    if probe.returncode == 2:
        print('美股公开数据分支尚未建立，页面显示等待首次交接。')
        return
    probe.check_returncode()
    subprocess.run(['git', 'fetch', '--depth=1', 'origin', 'us-market-data'], cwd=root, check=True)

    def read(name):
        value = subprocess.check_output(['git', 'show', 'FETCH_HEAD:data/us_market/' + name], cwd=root)
        return json.loads(value)

    manifest = read('manifest.json')
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('dates'), list):
        raise ValueError('Invalid public manifest')
    files = {'manifest.json': manifest}
    for date in manifest['dates']:
        if not isinstance(date, str) or not DATE.fullmatch(date):
            raise ValueError('Invalid public date')
        dt.date.fromisoformat(date)
        files[date + '.json'] = read(date + '.json')
    encoded = {name: json.dumps(value, ensure_ascii=False, allow_nan=False) for name, value in files.items()}
    sp500_path = 'FETCH_HEAD:data/us_market/sp500.json'
    if subprocess.run(['git', 'cat-file', '-e', sp500_path], cwd=root, capture_output=True).returncode == 0:
        sp500 = json.loads(subprocess.check_output(['git', 'show', sp500_path], cwd=root))
        if sp500.get('schema_version') != 1 or sp500.get('symbol') != '^GSPC':
            raise ValueError('Invalid S&P 500 payload')
        encoded['sp500.json'] = json.dumps(sp500, ensure_ascii=False, allow_nan=False)
    destination = root / 'data/us_market'
    destination.mkdir(parents=True, exist_ok=True)
    for name, value in encoded.items():
        (destination / name).write_text(value, encoding='utf-8')


if __name__ == '__main__':
    load()
