"""Official annual AFRE flow tables and the 2002--2012 official back-history."""
import re
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import pandas as pd
from bs4 import BeautifulSoup
from .common import ROOT,fetch,profile
BASE='https://www.pbc.gov.cn'
INDEX=BASE+'/diaochatongjisi/116219/116319/index.html'
HISTORY=BASE+'/goutongjiaoliu/113456/113469/2863557/2021122418533735135.pdf'
def download(refresh=False):
 import pdfplumber
 path=fetch(INDEX,'pboc_index.html',refresh)
 soup=BeautifulSoup(path.read_bytes(),'html.parser')
 urls=[urljoin(BASE,a['href']) for a in soup.find_all('a',href=True) if a.get_text(strip=True)=='社会融资规模']
 def annual(url):
  year=pd.Timestamp.now().year-urls.index(url)
  current_refresh=refresh and year>=pd.Timestamp.now().year-1
  p=fetch(url,f'pboc_{year}_index.html',current_refresh)
  s=BeautifulSoup(p.read_bytes(),'html.parser')
  links=[a for a in s.find_all('a',href=True) if a.get_text(strip=True)=='htm' or (a.get_text(strip=True).startswith('社会融资规模') and a['href'].endswith('.htm'))]
  u=urljoin(BASE,links[0]['href']).replace('http:','https:');p=fetch(u,f'pboc_{year}_flow.html',current_refresh)
  html=p.read_bytes()
  try:html=html.decode('utf-8')
  except UnicodeDecodeError:html=html.decode('gb18030')
  tables=pd.read_html(StringIO(html))
  rows=[]
  for table in tables:
   is_amount=True
   for _,row in table.iterrows():
    cells=[str(v).strip() for v in row]
    if cells[0].startswith('单位'):is_amount='亿元' in cells[0]
    if is_amount and re.fullmatch(r'20\d{2}\.\d{1,2}',cells[0]):
     val=pd.to_numeric(cells[1],errors='coerce');d=cells[0].split('.');rows.append((f'{d[0]}-{int(d[1]):02d}',val,u))
   if not rows:
    dates=None
    for _,row in table.iterrows():
     cells=[str(v).strip() for v in row]
     if sum(bool(re.fullmatch(r'20\d{2}\.\d{1,2}',v)) for v in cells)>=6: dates=cells[1:]
     if dates is not None and cells[0].startswith('社会融资规模') and any(c.isdigit() for c in cells[1:]):
      for d,v in zip(dates,cells[1:]):
       if re.fullmatch(r'20\d{2}\.\d{1,2}',d):a,b=d.split('.');rows.append((f'{a}-{int(b):02d}',pd.to_numeric(v,errors='coerce'),u))
  return rows
 with ThreadPoolExecutor(max_workers=4) as ex: rows=sum(list(ex.map(annual,urls)),[])
 # Get pre-2012 history directly from the published PBOC PDF, not a secondary series.
 p=fetch(HISTORY,'pboc_2002_history.pdf',False)
 with pdfplumber.open(p) as pdf:
  for page in pdf.pages:
   for line in (page.extract_text() or '').splitlines():
    m=re.match(r'^(20\d{2})\.(\d{2})\s+(-?\d+)\s',line)
    if m and int(m[1])<=2011:rows.append((f'{m[1]}-{m[2]}',float(m[3]),HISTORY))
 frame=pd.DataFrame(rows,columns=['observation_period','value','source_url']).sort_values('observation_period')
 # Keep exact annual rows; future empty slots are not observations.
 frame=frame.dropna(subset=['value']);frame=frame[frame.observation_period<str(pd.Timestamp.now().to_period('M'))]
 # Official annexes can repeat revised older months. Prefer the file with the
 # latest date embedded in its publication URL, independent of index/HSI.
 overlaps=frame[frame.observation_period.duplicated(keep=False)]
 overlaps.to_csv(ROOT/'output/diagnostics/social_financing_overlaps.csv',index=False)
 frame['publication_key']=frame.source_url.str.extract(r'/(20\d{12,})')[0].fillna('0000')
 frame=frame.sort_values(['publication_key','source_url'],kind='stable').drop_duplicates('observation_period',keep='last').sort_values('observation_period').drop(columns='publication_key')
 frame['release_date']=pd.NaT;frame['unit']='CNY_100million';frame['vintage_status']='revised_annual_mixed_vintages'
 profile(frame,'social_financing','CNY_100million');return frame
if __name__=='__main__':download()
