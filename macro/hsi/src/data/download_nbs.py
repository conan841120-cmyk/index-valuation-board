"""NBS public catalogue and streaming data endpoint used by 国家数据 UI."""
import json
import pandas as pd
from .common import fetch,profile,RAW
BASE='https://data.stats.gov.cn/dg/website'
CATALOGUES={
 'retail':('d0cb882c7f27443ab6b3ef9421901961','fc982599aa684be7969d7b90b1bd0e84','198301MM','202608MM','社会消费品零售总额同比增长'),
 'ppi':('60e8b361f11c4a878c652a6487a25561','fc982599aa684be7969d7b90b1bd0e84','198301MM','202608MM','工业生产者出厂价格指数'),
 'gdp':('28d936104e304aa191e338eb82b6dc09','a94b8b7365a94874968cabbe392cf679','198601SS','202602SS','国内生产总值当季值')}

def download(name,refresh=False):
 cid,root,start,end,field=CATALOGUES[name]
 # Range end is the last completed economic month/quarter at run time.
 now=pd.Timestamp.now();end=((now.to_period('M')-1).strftime('%Y%m')+'MM') if name!='gdp' else ((now.to_period('Q')-1).strftime('%Y')+f'{(now.to_period("Q")-1).quarter:02d}SS')
 p=fetch(BASE+'/publicrelease/web/external/new/queryIndicatorsByCid',f'nbs_{name}_fields.json',refresh,params={'cid':cid})
 fields=json.loads(p.read_text())['data']['list']
 matches=[f for f in fields if f['i_showname'].strip().startswith(field)]
 if name=='ppi':matches=[f for f in matches if f.get('ek_dp_name','').endswith('_上年同期=100') or f.get('dp')=='1']
 if len(matches)!=1:raise ValueError(f'{name}: ambiguous fields {[(f["i_showname"],f.get("dp")) for f in fields]}')
 target=matches[0];print('FIELD',name,target['i_showname'],target['_id'],target['du_name'],flush=True)
 body=dict(cid=cid,rootId=root,indicatorIds=[target['_id']],daCatalogId='',das=[{'text':'全国','value':'000000000000'}],showType=1,dts=[start+'-'+end])
 p=fetch(BASE+'/publicrelease/web/external/stream/esData',f'nbs_{name}_history.json',refresh,json_body=body)
 data=json.loads(p.read_text())
 if not data.get('success') or not data['data']:raise ValueError('NBS returned no data')
 rows=[]
 for r in data['data']:
  v=next((v for v in r['values'] if v['_id']==target['_id']),None)
  if v is None:continue
  code=r['code'];date=f'{code[:4]}-Q{int(code[4:6])}' if name=='gdp' else f'{code[:4]}-{code[4:6]}'
  value=pd.to_numeric(v.get('value'),errors='coerce')
  if name=='ppi':value-=100 # Official YoY index, previous-year same month =100.
  rows.append((date,value))
 frame=pd.DataFrame(rows,columns=['observation_period','value']).sort_values('observation_period')
 frame['release_date']=pd.NaT;frame['unit']='CNY_100million' if name=='gdp' else 'percent'
 frame['official_field']=target['i_showname'];frame['source_url']=BASE+'/publicrelease/web/external/stream/esData'
 frame['vintage_status']='latest_vintage_revised'
 frame['missing_reason']=frame.value.isna().map({True:'official field blank; no fill',False:''})
 profile(frame,name,frame.unit.iloc[0]);return frame
if __name__=='__main__':
 for name in CATALOGUES:download(name)
