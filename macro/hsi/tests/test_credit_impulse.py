import numpy as np
import pandas as pd
import pytest
from src.indicators.credit_impulse import credit_impulse

def test_formula_and_lag12():
 i=pd.period_range('2000-01',periods=50,freq='M');sf=pd.Series(np.arange(50.)**2+1,index=i)
 g=pd.Series(10000.,index=i);f=credit_impulse(sf,g)
 t=30
 assert f.sf6.iloc[t]==sf.iloc[t-5:t+1].sum()
 assert f.sf6_last_year.iloc[t]==f.sf6.iloc[t-12]
 assert f.sf6_last_year.iloc[t]!=f.sf6.iloc[t-6]
 assert f.sf6_difference.iloc[t]==f.sf6.iloc[t]-f.sf6.iloc[t-12]
 assert f.credit_impulse_raw.iloc[t]==f.sf6_difference.iloc[t]/10000
 assert f.credit_impulse_3m.iloc[t]==pytest.approx(f.credit_impulse_raw.iloc[t-2:t+1].mean())
 truncated=credit_impulse(sf.iloc[:t+1],g.iloc[:t+1])
 assert f.credit_impulse_3m.iloc[t]==truncated.credit_impulse_3m.iloc[t]

def test_unit_conversion_and_missing():
 i=pd.period_range('2000-01',periods=30,freq='M');s=pd.Series(np.arange(30.)+1,index=i)
 a=credit_impulse(s,pd.Series(20000.,index=i));b=credit_impulse(s,pd.Series(2.,index=i),gdp_unit='CNY_trillion')
 pd.testing.assert_frame_equal(a,b)
 with pytest.raises(ValueError):credit_impulse(s,pd.Series(2.,index=i),gdp_unit='USD')
 s.iloc[20]=np.nan;assert pd.isna(credit_impulse(s,pd.Series(2.,index=i)).sf6.iloc[23])
