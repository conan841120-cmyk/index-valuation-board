"""Offline, frozen-v1.0 backtest of verified IBKR daily index bars."""
import csv
import json
import hashlib
import datetime as dt
import argparse
import copy
from pathlib import Path
from timing.strategy import signals,simulate,metrics,VERSION,PARAMETERS
from timing.data import ibkr_rows


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or ['no_records']);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)


REPO = Path(__file__).resolve().parents[1]
PRD = REPO.parent/'宽基择时PRD/宽基短期择时信号/需求文档/宽基短期择时信号-PRD.html'
CONTRACTS = {'sp500':416904, 'ndx':416843}


def load_version(root):
    """Validate the entire frozen boundary before any calculation/output writes."""
    root=Path(root)
    freeze=json.loads((root/'freeze.json').read_text())
    manifest=json.loads((root/'data-manifest.json').read_text())
    if freeze['strategy'] != VERSION or manifest['strategy'] != VERSION or freeze['parameters'] != PARAMETERS:
        raise ValueError('Frozen strategy version or parameters mismatch')
    if hashlib.sha256((REPO/'timing/strategy.py').read_bytes()).hexdigest()!=freeze['engine_sha256']:
        raise ValueError('Frozen engine mismatch')
    if hashlib.sha256(PRD.read_bytes()).hexdigest()!=freeze['prd_sha256']:
        raise ValueError('Frozen PRD mismatch')
    if not isinstance(freeze['data_version'],str) or not freeze['data_version'] or ('data_version' in manifest and manifest['data_version']!=freeze['data_version']):
        raise ValueError('Frozen data version mismatch')
    raw_inputs={key:(root/'private-input'/f'{key}.json').read_bytes() for key in CONTRACTS}
    for key,conid in CONTRACTS.items():
        metadata=manifest['data'][key]
        if metadata['contract_id']!=conid or metadata['security_type']!='IND' or not metadata['source']:
            raise ValueError('Frozen index identity mismatch: '+key)
        if hashlib.sha256(raw_inputs[key]).hexdigest()!=metadata['sha256']:
            raise ValueError('Frozen input SHA256 mismatch: '+key+'; create a separate data version with init')
    verified_at=dt.datetime.fromisoformat(manifest['verified_at'])
    if verified_at.utcoffset() is None:raise ValueError('Frozen verification time must include timezone')
    histories={}
    for key,raw in raw_inputs.items():
        rows=ibkr_rows(json.loads(raw),verified_at)
        metadata=manifest['data'][key]
        if len(rows)<221:raise ValueError('Insufficient frozen warmup: '+key)
        actual=(rows[0]['date'],rows[-1]['date'],len(rows),220,rows[220]['date'],0)
        recorded=tuple(metadata[k] for k in ['raw_start','raw_end','sessions','warmup','first_executable','missing_sessions'])
        if actual!=recorded:raise ValueError('Frozen coverage metadata mismatch: '+key)
        histories[key]=signals(rows)
    return histories,freeze,manifest


def initialize(root, inputs, provenance, from_version):
    """Explicitly establish a NEW local version using operator-reviewed source evidence."""
    root,inputs=Path(root),Path(inputs)
    if root.exists():raise ValueError('Version directory already exists; init never replaces a frozen version')
    _,freeze,_=load_version(from_version)
    manifest=json.loads(Path(provenance).read_text())
    if not manifest.get('usage'):raise ValueError('Reviewed provenance must include usage and index source evidence')
    now=dt.datetime.now(dt.timezone.utc)
    raw_inputs={key:(inputs/f'{key}.json').read_bytes() for key in CONTRACTS}
    for key,conid in CONTRACTS.items():
        metadata=manifest['data'][key]
        if metadata['contract_id']!=conid or metadata['security_type']!='IND' or not metadata['source']:
            raise ValueError('Reviewed index identity missing: '+key)
        rows=ibkr_rows(json.loads(raw_inputs[key]),now)
        if len(rows)<221:raise ValueError('Insufficient warmup: '+key)
        metadata.update(sha256=hashlib.sha256(raw_inputs[key]).hexdigest(),raw_start=rows[0]['date'],raw_end=rows[-1]['date'],sessions=len(rows),warmup=220,first_executable=rows[220]['date'],missing_sessions=0)
    freeze=copy.deepcopy(freeze)
    freeze.update(data_version=root.name,frozen_at=now.isoformat(),parent_manifest_sha256=hashlib.sha256((Path(from_version)/'data-manifest.json').read_bytes()).hexdigest())
    manifest.update(data_version=root.name,strategy=VERSION,verified_at=now.isoformat())
    # All input/source validation above precedes creation of the new version.
    (root/'private-input').mkdir(parents=True)
    for key,raw in raw_inputs.items():(root/'private-input'/f'{key}.json').write_bytes(raw)
    (root/'freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n')
    (root/'data-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return root


def run(root, output=None):
    root=Path(root)
    histories,freeze,manifest=load_version(root)
    out=Path(output) if output else root/'results/replays'/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if out.exists():raise ValueError('Replay output already exists; choose a new directory')
    outputs={f'{key}-signals.csv':rows for key,rows in histories.items()}
    common=max(v[220]['date'] for v in histories.values());end=min(v[-1]['date'] for v in histories.values())
    results=[];yearly=[];attribution=[]
    for key,history in histories.items():
        for scope,start in [('longest',history[220]['date']),('common',common)]:
            rows=[r for r in history if scope=='longest' or r['date']<=end]
            for mode in ['AB','A','B']:
                for fee in [0,.0005,.001]:
                    run=simulate(rows,fee,mode,start)
                    prefix=f'{key}-{scope}-{mode}-{fee:.4f}'
                    for kind in ['trades','orders','equity']:outputs[f'{prefix}-{kind}.csv']=run[kind]
                    m=metrics(run);results.append(dict(index=key,scope=scope,mode=mode,fee=fee,start=run['equity'][0]['date'],end=run['equity'][-1]['date'],**m))
                    for category in 'AB':
                        group=[t for t in run['trades'] if t['kind']==category]
                        attribution.append(dict(index=key,scope=scope,mode=mode,fee=fee,kind=category,count=len(group),win_rate=sum(t['net_return']>0 for t in group)/len(group) if group else None,mean_return=sum(t['net_return'] for t in group)/len(group) if group else None,average_holding=sum(t['holding_days'] for t in group)/len(group) if group else None,primary_reasons={x:sum(t['primary']==x for t in group) for x in ['stop','profit','ma5','expiry']}))
                    for year in sorted(set(e['date'][:4] for e in run['equity'])):
                        e=[e for e in run['equity'] if e['date'].startswith(year)]
                        i=run['equity'].index(e[0]);prev=run['equity'][i-1] if i else {'equity':1,'benchmark':1}
                        yearly.append(dict(index=key,scope=scope,mode=mode,fee=fee,year=year,
                                           strategy_return=e[-1]['equity']/prev['equity']-1,benchmark_return=e[-1]['benchmark']/prev['benchmark']-1,
                                           closed_trades=sum(t['exit_date'].startswith(year) for t in run['trades'])))
    # Every version/input validation and all 36 simulations succeed before writing.
    outputs.update({'annual.csv':yearly,'attribution.csv':attribution})
    summary=json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    receipt=dict(strategy=VERSION,data_version=freeze['data_version'],manifest_sha256=hashlib.sha256((root/'data-manifest.json').read_bytes()).hexdigest(),freeze_sha256=hashlib.sha256((root/'freeze.json').read_bytes()).hexdigest(),runs=len(results),source_version=str(root.resolve()))
    out.mkdir(parents=True)
    for name,rows in outputs.items():write_csv(out/name,rows)
    (out/'summary.json').write_text(summary)
    (out/'run.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print('Replay saved to '+str(out))
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command')
    replay=sub.add_parser('run',help='Verify and replay an existing frozen version into a new output directory')
    replay.add_argument('root',nargs='?',default='research/timing-v1');replay.add_argument('--out')
    init=sub.add_parser('init',help='Establish a separate version; never replace an existing directory')
    init.add_argument('root');init.add_argument('--inputs',required=True);init.add_argument('--provenance',required=True);init.add_argument('--from-version',default='research/timing-v1')
    args=parser.parse_args()
    if args.command=='init':initialize(args.root,args.inputs,args.provenance,args.from_version)
    else:run(getattr(args,'root','research/timing-v1'),getattr(args,'out',None))
