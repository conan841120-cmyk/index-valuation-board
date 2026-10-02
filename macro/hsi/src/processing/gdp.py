"""Quarter-end observation mapping versus documented publication availability."""
import numpy as np
import pandas as pd
UNIT_MULTIPLIERS={'CNY_100million':1.,'CNY_billion':10.,'CNY_trillion':10000.}

def in_100million(values,unit):
 if unit not in UNIT_MULTIPLIERS:raise ValueError(f'Unsupported amount unit: {unit}')
 return values*UNIT_MULTIPLIERS[unit]

def align_gdp(quarterly,months,mode='observation_period'):
 if mode not in ('observation_period','release_aware'):raise ValueError(mode)
 q=quarterly.copy();q['quarter']=pd.PeriodIndex(q.observation_period,freq='Q')
 if not q.unit.isin(UNIT_MULTIPLIERS).all():raise ValueError('GDP unit not recognized')
 q['amount']=[in_100million(v,u) for v,u in zip(q.value,q.unit)]
 q['release_date']=pd.to_datetime(q.release_date,errors='coerce')
 q=q.dropna(subset='amount').sort_values('quarter');by=q.set_index('quarter')
 rows=[]
 for m in months:
  cutoff=m.end_time.normalize()
  available=q[q.quarter.map(lambda p:p.end_time.normalize())<=cutoff] if mode=='observation_period' else q[q.release_date<=cutoff]
  current=available.iloc[-1] if len(available) else None
  prev=(by.loc[current.quarter-1] if current is not None and current.quarter-1 in by.index else None)
  if mode=='release_aware' and prev is not None and (pd.isna(prev.release_date) or prev.release_date>cutoff):prev=None
  a=current.amount if current is not None else np.nan;b=prev.amount if prev is not None else np.nan
  rows.append(dict(gdp_current_quarter=a,gdp_previous_quarter=b,gdp_2q=a+b,gdp_quarter=str(current.quarter) if current is not None else None,gdp_release_date=current.release_date if current is not None else pd.NaT))
 return pd.DataFrame(rows,index=months)
