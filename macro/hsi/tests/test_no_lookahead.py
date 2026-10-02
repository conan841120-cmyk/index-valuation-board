import pandas as pd
import pytest
from src.indicators.leading_indicator import build
from src.indicators.weighted_zscore import MODES
from tests.test_start_date import data

@pytest.mark.parametrize('year',[2018,2020,2021,2022,2023])
@pytest.mark.parametrize('mode',MODES)
def test_future_month_deletion(year,mode):
 full=data();cut=pd.Period(f'{year}-12','M');short={}
 for name,d in full.items():
  periods=pd.PeriodIndex(d.observation_period,freq='Q' if name=='gdp' else 'M')
  short[name]=d[periods.end_time<=cut.end_time].copy()
 a=build(full,std_mode=mode);b=build(short,std_mode=mode)
 columns=['leading_indicator','z_retail','z_ppi','z_hk_m2','z_credit_impulse','credit_impulse_3m']
 pd.testing.assert_frame_equal(a.loc[f'{year}-01':str(cut),columns],b.loc[f'{year}-01':str(cut),columns],rtol=1e-12,atol=1e-12)
