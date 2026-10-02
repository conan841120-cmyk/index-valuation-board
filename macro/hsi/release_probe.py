"""Bounded current-period checks; no historical PDFs or full-series calculation."""
import hashlib
import json
import math
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from release_watch import month_add, values
from src.data.common import fetch, RAW
from src.data.download_nbs import BASE as NBS_BASE, CATALOGUES
from src.data.download_pboc import BASE as PBOC_BASE, INDEX as PBOC_INDEX
from src.data.download_hkma import BASE as HKMA_BASE, INDEX as HKMA_INDEX

NBS_IDS = {'retail': 'aaac57d54d2e465d91bc9f3ea1a8618e',
    'ppi': '150633e52b9a470a9a9fd1b296dd6c5b', 'gdp': 'd22612f09aeb4241bc557ef0ac61b3ba'}


def nbs(name, today, data, missing):
    current = today.strftime('%Y-%m')
    end_month = month_add(current, -1)
    start_month = min([month_add(current, -3)] + [p[:4] + f'-{int(p[-1])*3:02d}' if '-Q' in p else p for p in missing])
    def code(month):
        return month.replace('-', '') + 'MM' if name != 'gdp' else month[:4] + f'{(int(month[-2:])-1)//3+1:02d}SS'
    cid, root = CATALOGUES[name][:2]
    identifier = NBS_IDS[name]
    body = dict(cid=cid, rootId=root, indicatorIds=[identifier], daCatalogId='',
        das=[{'text': '全国', 'value': '000000000000'}], showType=1, dts=[code(start_month) + '-' + code(end_month)])
    p = fetch(NBS_BASE + '/publicrelease/web/external/stream/esData', f'probe_nbs_{name}.json', True, json_body=body)
    response = json.loads(p.read_text())
    if not response.get('success') or not isinstance(response.get('data'), list) or not response['data']:
        raise ValueError('国家数据近期查询为空或结构变化')
    actual, matched = {}, 0
    for row in response['data']:
        cell = next((v for v in row.get('values', []) if v.get('_id') == identifier), None)
        if cell is None:
            continue
        matched += 1
        observation = row['code'][:4] + ('-Q' + str(int(row['code'][4:6])) if name == 'gdp' else '-' + row['code'][4:6])
        try:
            value = float(cell['value']) - (100 if name == 'ppi' else 0)
        except (ValueError, TypeError):
            continue
        if math.isfinite(value):
            actual[observation] = value
    if not matched:
        raise ValueError('国家数据未返回已确认的官方字段')
    cached = values(data[name])
    if any(period not in cached or not math.isclose(cached[period], value, rel_tol=0, abs_tol=1e-10) for period, value in actual.items()):
        return True
    if name == 'retail' and any(p.endswith('-02') for p in missing):
        # The independent field is intentionally blank: inspect the actual
        # combined bulletin, never fill January/February in the indicator.
        year = next(p[:4] for p in missing if p.endswith('-02'))
        for index in range(3):
            url = 'https://www.stats.gov.cn/sj/zxfb/' + (f'index_{index}.html' if index else '')
            page = fetch(url, f'probe_nbs_bulletin_{index}.html', True)
            soup = BeautifulSoup(page.read_text(), 'html.parser')
            if any(year + '年' in a.get('title', '') and '社会消费品零售' in a.get('title', '') and
                re.search(r'1[—－–-]2月', a.get('title', '')) for a in soup.select('a.fl.pc_1600')):
                return True
    return False


def pboc(today, data, missing):
    index = fetch(PBOC_INDEX, 'probe_pboc_index.html', True)
    soup = BeautifulSoup(index.read_bytes(), 'html.parser')
    years = [urljoin(PBOC_BASE, a['href']) for a in soup.find_all('a', href=True) if a.get_text(strip=True) == '社会融资规模']
    if not years:
        raise ValueError('人民银行社融年度目录未找到')
    page = fetch(years[0], 'probe_pboc_current_year.html', True)
    soup = BeautifulSoup(page.read_bytes(), 'html.parser')
    links = [a for a in soup.find_all('a', href=True) if a.get_text(strip=True) == 'htm' or
        (a.get_text(strip=True).startswith('社会融资规模') and a['href'].endswith('.htm'))]
    if not links:
        raise ValueError('人民银行当前年度最新附表未找到')
    url = urljoin(PBOC_BASE, links[0]['href']).replace('http:', 'https:')
    flow = fetch(url, 'probe_pboc_current_flow.html', True)
    valid_periods = values(data['social_financing'])
    latest = max((r for r in data['social_financing'] if r['observation_period'] in valid_periods), key=lambda r: r['observation_period'])
    baseline = RAW / f'pboc_{today.year}_flow.html.meta.json'
    old_hash = json.loads(baseline.read_text())['sha256'] if baseline.exists() else None
    return any(period <= latest['observation_period'] for period in missing) or url != latest['source_url'] or hashlib.sha256(flow.read_bytes()).hexdigest() != old_hash


def hkma(today, data, missing):
    current = today.strftime('%Y-%m')
    months = {current} | {month_add(p, 1) for p in missing}
    session = requests.Session()
    page = fetch(HKMA_INDEX, 'probe_hkma_landing.html', True, session=session)
    token = BeautifulSoup(page.read_bytes(), 'html.parser').find('meta', attrs={'name': 'csrf_token'})
    if token is None:
        raise ValueError('金管局发布目录校验标识未找到')
    headers = {'X-CSRF-TOKEN': token['content'], 'X-Requested-With': 'XMLHttpRequest', 'Referer': HKMA_INDEX}
    existing = {r['observation_period']: r for r in data['hk_m2']}
    for month in sorted(months):
        page = fetch(HKMA_INDEX + 'api', f'probe_hkma_{month}.json', True,
            params={'pagesize': 10000, 'currentcount': 0, 'year': int(month[:4]), 'month': int(month[-2:])},
            headers=headers, session=session)
        response = json.loads(page.read_text())
        if not isinstance(response.get('data'), list):
            raise ValueError('金管局发布目录结构变化')
        for r in response['data']:
            match = re.fullmatch(r'Monetary Statistics for ([A-Za-z]+) (\d{4})', r['title'], re.I)
            if not match:
                continue
            from datetime import datetime
            observation = datetime.strptime(match[1] + ' ' + match[2], '%B %Y').strftime('%Y-%m')
            cached = existing.get(observation, {})
            if observation < '2011-08':
                continue
            if cached.get('source_url') != urljoin(HKMA_BASE, r['url']) or cached.get('release_date') != str(r['publish_date'])[:10]:
                return True
    return False


def inspect_source(name, today, data, missing):
    RAW.mkdir(parents=True, exist_ok=True)
    if name in NBS_IDS:
        return nbs(name, today, data, missing)
    if name == 'social_financing':
        return pboc(today, data, missing)
    return hkma(today, data, missing)
