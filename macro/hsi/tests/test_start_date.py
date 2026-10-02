import pandas as pd
from src.data.common import ROOT
from src.indicators.leading_indicator import build
from src.indicators.weighted_zscore import MODES

def data():
 return {n:pd.read_csv(ROOT/'data/processed'/f'{n}.csv') for n in ['retail','ppi','hk_m2','social_financing','gdp']}

def test_actual_composite_starts_july_2012():
 for mode in MODES:
  f=build(data(),std_mode=mode)
  assert str(f.leading_indicator.first_valid_index())=='2012-07'
  assert pd.isna(f.loc['2012-06','z_hk_m2'])
  assert pd.notna(f.loc['2012-07','z_hk_m2'])
