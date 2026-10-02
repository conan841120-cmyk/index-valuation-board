from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests,json
ROOT=Path(__file__).resolve().parents[2]
URLS={
 'nbs_home':'https://data.stats.gov.cn/',
 'nbs_tree_post':'https://data.stats.gov.cn/easyquery.htm',
 'nbs_tree_http':'http://data.stats.gov.cn/easyquery.htm?m=getTree&dbcode=hgyd&wdcode=zb&id=zb',
 'csd_money':'https://www.censtatd.gov.hk/api/get.php?id=340-45011&lang=EN&period=201001,202609',
 'hkma_docs':'https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/money/',
 'hkma_api':'https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/money/supply-components-all?segment=new&pagesize=1000',
 'pboc_index':'https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html',
}
def run(item):
 name,url=item
 try:
  if name=='nbs_tree_post': r=requests.post(url,data=dict(m='getTree',dbcode='hgyd',wdcode='zb',id='zb'),timeout=25)
  else:r=requests.get(url,timeout=25,headers={'User-Agent':'Mozilla/5.0'})
  path=ROOT/'data/raw'/f'{name}.raw';path.write_bytes(r.content)
  print(name,r.status_code,len(r.content),r.text[:180].replace('\n',' '),flush=True)
  return dict(name=name,url=url,status=r.status_code,bytes=len(r.content))
 except requests.RequestException as e:
  print(name,str(e),flush=True);return dict(name=name,url=url,error=str(e))
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=5) as ex: out=list(ex.map(run,URLS.items()))
 (ROOT/'data/raw/probe_log.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
