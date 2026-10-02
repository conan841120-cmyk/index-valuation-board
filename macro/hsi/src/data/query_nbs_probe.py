import json
from .common import fetch
from .discover_nbs import BASE,tree
for n in tree(1,'55de73673b3d440585cff051fb2e8694'):print(n['_name'],n['_id'],n['isLeaf'])
for name in ['retail','gdp']:
 d=json.loads(open(f'data/raw/nbs_{name}_fields.json').read())
 print(name,[(n['i_showname'],n['_id']) for n in d['data']['list']])
 ident= 'aaac57d54d2e465d91bc9f3ea1a8618e' if name=='retail' else next(n['_id'] for n in d['data']['list'] if n['i_showname'].startswith('国内生产总值当季'))
 body=dict(cid='',indicatorIds=[ident],daCatalogId='',das=[{'text':'全国','value':'000000000000'}],showType=1,dts=['200001MM-202608MM' if name=='retail' else '200001SS-202602SS'])
 p=fetch(BASE+'/publicrelease/web/external/getEsDataByIndicatorIdAndDa',f'nbs_{name}_data_probe.json',json_body=body)
 print(p.read_text()[:1200])
