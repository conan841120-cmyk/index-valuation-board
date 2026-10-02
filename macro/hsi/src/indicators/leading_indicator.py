import pandas as pd
import yaml
from src.data.common import ROOT
from src.processing.gdp import align_gdp
from .credit_impulse import credit_impulse
from .weighted_zscore import weighted_zscore
FACTORS=('retail','ppi','hk_m2','credit_impulse')

def load_config(path=None):
 c=yaml.safe_load(open(path or ROOT/'config.yaml'))
 fixed={'half_life_months':36,'composite_start':'2012-07','m2_history_start':'2011-08','min_history_observations':12}
 for k,v in fixed.items():
  if c[k]!=v:raise ValueError(f'Author-locked parameter {k} must be {v}')
 if c['component_weights']!={k:.25 for k in FACTORS}:raise ValueError('All four weights must be 0.25')
 if c['credit_impulse']!={'sf_window_months':6,'yoy_lag_months':12,'smoothing_months':3}:raise ValueError('Author-locked credit formula')
 if c['gdp_observation_rule']!='quarter_end_carry_forward' or c['missing_value_policy']!='preserve_nan':raise ValueError('Unsupported mapping/missing rule')
 if c['variance_pandas_bias'] is not False:raise ValueError('Pandas candidates explicitly use unbiased std (bias=False)')
 return c

def composite(z):
 return .25*z.loc[:,list(FACTORS)].sum(axis=1,min_count=4)

def build(data,gdp_mode='observation_period',std_mode='explicit_population',config=None):
 c=config or load_config()
 valid_ends=[pd.Period(data[n].dropna(subset='value').observation_period.max(),'M') for n in ('retail','ppi','hk_m2','social_financing')]
 months=pd.period_range('1993-01',min(valid_ends),freq='M');f=pd.DataFrame(index=months)
 for name in ['retail','ppi','hk_m2','social_financing']:
  d=data[name].copy();d.index=pd.PeriodIndex(d.observation_period,freq='M')
  if d.index.duplicated().any():raise ValueError(f'{name}: duplicated observation')
  if name=='hk_m2':d=d[d.index>=pd.Period(c['m2_history_start'],'M')]
  if name in ('retail','ppi','hk_m2') and not d.unit.eq('percent').all():raise ValueError(f'{name}: YoY percent required')
  f[name+'_yoy' if name!='social_financing' else 'social_financing_monthly']=d.value.reindex(months)
  f[name+'_release_date']=pd.to_datetime(d.release_date,errors='coerce').reindex(months)
 g=align_gdp(data['gdp'],months,gdp_mode);f=f.join(g)
 units=data['social_financing'].unit.unique()
 if len(units)!=1:raise ValueError('Convert mixed financing units first')
 ci=credit_impulse(f.social_financing_monthly,f.gdp_2q,sf_unit=units[0]);f=f.drop(columns='social_financing_monthly').join(ci)
 z=pd.DataFrame(index=months)
 for name in FACTORS:
  raw=f.credit_impulse_3m if name=='credit_impulse' else f[name+'_yoy']
  # Remove leading empty calendar rows before recursive EWM initialization.
  start=raw.first_valid_index();s=raw.loc[start:] if start is not None else raw
  w=weighted_zscore(s,std_mode,c['min_history_observations']);z[name]=w.z.reindex(months)
  f['z_'+name]=z[name];f['contribution_'+name]=.25*z[name]
  f['weighted_mean_'+name]=w['mean'].reindex(months);f['weighted_std_'+name]=w['std'].reindex(months)
 f['leading_indicator']=composite(z);f.loc[f.index<pd.Period(c['composite_start'],'M'),'leading_indicator']=float('nan')
 hsi=data.get('hsi')
 f['hsi_close']=pd.Series(hsi.value.to_numpy(),index=pd.PeriodIndex(hsi.observation_period,freq='M')).reindex(months) if hsi is not None else float('nan')
 f['m2_release_date']=f.hk_m2_release_date
 f.index.name='date';return f
