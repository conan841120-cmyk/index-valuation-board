"""构建独立美股页面、按日 JSON 和公开 Markdown；不读私有采集仓库。"""
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

WEB = Path(__file__).resolve().parent
DATE = re.compile(r'\d{4}-\d{2}-\d{2}\Z')
RUN_ID = re.compile(r'(digest|alerts)-\d{8}T\d{6}-[0-9a-f]{8}\Z')


def md_text(value):
    text = str(value or '').replace('\\', '\\\\')
    for symbol in '[]*_`<>':
        text = text.replace(symbol, '\\' + symbol)
    return text.replace('\n', ' ')


def markdown(run):
    lines = ['# 美股信息快照', '', '数据状态：' + md_text(run.get('data_status')),
             '采集开始（UTC）：' + md_text(run.get('started_at')),
             '采集结束（UTC）：' + md_text(run.get('finished_at')),
             '这是历史快照，来源状态按采集时点判断，不代表实时行情。', '', '## 行情']
    for symbol, row in run.get('quotes', {}).items():
        usable = row.get('data_status') == 'ok'
        lines.append('- %s：%s；数据时间 %s；来源 %s；状态 %s' % (
            md_text(symbol), md_text(row.get('price')) if usable else '数据不可作当前行情',
            md_text(row.get('as_of') or '未知'), md_text(row.get('source') or '未知'),
            md_text(row.get('data_status') or '待核验')))
    lines += ['', '## 新闻']
    for row in run.get('news', []):
        title = md_text(row.get('title_zh') or row.get('title'))
        link = row.get('link', '')
        try:
            parsed = urlsplit(link)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                link = ''
        except (TypeError, ValueError):
            link = ''
        lines += ['- ' + ('[%s](%s)' % (title, quote(link, safe=':/?&=%#-._~')) if link else title),
                  '  - 发布时间：' + md_text(row.get('published') or '未知'),
                  '  - 标题/信源摘要：' + md_text(row.get('zh') or '未生成')]
        lines += ['  - 正文要点：' + md_text(point) for point in row.get('points', [])]
        if not row.get('points'):
            lines.append('  - 未取得核验正文要点。')
    lines += ['', '## 检测记录']
    lines += ['- ' + md_text(row.get('text')) for row in run.get('price_alerts', [])]
    lines += ['- ' + md_text(row) for row in run.get('heads', [])]
    lines += ['', '## 来源状态']
    for row in run.get('sources', []):
        lines.append('- %s：%s；可用 %s/%s；检查 %s；最后数据 %s' % (
            md_text(row.get('name')), md_text(row.get('status')), row.get('usable', 0),
            row.get('received', 0), md_text(row.get('checked_at') or '未知'),
            md_text(row.get('latest_published_at') or '未知')))
    return '\n'.join(lines) + '\n'


def build(source, out):
    source, out = Path(source), Path(out)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8')) if (source / 'manifest.json').exists() else {
        'schema_version': 1, 'date_timezone': 'Asia/Shanghai', 'dates': []}
    if manifest.get('schema_version') != 1 or manifest.get('date_timezone') != 'Asia/Shanghai':
        raise ValueError('Unsupported manifest')
    dates = manifest['dates']
    if not isinstance(dates, list) or any(not isinstance(date, str) or not DATE.fullmatch(date) for date in dates):
        raise ValueError('Invalid dates')
    if dates != sorted(set(dates), reverse=True):
        raise ValueError('Dates must be unique and descending')
    for date in dates:
        dt.date.fromisoformat(date)
    days = {}
    for date in dates:
        day = json.loads((source / (date + '.json')).read_text(encoding='utf-8'))
        if day.get('schema_version') != 1 or day.get('date') != date:
            raise ValueError('Invalid day payload')
        for mode in ('digest', 'alerts'):
            if not isinstance(day.get(mode), list):
                raise ValueError('Invalid run list')
            for run in day[mode]:
                if not RUN_ID.fullmatch(run['run_id']) or run['mode'] != mode or run['date'] != date:
                    raise ValueError('Invalid run identity')
        days[date] = day
    # 先验证全部日期；损坏数据不会被当作空内容发布。
    bootstrap = {'manifest': manifest, 'day': days.get(dates[0]) if dates else None}
    embedded = json.dumps(bootstrap, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    template = (WEB / 'us_market.html').read_text(encoding='utf-8')
    html = template.replace('<!--DATA-->', embedded).replace('<!--STYLE-->',
            (WEB / 'us_market.css').read_text(encoding='utf-8')).replace('<!--APP-->',
            (WEB / 'us_market.js').read_text(encoding='utf-8'))
    (out / 'data').mkdir(parents=True, exist_ok=True)
    (out / 'reports').mkdir(exist_ok=True)
    for date, day in days.items():
        (out / 'data' / (date + '.json')).write_text(json.dumps(day, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        for run in day['digest'] + day['alerts']:
            (out / 'reports' / (run['run_id'] + '.md')).write_text(markdown(run), encoding='utf-8')
    (out / 'index.html').write_text(html, encoding='utf-8')
    print('美股页面：%d 个存档日期 → %s' % (len(dates), out))
    return out / 'index.html'
