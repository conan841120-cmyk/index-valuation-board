"""Release-gated observation histories, without claiming historic vintages."""
import pandas as pd
import numpy as np
from src.indicators.leading_indicator import build

def available_history(data,as_of):
 cutoff=pd.Timestamp(as_of);out={}
 for name,d in data.items():
  d=d.copy()
  if name=='hsi':out[name]=d;continue
  dates=pd.to_datetime(d.release_date,errors='coerce')
  d['value']=d.value.where(dates.notna() & (dates<=cutoff))
  out[name]=d
 return out

def snapshot(data,as_of,mode='explicit_population',config=None):
 filtered=available_history(data,as_of)
 if any(filtered[n].value.notna().sum()==0 for n in ('retail','ppi','hk_m2','social_financing','gdp')):return None
 f=build(filtered,'release_aware',mode,config)
 valid=f[f.leading_indicator.notna()]
 if not len(valid):return None
 last=valid.iloc[-1].copy();last['observation_period_used']=str(valid.index[-1]);last['as_of_date']=pd.Timestamp(as_of).strftime('%Y-%m-%d')
 last['max_known_input_release_date']=max(pd.to_datetime(d.loc[d.value.notna(),'release_date'],errors='coerce').max() for n,d in filtered.items() if n!='hsi')
 last['stale_months']=pd.Timestamp(as_of).to_period('M').ordinal-valid.index[-1].ordinal
 return last

def real_time_history(data,mode,config):
 end=pd.Timestamp.now().to_period('M')
 rows=[]
 for m in pd.period_range('2012-07',end,freq='M'):
  # Current month is evaluated today, not at its future month end.
  asof=min(m.end_time.normalize(),pd.Timestamp.now().normalize())
  row=snapshot(data,asof,mode,config)
  if row is None:rows.append(dict(as_of_date=str(asof.date()),observation_period_used=None,leading_indicator=np.nan,status='insufficient verified release-date history'))
  else:
   r=row.to_dict();r['status']='release gated; latest-vintage and incomplete early history, not true historical vintage';rows.append(r)
 return pd.DataFrame(rows)
