import numpy as np
import pandas as pd
from src.data.common import ROOT
from src.indicators.leading_indicator import build
from src.indicators.weighted_zscore import MODES
from .turning_points import match_score,turning_points

def compare(data,refs,curve,config):
 rows=[];frames={};reference=curve.set_index(pd.PeriodIndex(curve.date,freq='M')).reference_indicator
 for g in ['observation_period','release_aware']:
  for mode in MODES:
   ident=f'candidate_{len(rows)+1:02d}';f=build(data,g,mode,config);s=f.leading_indicator
   f.to_csv(ROOT/'output/candidates'/f'{ident}.csv');frames[ident]=f
   pairs=pd.concat([s.rename('candidate'),reference.rename('reference')],axis=1).dropna()
   rmse=float(np.sqrt(((pairs.candidate-pairs.reference)**2).mean())) if len(pairs) else np.nan
   score,detail=match_score(s,refs);detail.to_csv(ROOT/'output/candidates'/f'{ident}_turning_matches.csv',index=False)
   turning_points(s).to_csv(ROOT/'output/candidates'/f'{ident}_turning_points.csv',index=False)
   start=s.first_valid_index();n=int(s.notna().sum())
   notes=[]
   if str(start)!='2012-07':notes.append('Start differs from 2012-07: verified early GDP release dates unavailable; candidate incomplete, not certified')
   if mode in ('explicit_unbiased','pandas_adjust_true'):notes.append('These two modes are mathematically equivalent under these settings')
   notes.append('Retail Jan/Feb missing retained; latest-vintage macro history; HSI correlations descriptive only')
   row=dict(candidate_id=ident,gdp_alignment_mode=g,standardization_mode=mode,start_date=str(start) if start else None,num_observations=n,screenshot_shape_score=1/(1+rmse) if np.isfinite(rmse) else np.nan,screenshot_absolute_rmse=rmse,screenshot_months_compared=len(pairs),turning_point_match_score=score,start_date_valid=(str(start)=='2012-07'),notes='; '.join(notes))
   for lag in [0,1,3,6]:
    name='hsi_contemporaneous_corr' if lag==0 else f'hsi_lead_{lag}m_corr'
    row[name]=s.corr(f.hsi_close.shift(-lag))
   rows.append(row)
 comparison=pd.DataFrame(rows);comparison.to_csv(ROOT/'output/candidates/candidate_comparison.csv',index=False)
 # Eligibility first; screenshot absolute levels only; NEVER HSI correlation.
 eligible=comparison[comparison.start_date_valid & comparison.screenshot_shape_score.notna()]
 best=eligible.sort_values('screenshot_shape_score',ascending=False).iloc[0].candidate_id if len(eligible) else None
 return comparison,frames,best
