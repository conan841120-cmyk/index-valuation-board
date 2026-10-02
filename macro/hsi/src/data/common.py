"""Cache exact HTTP responses; only --refresh re-downloads successful objects."""
import hashlib,json
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw'
def fetch(url,name,refresh=False,params=None,json_body=None,headers=None,session=None):
 path=RAW/name; meta=path.with_suffix(path.suffix+'.meta.json')
 if path.exists() and meta.exists() and not refresh:
  record=json.loads(meta.read_text()); print(f'CACHE {name} HTTP {record["status"]}',flush=True);return path
 client=session or requests.Session()
 if session is None:
  client.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=.5,status_forcelist=[502,503,504])))
 method=client.post if json_body is not None else client.get
 kwargs={'json':json_body} if json_body is not None else {'params':params}
 r=method(url,timeout=35,headers={'User-Agent':'Mozilla/5.0',**(headers or {})},**kwargs)
 record=dict(source=r.url,method='POST' if json_body is not None else 'GET',request_body=json_body,status=r.status_code,bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest(),retrieved_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
 print(f'DOWNLOAD {name}: {record}',flush=True)
 r.raise_for_status()
 temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_bytes(r.content);temporary.replace(path)
 meta.write_text(json.dumps(record,ensure_ascii=False,indent=2));return path

def profile(frame,name,unit):
 valid=frame.dropna(subset='value')
 print(json.dumps(dict(dataset=name,rows=len(frame),valid_rows=len(valid),first_date=str(valid.observation_period.min()),last_date=str(valid.observation_period.max()),unit=unit,missing_values=int(frame.value.isna().sum()),duplicates=int(frame.observation_period.duplicated().sum())),ensure_ascii=False),flush=True)
 if frame.observation_period.duplicated().any():raise ValueError(f'{name}: duplicate dates')
 frame.to_csv(ROOT/'data/processed'/f'{name}.csv',index=False)
