"""Real Chrome regressions for the optional module, using local assets only.
Run with a Python environment containing playwright; no market network requests.
"""
import argparse
import copy
import json
import mimetypes
from pathlib import Path
import subprocess
from playwright.sync_api import sync_playwright

REPO=Path(__file__).resolve().parents[1]

def probe(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    root=REPO/'docs';base=json.loads((root/'sp500-deviation/timing.json').read_text())
    # Test real React boundaries, without adding fault switches to production UI.
    entry="""import React from 'react';import {createRoot} from 'react-dom/client';import {TimingBoundary} from './TimingSignals.jsx';
    function Broken(){throw Error('intentional render regression');}
    const moduleFailure=location.pathname.includes('module-boundary');
    createRoot(document.getElementById('root')).render(<><div id="price-history">原走势图</div><TimingBoundary>{moduleFailure?<Broken/>:<><TimingBoundary name="标普500指数"><article className="timing-card"><strong role="status">正常</strong></article></TimingBoundary><TimingBoundary name="纳斯达克100指数"><Broken/></TimingBoundary></>}</TimingBoundary></>);"""
    # esbuild is already locked in the site's own frontend dependencies.
    builder="import {build} from './web/sp500/node_modules/esbuild/lib/main.js';const r=await build({stdin:{contents:"+json.dumps(entry)+",loader:'jsx',resolveDir:"+json.dumps(str(REPO/'web/sp500'))+"},bundle:true,write:false,format:'iife',define:{'process.env.NODE_ENV':'\"production\"'}});process.stdout.write(r.outputFiles[0].text);"
    boundary_script=subprocess.check_output(['node','--input-type=module','-e',builder],cwd=REPO)
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for case in ['normal','bad_one_index','wrong_identity','missing_close','missing_ma5','missing_timestamp','missing_kind','wrong_version','bad_calendar','broken_json','http_failure','card_boundary','module_boundary']:
            data=copy.deepcopy(base)
            if case=='bad_one_index':data['indices']['ndx']['latest']['close']='bad-price'
            if case=='wrong_identity':data['indices']['ndx']['symbol']='SPX'
            if case=='missing_close':del data['indices']['ndx']['latest']['close']
            if case=='missing_ma5':del data['indices']['ndx']['latest']['ma5']
            if case=='missing_timestamp':del data['indices']['ndx']['successful_at']
            if case=='missing_kind':del data['indices']['ndx']['latest']['kind']
            if case=='wrong_version':data['schema_version']=2
            if case=='bad_calendar':data['sessions']={}
            page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(r):
                rel=r.request.url.split('review.local/',1)[-1]
                if rel=='boundary.js':r.fulfill(body=boundary_script,content_type='text/javascript');return
                if rel in ['card-boundary','module-boundary']:
                    r.fulfill(body='<div id="root"></div><script src="/boundary.js"></script>',content_type='text/html');return
                if rel.endswith('timing.json'):
                    if case=='broken_json':r.fulfill(body='{broken',content_type='application/json')
                    elif case=='http_failure':r.fulfill(status=503,body='unavailable')
                    else:r.fulfill(json=data)
                    return
                path=root/rel
                if path.is_dir():path=path/'index.html'
                if path.is_file():r.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                else:r.abort()
            page.route('**/*',route)
            page.goto('http://review.local/'+(case.replace('_','-') if case in ['card_boundary','module_boundary'] else 'sp500-deviation/'))
            if case in ['card_boundary','module_boundary']:
                page.get_by_text('暂不可判定',exact=True).wait_for()
            else:
                page.wait_for_function("document.querySelectorAll('.timing-card').length===2 && ![...document.querySelectorAll('.timing-card [role=status]')].some(n=>n.textContent==='正在读取')")
            cards=page.locator('.timing-card').count();statuses=page.locator('[role=status]').all_text_contents()
            assert page.locator('#price-history').count()==1,(case,'old chart disappeared')
            assert not errors,(case,errors)
            if case not in ['normal','card_boundary','module_boundary']:
                card_status=page.locator('.timing-card [role=status]').all_text_contents()
                assert card_status[1]=='暂不可判定',(case,card_status)
                if case in ['bad_one_index','wrong_identity','missing_close','missing_ma5','missing_timestamp','missing_kind']:
                    assert card_status[0]!='暂不可判定',(case,'healthy index lost')
                    assert '数据无效' in page.locator('.timing-card').nth(1).inner_text()
                    assert page.locator('.timing-evidence[data-index=ndx] dd').all_text_contents()==['—']*7
            if case=='card_boundary':assert cards==2 and statuses==['正常','暂不可判定']
            if case=='module_boundary':assert '暂不可判定' in statuses
            result=dict(case=case,errors=errors,cards=cards,old_chart_present=True,statuses=statuses)
            if case=='normal':
                summaries=page.locator('.timing-complete summary');assert page.locator('.timing-complete[open]').count()==0
                summaries.first.focus();page.keyboard.press('Enter');assert page.locator('.timing-complete[open]').count()==1
                page.set_viewport_size({'width':390,'height':844})
                page.wait_for_function('document.documentElement.scrollWidth<=innerWidth')
                result['mobile_overflow']=page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not result['mobile_overflow']
            if case in ['bad_one_index','wrong_identity']:
                page.locator('.timing-module').scroll_into_view_if_needed();page.screenshot(path=str(output/f'{case}.png'))
            results.append(result);page.close()
        browser.close()
    (output/'browser-probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('Browser regressions passed:',len(results),'cases')
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(REPO/'output/playwright/timing-repair-20261115'))
    probe(parser.parse_args().out)
