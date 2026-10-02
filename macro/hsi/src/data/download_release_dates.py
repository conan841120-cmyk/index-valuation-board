"""Publication-list dates, never infer publication dates from economic periods."""
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import pandas as pd
from bs4 import BeautifulSoup
from .common import fetch,ROOT
BASE='https://www.stats.gov.cn/sj/zxfb/'

def nbs(refresh=False):
 previous=ROOT/'data/processed/nbs_release_dates.csv'
 retained=pd.read_csv(previous) if refresh and previous.exists() else pd.DataFrame()
 first=fetch(BASE,'nbs_press_index.html',refresh)
 count=int(re.search(r'createPageHTML\((\d+),',first.read_text())[1])
 def page(i):
  p=first if i==0 else fetch(BASE+f'index_{i}.html',f'nbs_press_page_{i}.html',refresh)
  soup=BeautifulSoup(p.read_text(),'html.parser');rows=[]
  for a in soup.select('a.fl.pc_1600'):
   title=a.get('title','');parent=a.find_parent('li');date=re.search(r'\d{4}-\d{2}-\d{2}',parent.get_text())
   if not date:continue
   dataset=None;obs=None
   if '社会消费品零售' in title:dataset='retail'
   elif '工业生产者出厂价格' in title:dataset='ppi'
   elif '国内生产总值' in title and '核算' in title:dataset='gdp'
   if not dataset:continue
   if dataset=='gdp':
    m=re.search(r'(20\d{2})年(?:第)?([一二三四1-4])季度',title)
    if m:obs=f'{m[1]}-Q'+str({'一':1,'二':2,'三':3,'四':4}.get(m[2],m[2]))
   else:
    half=re.search(r'(20\d{2})年上半年',title)
    if half:obs=f'{half[1]}-06'
    m=re.search(r'(20\d{2})年(?:1[—－–-])?(\d{1,2})月份',title)
    if m:obs=f'{m[1]}-{int(m[2]):02d}'
    else:
     m=re.search(r'(\d{1,2})月份',title)
     if m:obs=f'{date[0][:4]}-{int(m[1]):02d}'
   if obs:rows.append((dataset,obs,date[0],urljoin(BASE,a['href']),title))
  return rows
 with ThreadPoolExecutor(max_workers=4) as pool:rows=sum(pool.map(page,range(min(count,5) if not retained.empty else count)),[])
 frame=pd.DataFrame(rows,columns=['dataset','observation_period','release_date','release_source_url','release_title'])
 if not retained.empty:frame=pd.concat([retained,frame],ignore_index=True)
 frame=frame.sort_values('release_date').drop_duplicates(['dataset','observation_period'])
 frame.to_csv(ROOT/'data/processed/nbs_release_dates.csv',index=False)
 for name in ['retail','ppi','gdp']:
  p=ROOT/'data/processed'/f'{name}.csv';f=pd.read_csv(p).drop(columns=['release_date','release_source_url','release_title'],errors='ignore')
  f=f.merge(frame[frame.dataset==name].drop(columns='dataset'),on='observation_period',how='left');f.to_csv(p,index=False)
  print(name,'verified publication-list dates',f.release_date.notna().sum(),flush=True)
 return frame
if __name__=='__main__':nbs()

def pboc(refresh=False):
 previous=ROOT/'data/processed/pboc_release_dates.csv'
 retained=pd.read_csv(previous) if refresh and previous.exists() else pd.DataFrame()
 base='https://www.pbc.gov.cn';index=base+'/diaochatongjisi/116219/116225/index.html'
 first=fetch(index,'pboc_monthly_releases.html',refresh)
 count=int(re.search(r'totalpage="(\d+)"',first.read_text())[1])
 def page(i):
  p=first if i==1 else fetch(base+f'/diaochatongjisi/116219/116225/11871-{i}.html',f'pboc_release_page_{i}.html',refresh)
  soup=BeautifulSoup(p.read_bytes(),'html.parser');rows=[]
  for a in soup.find_all('a',href=True):
   title=a.get_text(strip=True)
   direct='社会融资规模' in title and '统计数据报告' in title and '存量' not in title and '地区' not in title
   year=pd.Timestamp.now().year
   combined='金融统计数据报告' in title and title.startswith((str(year),str(year-1)))
   if not (direct or combined):continue
   tr=a.find_parent('tr');date=re.search(r'20\d{2}-\d{2}-\d{2}',tr.get_text()) if tr else None
   if not date:continue
   m=re.search(r'(20\d{2})年(\d{1,2})月份?',title)
   if m:obs=f'{m[1]}-{int(m[2]):02d}'
   else:
    y=re.search(r'(20\d{2})年',title)
    if not y:continue
    month=6 if '上半年' in title else 3 if '一季度' in title else 9 if '前三季度' in title else 12 if re.search(r'年(?:社会|金融)',title) else None
    if month is None:continue
    obs=f'{y[1]}-{month:02d}'
   url=urljoin(base,a['href'])
   if combined:
    content=fetch(url,f'pboc_financial_report_{obs}.html',refresh)
    if '社会融资规模增量' not in content.read_text():continue
   rows.append((obs,date[0],url,title,0 if direct else 1))
  return rows
 with ThreadPoolExecutor(max_workers=4) as pool:rows=sum(pool.map(page,range(1,min(count,5)+1 if not retained.empty else count+1)),[])
 # This report survives on the news archive but is absent from the statistical
 # list. Read the actual publication date, not the migrated URL's date.
 url=base+'/goutongjiaoliu/113456/113469/2025092212554594361/index.html'
 p=fetch(url,'pboc_2025_01_original_release.html',refresh)
 soup=BeautifulSoup(p.read_bytes(),'html.parser');title=soup.title.get_text(strip=True)
 date=re.search(r'2025-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',soup.get_text(' ',strip=True))
 if title!='2025年1月社会融资规模增量统计数据报告' or date is None:raise ValueError('Supplemental PBOC release could not be verified')
 rows.append(('2025-01',date[0][:10],url,title,0))
 f=pd.DataFrame(rows,columns=['observation_period','release_date','release_source_url','release_title','priority'])
 if not retained.empty:
  retained['priority']=0;f=pd.concat([retained,f],ignore_index=True)
 f=f.sort_values(['observation_period','priority','release_date']).drop_duplicates('observation_period').drop(columns='priority')
 f.to_csv(ROOT/'data/processed/pboc_release_dates.csv',index=False)
 p=ROOT/'data/processed/social_financing.csv';d=pd.read_csv(p).drop(columns=['release_date','release_source_url','release_title'],errors='ignore');d=d.merge(f,on='observation_period',how='left');d.to_csv(p,index=False)
 print('social financing verified publication-list dates',d.release_date.notna().sum(),flush=True)
 return f
