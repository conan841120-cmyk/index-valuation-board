"""Regression checks for source mistakes discovered during this reproduction."""
import pandas as pd
from src.main import load_data
from src.indicators.leading_indicator import build

def test_official_flow_amount_not_percentage_appendix():
 d=load_data()['social_financing'].set_index('observation_period')
 # Published 2017--2019 revised nominal flow table, not its total=100 appendix.
 assert d.loc['2017-01','value']==37720
 assert d.loc['2018-01','value']==31417
 assert d.loc['2019-01','value']==46791
 assert d.unit.eq('CNY_100million').all()

def test_verified_supplemental_publication_dates():
 d=load_data()
 assert d['social_financing'].set_index('observation_period').loc['2025-01','release_date']=='2025-02-14'
 assert d['retail'].set_index('observation_period').loc['2026-06','release_date']=='2026-07-15'

def test_m2_total_yoy_and_official_early_hsi():
 d=load_data();m=d['hk_m2'].set_index('observation_period');h=d['hsi'].set_index('observation_period')
 assert m.loc['2011-08','value']==15.5
 assert m.loc['2011-09','value']==11.2
 assert h.loc['2012-07','value']==19796.81
 assert h.loc['2012-07','last_trading_date']=='2012-07-31'

def test_hsi_cannot_change_the_indicator():
 d=load_data();a=build(d)
 d['hsi']['value']=-1e12
 b=build(d)
 pd.testing.assert_frame_equal(a[['leading_indicator','z_retail','z_ppi','z_hk_m2','z_credit_impulse']],b[['leading_indicator','z_retail','z_ppi','z_hk_m2','z_credit_impulse']])
