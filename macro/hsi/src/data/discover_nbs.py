import json
from .common import fetch
BASE='https://data.stats.gov.cn/dg/website'
def tree(code,pid=None):
 d=json.loads(fetch(BASE+'/publicrelease/web/external/new/queryIndexTreeAsync',f'nbs_tree_{code}_{pid or "root"}.json',params=dict(code=code,pid=pid)).read_text());return d.get('data',[])
def explore(code,pid=None,depth=0):
 for n in tree(code,pid):
  print('  '*depth,n['_name'],n['_id'],n.get('isLeaf'),flush=True)
  if depth<1 or any(w in n['_name'] for w in ['国内贸易','社会消费','工业生产者出厂价格分类','国民经济核算','国内生产总值']):
   if not n.get('isLeaf'):explore(code,n['_id'],depth+1)
if __name__=='__main__':
 explore(1);explore(2)
