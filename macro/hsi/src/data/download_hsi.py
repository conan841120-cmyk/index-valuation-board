"""HSI comparison data: official HKEX where available, Sina in between."""
import ast
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup
from .common import fetch,profile,ROOT,RAW

URL='https://finance.sina.com.cn/stock/hkstock/HSI/klc_kl.js'
HIGHLIGHTS='https://www.hkex.com.hk/Market-Data/Statistics/Consolidated-Reports/HKEX-Monthly-Market-Highlights'

def factbook(year,refresh=False):
 url=f'https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Reports/HKEX-Fact-Book/HKEx-Fact-Book-{year}/fb_{year}.pdf'
 path=fetch(url,f'hkex_factbook_{year}.pdf',refresh)
 with pdfplumber.open(path) as pdf:text=pdf.pages[23].extract_text() or ''
 if 'Hang Seng Index' not in text or f'daily closing ({year})' not in text.lower():raise ValueError('HKEX factbook page changed')
 (ROOT/'data/interim'/f'hsi_factbook_{year}_text.txt').write_text(text)
 last={}
 for line in text.splitlines():
  cells=line.split()
  if len(cells)!=13 or not cells[0].isdigit() or not 1<=int(cells[0])<=31:continue
  for month,cell in enumerate(cells[1:],1):
   if re.fullmatch(r'\d[\d,]*\.\d{2}',cell):last[month]=(int(cells[0]),float(cell.replace(',','')))
 if len(last)!=12:raise ValueError(f'{year}: cannot read twelve official month-end closes')
 return pd.DataFrame([dict(observation_period=f'{year}-{m:02d}',value=v,last_trading_date=f'{year}-{m:02d}-{day:02d}',source_url=url,unit='index_points',release_date=None,source_type='official_HKEX_factbook') for m,(day,v) in last.items()])

def monthly_official(refresh=False):
 path=fetch(HIGHLIGHTS,'hkex_highlights.html',refresh,params={'sc_lang':'en'})
 soup=BeautifulSoup(path.read_bytes(),'html.parser');options=[]
 for item in soup.select('#firstDropdownList .select-item'):
  label=item.get_text(' ',strip=True)
  try:month=pd.to_datetime(label).strftime('%Y-%m')
  except (ValueError,TypeError):continue
  options.append((month,item['data-id']))
 if not options:raise ValueError('HKEX monthly archive selector not found')
 def one(option):
  month,guid=option
  p=fetch(HIGHLIGHTS,f'hkex_{month}_highlight.html',refresh,params={'sc_lang':'en','select':guid})
  s=BeautifulSoup(p.read_bytes(),'html.parser')
  for tr in s.find_all('tr'):
   cells=tr.find_all('td')
   if len(cells)>1 and cells[0].get_text(strip=True)=='Hang Seng Index':
    return dict(observation_period=month,value=float(cells[1].get_text(strip=True).replace(',','')),source_url=HIGHLIGHTS+'?sc_lang=en&select='+guid,unit='index_points',source_type='official_HKEX_monthly_highlights')
  raise ValueError(f'{month}: missing official HSI closing field')
 with ThreadPoolExecutor(max_workers=4) as pool:return pd.DataFrame(pool.map(one,options))

def download(refresh=False):
 p=fetch(URL,'sina_hsi_encoded.js',refresh)
 source=fetch('https://raw.githubusercontent.com/akfamily/akshare/master/akshare/stock/cons.py','akshare_stock_constants.py',refresh)
 # Extract a literal math decoder only; never execute the downloaded Python.
 tree=ast.parse(source.read_text())
 code=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='hk_js_decode' for t in n.targets))
 if any(token in code for token in ['require','fetch(','XMLHttpRequest','process','window','document','eval(']):raise ValueError('Decoder is not a pure math function')
 decoder=RAW/'sina_decoder.js';decoder.write_text(code);out=ROOT/'data/interim/sina_hsi_daily.json'
 subprocess.run(['node',str(ROOT/'src/data/decode_sina.js'),str(p),str(decoder),str(out)],check=True)
 d=pd.DataFrame(json.loads(out.read_text()));print('decoded daily rows',len(d),flush=True)
 f=pd.DataFrame({'timestamp':pd.to_datetime(d.date,utc=True),'value':pd.to_numeric(d.close)})
 f=f[f.timestamp>=pd.Timestamp('2012-07-01',tz='UTC')].dropna()
 f['observation_period']=f.timestamp.dt.tz_localize(None).dt.to_period('M').astype(str)
 f=f[f.observation_period<str(pd.Timestamp.now().to_period('M'))].groupby('observation_period',as_index=False).last()
 f['last_trading_date']=f.timestamp.dt.strftime('%Y-%m-%d');f['release_date']=f.last_trading_date
 f['unit']='index_points';f['source_url']=URL;f['source_type']='secondary_Sina_daily';f=f.drop(columns='timestamp')
 early=pd.concat([factbook(y,False) for y in (2012,2013)])
 recent=monthly_official(refresh)
 official=pd.concat([early,recent],ignore_index=True)
 check=official[['observation_period','value']].merge(f[['observation_period','value']],on='observation_period',suffixes=('_official','_sina'))
 check['difference']=check.value_official-check.value_sina
 check.to_csv(ROOT/'output/diagnostics/hsi_official_crosscheck.csv',index=False)
 if check.difference.abs().gt(.01).any():raise ValueError('HSI sources disagree beyond rounding')
 for col in ('last_trading_date','release_date'):recent[col]=recent.observation_period.map(f.set_index('observation_period')[col])
 f=pd.concat([f,early,recent],ignore_index=True).drop_duplicates('observation_period',keep='last').sort_values('observation_period')
 f=f[f.observation_period>='2012-07'].reset_index(drop=True)
 profile(f,'hsi','index_points');return f

if __name__=='__main__':download()
