"""Read directly published all-currency M2 YoY from HKMA monthly annexes."""
import json,re,time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import pandas as pd
import requests
import pdfplumber
from bs4 import BeautifulSoup
from .common import fetch,profile,ROOT,RAW
BASE='https://www.hkma.gov.hk'
INDEX=BASE+'/eng/news-and-media/press-releases/'

def release_directory(year, month='', refresh=False):
 """Read the public archive; renew an invalid session once, never treat it as empty."""
 name=f'hkma_releases_{year}' + (f'_{month:02d}' if month != '' else '') + '.json'
 cached=RAW/name
 if not refresh and cached.exists() and cached.with_suffix(cached.suffix+'.meta.json').exists():
  response=json.loads(cached.read_text())
  if isinstance(response.get('data'),list):return response['data']
 for attempt in range(2):
  session=requests.Session()
  nonce={'_':str(time.time_ns())} if attempt else {}
  p=fetch(INDEX,'hkma_archive_landing.html',True,params=nonce,session=session)
  token=BeautifulSoup(p.read_bytes(),'html.parser').find('meta',attrs={'name':'csrf_token'})
  if token is None:raise ValueError('金管局发布目录校验标识未找到')
  headers={'X-CSRF-TOKEN':token['content'],'X-Requested-With':'XMLHttpRequest','Referer':INDEX}
  params={'pagesize':10000,'currentcount':0,'year':year,'month':month,**nonce}
  p=fetch(INDEX+'api',name,refresh or bool(attempt),params=params,headers=headers,session=session)
  response=json.loads(p.read_text())
  if isinstance(response.get('data'),list):return response['data']
  if response.get('data') is not False:raise ValueError('金管局发布目录结构变化')
 raise ValueError('金管局目录请求返回data=false，重新建立会话后仍未取得有效目录')

def download(refresh=False):
 previous=ROOT/'data/processed/hk_m2.csv'
 retained=pd.read_csv(previous) if refresh and previous.exists() else pd.DataFrame()
 cutoff=str(pd.Timestamp.now().to_period('M')-3)
 if not retained.empty:retained=retained[retained.observation_period<cutoff]
 years=range(int(cutoff[:4]) if not retained.empty else 2011,pd.Timestamp.now().year+1)
 releases=[]
 for year in years:
  releases.extend(x for x in release_directory(year,refresh=refresh) if re.match(r'Monetary Statistics for ',x['title'],re.I))
 def one(x):
  observation=pd.to_datetime(re.sub(r'^Monetary Statistics for ','',x['title'],flags=re.I)).strftime('%Y-%m')
  if observation<'2011-08':return None
  if not retained.empty and observation<cutoff:return None
  u=urljoin(BASE,x['url']);p=fetch(u,f'hkma_{observation}_release.html',refresh)
  soup=BeautifulSoup(p.read_bytes(),'html.parser')
  links=[urljoin(BASE,a['href']) for a in soup.find_all('a',href=True) if any(ext in a['href'].lower() for ext in ('.pdf','.xlsx','.xls')) and 'annex' in a.get_text().lower()]
  if not links:raise ValueError(f'{observation}: missing annex')
  ext='xlsx' if '.xlsx' in links[0] else 'xls' if '.xls' in links[0] else 'pdf'
  p=fetch(links[0],f'hkma_{observation}_annex.{ext}',refresh)
  if ext!='pdf':
   table=pd.read_excel(p,sheet_name=0,header=None)
   labels=table.iloc[:,0].astype(str).str.strip()
   begin=next(i for i,l in enumerate(labels) if re.match(r'^M2\s',l))
   row=next(table.iloc[i] for i in range(begin,begin+5) if labels.iloc[i]=='Total')
   cells=list(row);changes=[float(cells[i+1]) for i,c in enumerate(cells[:-1]) if str(c).strip()=='(']
   if len(changes)!=3:raise ValueError(f'{observation}: unexpected Excel growth columns')
   return observation,round(changes[-1],1),x['publish_date'],u,links[0],str(list(row.dropna()))
  with pdfplumber.open(p) as pdf: text='\n'.join(pg.extract_text() or '' for pg in pdf.pages)
  (ROOT/'data/interim'/f'hkma_{observation}_annex.txt').write_text(text)
  lines=text.splitlines();begin=next(i for i,l in enumerate(lines) if re.match(r'^M2\s',l))
  total=next(l for l in lines[begin:begin+5] if l.startswith('Total '))
  changes=re.findall(r'\(\s*([-+]?\s*\d+(?:\.\d+)?)\s*\)',total)
  if len(changes)!=3:raise ValueError(f'{observation}: unexpected growth columns: {total}')
  return observation,float(changes[-1].replace(' ','')),x['publish_date'],u,links[0],total
 with ThreadPoolExecutor(max_workers=4) as pool: results=[r for r in pool.map(one,releases) if r]
 frame=pd.DataFrame(results,columns=['observation_period','value','release_date','source_url','annex_url','source_row']).sort_values('observation_period')
 frame['unit']='percent';frame['official_field']='Table 1A / Money Supply / M2 / Total / earlier same month % change'
 frame['vintage_status']='contemporaneous_monthly_release_annex'
 if not retained.empty:frame=pd.concat([retained,frame],ignore_index=True).sort_values('observation_period')
 profile(frame,'hk_m2','percent');return frame
if __name__=='__main__':download()
