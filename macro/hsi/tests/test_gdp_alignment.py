import pandas as pd
from src.processing.gdp import align_gdp

def test_two_quarters_and_publication_delay():
 q=pd.DataFrame({'observation_period':['2011-Q4','2012-Q1','2012-Q2'],'value':[90.,100.,110.],'unit':'CNY_100million','release_date':['2012-01-17','2012-04-13','2012-07-13']})
 months=pd.period_range('2012-05','2012-08',freq='M')
 a=align_gdp(q,months);b=align_gdp(q,months,'release_aware')
 assert a.loc['2012-06','gdp_2q']==210
 assert b.loc['2012-06','gdp_2q']==190
 assert b.loc['2012-07','gdp_2q']==210
 assert a.loc['2012-05','gdp_quarter']=='2012Q1'
