"""Prefix-only standardization; missing rows still age by calendar months."""
import numpy as np
import pandas as pd
MODES=('explicit_population','explicit_unbiased','pandas_adjust_true','pandas_adjust_false')

def time_weight(age_months):
 return .5**(np.asarray(age_months)/36.)

def weighted_zscore(series,mode='explicit_population',min_periods=12):
 if mode not in MODES:raise ValueError(mode)
 if not isinstance(series.index,pd.PeriodIndex) or series.index.freqstr!='M':raise ValueError('Monthly PeriodIndex required')
 if not series.index.is_unique or not series.index.is_monotonic_increasing:raise ValueError('Unique ordered months required')
 grid=pd.period_range(series.index[0],series.index[-1],freq='M');x=series.reindex(grid).astype(float)
 if mode.startswith('pandas_'):
  window=x.ewm(halflife=36,adjust=(mode=='pandas_adjust_true'),ignore_na=False,min_periods=min_periods)
  mean=window.mean();std=window.std(bias=False)
 else:
  mean=pd.Series(np.nan,index=grid);std=mean.copy();v=x.to_numpy()
  for t in range(len(v)):
   mask=np.isfinite(v[:t+1])
   if mask.sum()<min_periods:continue
   weights=time_weight(t-np.arange(t+1)[mask]);values=v[:t+1][mask]
   total=weights.sum();mu=np.dot(weights,values)/total
   denom=total if mode=='explicit_population' else total-(weights@weights)/total
   var=np.dot(weights,(values-mu)**2)/denom if denom>0 else np.nan
   mean.iloc[t]=mu;std.iloc[t]=np.sqrt(max(0.,var))
 z=(x-mean)/std.where(std>0)
 return pd.DataFrame({'mean':mean,'std':std,'z':z}).reindex(series.index)
