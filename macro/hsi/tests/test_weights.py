import pandas as pd
import pytest
from src.indicators.leading_indicator import composite,load_config,FACTORS

def test_equal_weight_and_missing_never_reweight():
 z=pd.DataFrame([[1.,2.,3.,4.],[1.,2.,3.,None]],columns=FACTORS)
 assert composite(z).iloc[0]==2.5
 assert pd.isna(composite(z).iloc[1])

def test_parameters_locked(tmp_path):
 import yaml
 c=load_config();c['component_weights']['retail']=.3;p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump(c))
 with pytest.raises(ValueError):load_config(p)
