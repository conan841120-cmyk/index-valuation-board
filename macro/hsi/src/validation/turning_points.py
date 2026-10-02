import numpy as np
import pandas as pd

def turning_points(series):
 # Do not join across missing months to invent extrema.
 prev=series.shift(1);after=series.shift(-1)
 peaks=(series>prev)&(series>=after);troughs=(series<prev)&(series<=after)
 rows=[(str(t),'indicator_peak' if peaks.loc[t] else 'indicator_trough',series.loc[t]) for t in series.index[peaks|troughs]]
 return pd.DataFrame(rows,columns=['date','type','value'])

def match_score(series,reference):
 found=turning_points(series);rows=[]
 for _,r in reference[reference.type.str.startswith('indicator')].iterrows():
  t=pd.Period(r.reference_date,'M');window=found[found.type==r.type].copy()
  window['distance']=window.date.map(lambda d:abs(pd.Period(d,'M').ordinal-t.ordinal))
  nearest=window.sort_values('distance').iloc[0] if len(window) else None
  covered=t in series.index and pd.notna(series.get(t))
  neighbors=covered and pd.notna(series.get(t-1)) and pd.notna(series.get(t+1))
  if not neighbors:nearest=None
  rows.append(dict(reference_date=str(t),type=r.type,covered=covered,local_neighbors_available=neighbors,status='scorable' if neighbors else 'unscorable: missing adjacent month',matched_date=nearest.date if nearest is not None else None,distance_months=nearest.distance if nearest is not None else np.nan,match_within_1m=bool(covered and nearest is not None and nearest.distance<=1)))
 details=pd.DataFrame(rows)
 return (details.match_within_1m.mean() if len(details) else np.nan),details
