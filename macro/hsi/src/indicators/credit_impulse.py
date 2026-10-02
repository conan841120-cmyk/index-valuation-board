import pandas as pd
from src.processing.gdp import in_100million

def credit_impulse(sf,gdp_2q,sf_unit='CNY_100million',gdp_unit='CNY_100million'):
 sf=in_100million(sf,sf_unit);denominator=in_100million(gdp_2q,gdp_unit)
 if (denominator.dropna()<=0).any():raise ValueError('Nominal GDP must be positive')
 f=pd.DataFrame({'social_financing_monthly':sf})
 f['sf6']=sf.rolling(6,min_periods=6).sum()
 f['sf6_last_year']=f.sf6.shift(12)
 f['sf6_difference']=f.sf6-f.sf6_last_year
 f['credit_impulse_raw']=f.sf6_difference/denominator
 f['credit_impulse_3m']=f.credit_impulse_raw.rolling(3,min_periods=3).mean()
 f['credit_impulse_raw_percent']=100*f.credit_impulse_raw
 return f
