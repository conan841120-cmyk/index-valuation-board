import numpy as np
import pandas as pd
import pytest
from src.indicators.weighted_zscore import weighted_zscore,time_weight,MODES

def test_half_life():
 assert np.allclose(time_weight([0,36,72,108]),[1,.5,.25,.125])

@pytest.mark.parametrize('mode',MODES)
def test_prefix_invariance(mode):
 i=pd.period_range('2000-01',periods=150,freq='M');x=pd.Series(np.random.default_rng(0).normal(size=150),index=i);x.iloc[20]=np.nan
 full=weighted_zscore(x,mode);short=weighted_zscore(x.iloc[:100],mode)
 pd.testing.assert_frame_equal(full.iloc[:100],short)

def test_unbiased_matches_pandas_adjust_true_with_missing_calendar_months():
 i=pd.period_range('2000-01',periods=100,freq='M');x=pd.Series(np.arange(100.)**.5,index=i);x.iloc[[18,19,60]]=np.nan
 a=weighted_zscore(x,'explicit_unbiased');b=weighted_zscore(x,'pandas_adjust_true')
 np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-12,equal_nan=True)

def test_manual_population_and_constant():
 i=pd.period_range('2000-01',periods=3,freq='M');x=pd.Series([1.,3.,9.],index=i)
 w=time_weight([2,1,0]);mu=np.average(x,weights=w);sd=np.sqrt(np.average((x-mu)**2,weights=w))
 assert weighted_zscore(x,min_periods=2).z.iloc[-1]==pytest.approx((9-mu)/sd)
 assert weighted_zscore(x*0+1,min_periods=2).z.isna().all()
