"""Local Chrome integration checks; verified frozen prices, no remote requests."""
import argparse
import copy
import datetime as dt
import json
import mimetypes
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO=Path(__file__).resolve().parents[1]

def expected(history,years='3',kind='AB',all_dates=False):
    end=dt.date.fromisoformat(history['price_end'])
    cutoff=history['price_start'] if years=='all' else end.replace(year=end.year-int(years)).isoformat()
    rows=[r for r in history['rows'] if r['date']>=cutoff]
    signals=[r for r in rows if r['eligible'] and r['kind'] and (kind=='AB' or r['kind']==kind)]
    seen=set();markers=[]
    for r in signals:
        identity=r['first_date'] or r['date']
        if all_dates or identity not in seen:markers.append(r)
        seen.add(identity)
    return rows,signals,markers

def probe(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    root=REPO/'docs';base=json.loads((root/'sp500-deviation/timing.json').read_text());results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for case in ['desktop','mobile','bad_history_type','bad_history_identity','history_missing_day','no_history','stale','warmup']:
            data=copy.deepcopy(base)
            if case=='bad_history_type':data['indices']['ndx']['history']['rows'][-1]['close']='invalid'
            if case=='bad_history_identity':data['indices']['ndx']['history']['symbol']='SPX'
            if case=='history_missing_day':data['indices']['ndx']['history']['rows'].pop(500)
            if case=='no_history':del data['indices']['ndx']['history']
            if case=='stale':data['calendar_until']='2026-01-01'
            # Explicit UI fixture: unknown historical observations, never presented as actual market signals.
            if case=='warmup':
                h=data['indices']['ndx']['history'];h['eligible_start']=None
                for row in h['rows']:row.update(eligible=False,ma200=None,kind=None,consecutive=0)
            page=browser.new_page(viewport={'width':390 if case=='mobile' else 1440,'height':900},has_touch=case=='mobile');errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(r):
                rel=r.request.url.split('review.local/',1)[-1]
                if rel.endswith('timing.json'):r.fulfill(json=data);return
                path=root/rel
                if path.is_dir():path=path/'index.html'
                if path.is_file():r.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                else:r.abort()
            page.route('**/*',route);page.goto('http://review.local/sp500-deviation/')
            page.locator('.timing-main-chart svg').wait_for()
            chart=page.locator('.timing-main-chart svg');module=page.locator('.timing-module')
            def group(label,button):page.get_by_role('group',name=label).get_by_role('button',name=button,exact=True).click()
            def verify(key,years='3',kind='AB',all_dates=False):
                rows,signals,markers=expected(base['indices'][key]['history'],years,kind,all_dates)
                actual=page.locator('.timing-marker').evaluate_all('(nodes)=>nodes.map(n=>({date:n.dataset.date,kind:n.dataset.kind,close:Number(n.dataset.close)}))')
                assert actual==[dict(date=r['date'],kind=r['kind'],close=r['close']) for r in markers],(key,years,kind,len(actual),len(markers))
                assert page.locator('.timing-date-list button').count()==len(signals)
                assert chart.get_attribute('data-fields')=='close,ma200'
                if markers:
                    row=markers[0];node=page.locator('.timing-marker').first
                    geometry=node.evaluate('(n)=>{const s=n.closest("svg"),c=n.querySelector("circle");return {cx:Number(c.getAttribute("cx")),cy:Number(c.getAttribute("cy")),domain:s.dataset.domain,width:s.viewBox.baseVal.width}}')
                    cx,cy=geometry['cx'],geometry['cy'];lo,hi=map(float,geometry['domain'].split(','));width=geometry['width']
                    day=lambda d:dt.date.fromisoformat(d).toordinal()
                    x=64+(day(row['date'])-day(rows[0]['date']))/(day(rows[-1]['date'])-day(rows[0]['date']))*(width-82)
                    y=358-(row['close']-lo)/(hi-lo)*340
                    assert abs(cx-x)<.01 and abs(cy-y)<.01,('signal-day close position',cx,cy,x,y)
                return signals,markers
            if case in ['desktop','mobile']:
                module.screenshot(path=str(output/f'{case}-default.png'))
                original=page.locator('#price-history svg').evaluate_all('(nodes)=>nodes.map(n=>({fields:n.dataset.fields,domain:n.dataset.domain,paths:[...n.querySelectorAll("path")].map(p=>p.getAttribute("d"))}))')
                assert original
                signals,markers=verify('sp500');page.get_by_label('显示全部符合条件日期').check();verify('sp500',all_dates=True)
                page.get_by_label('显示全部符合条件日期').uncheck();verify('sp500')
                for label,years in [('近1年','1'),('近5年','5'),('全部','all'),('近3年','3')]:
                    group('历史图范围',label);verify('sp500',years)
                group('历史图范围','全部');signals,markers=verify('sp500','all')
                bdate=next(r['date'] for r in signals if r['kind']=='B')
                page.locator('.timing-date-list summary').click();datebutton=page.locator('.timing-date-list button').filter(has_text=bdate).first
                datebutton.tap() if case=='mobile' else datebutton.click()
                assert bdate in page.locator('.timing-signal-detail').inner_text()
                assert page.locator('.timing-marker[aria-pressed=true]').get_attribute('data-date')==bdate
                # A non-first qualifying day stays selectable in first-only mode.
                later=next(r for r in signals if r['consecutive']>1)
                page.locator('.timing-date-list button').filter(has_text=later['date']).click()
                detail=page.locator('.timing-signal-detail').inner_text()
                assert later['date'] in detail and later['first_date'] in detail and str(later['consecutive']) in detail
                group('历史图类型','仅A类');verify('sp500','all','A')
                group('历史图类型','仅B类');verify('sp500','all','B')
                group('历史图范围','近1年');verify('sp500','1','B')
                assert page.get_by_text('所选区间没有符合条件的日期。',exact=True).count()==1
                assert chart.locator('path').count()==2
                group('历史图类型','全部类型');group('历史图范围','近3年');group('历史图指数','纳斯达克100指数');verify('ndx')
                assert '纳斯达克100指数' in page.locator('.timing-signal-detail').inner_text()
                assert chart.get_attribute('aria-label').startswith('纳斯达克100指数')
                group('历史图指数','标普500指数');verify('sp500')
                marker=page.locator('.timing-marker').first
                marker.tap() if case=='mobile' else marker.click()
                assert marker.get_attribute('data-date') in page.locator('.timing-signal-detail').inner_text()
                marker.hover();tooltip=page.locator('.timing-main-chart .sp-plot-tooltip');assert tooltip.count()==1
                assert marker.get_attribute('data-date') in tooltip.inner_text()
                assert original==page.locator('#price-history svg').evaluate_all('(nodes)=>nodes.map(n=>({fields:n.dataset.fields,domain:n.dataset.domain,paths:[...n.querySelectorAll("path")].map(p=>p.getAttribute("d"))}))')
                page.locator('.timing-date-list summary').click()
                if case=='mobile':
                    a=page.locator('.timing-main-chart').bounding_box();b=page.locator('.timing-signal-detail').bounding_box()
                    assert b['y']>=a['y']+a['height']-1
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                module.screenshot(path=str(output/f'{case}.png'))
            elif case=='stale':
                assert '历史结果' in page.locator('.timing-current').first.inner_text();assert chart.count()==1
            else:
                group('历史图指数','纳斯达克100指数')
                if case=='warmup':assert page.get_by_text('暖机不足，所选区间暂不可判定。',exact=True).count()==1
                else:
                    assert page.locator('.timing-history-empty').count()==1
                    assert '所选区间没有符合条件的日期' not in page.locator('.timing-history-empty').inner_text()
                assert page.locator('.timing-current').first.get_by_role('status').inner_text()!='暂不可判定'
                group('历史图指数','标普500指数');verify('sp500')
            assert not errors,(case,errors)
            assert page.locator('#price-history svg').count()>0
            results.append(dict(case=case,passed=True,errors=errors,old_chart_present=True));page.close()
        browser.close()
    (output/'browser-history.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('Historical chart browser regressions passed:',len(results),'cases')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(REPO/'output/playwright/timing-history-20261115'))
    probe(parser.parse_args().out)
