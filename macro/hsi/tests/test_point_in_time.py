import pandas as pd
from src.validation.point_in_time import available_history,snapshot
from tests.test_start_date import data

def test_unreleased_and_unknown_dates_hidden():
 x={'retail':pd.DataFrame({'value':[1,2,3],'release_date':['2018-12-01','2019-01-01',None]})}
 f=available_history(x,'2018-12-31')['retail'];assert f.value.iloc[0]==1;assert f.value.iloc[1:].isna().all()

def test_release_gated_synthetic_future_poisoning():
 x=data()
 # Synthetic release dates ONLY in this test, never in production datasets.
 for n,f in x.items():
  p=pd.PeriodIndex(f.observation_period,freq='Q' if n=='gdp' else 'M')
  f['release_date']=(p.end_time.normalize()+pd.Timedelta(days=20)).astype(str)
 a=snapshot(x,'2023-12-31')
 for n,f in x.items():f.loc[pd.to_datetime(f.release_date)>'2023-12-31','value']=1e12
 b=snapshot(x,'2023-12-31')
 assert a is not None
 pd.testing.assert_series_equal(a,b)
