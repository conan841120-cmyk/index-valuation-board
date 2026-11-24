"""Independent ledger-level accounting/time audit of exported runs."""
import csv
import json
import math
from pathlib import Path


def verify(root=Path('research/timing-v1/results')):
    checked=0
    for path in root.glob('*-trades.csv'):
        prefix=path.name[:-11];fee=float(prefix.rsplit('-',1)[1]);key=prefix.split('-')[0]
        signals={r['date']:r for r in csv.DictReader((root/f'{key}-signals.csv').open())}
        dates=list(signals);previous_exit=None
        for t in csv.DictReader(path.open()):
            entry,exit,signal=t['entry_date'],t['exit_date'],t['signal_date']
            assert dates.index(entry)==dates.index(signal)+1
            assert signals[signal]['kind']==t['kind']
            assert float(t['entry_price'])==float(signals[entry]['open'])
            assert float(t['exit_price'])==float(signals[exit][t['exit_session']])
            assert int(t['holding_days'])==dates.index(exit)-dates.index(entry)+1
            assert int(t['holding_days'])<=20
            if t['primary']=='expiry':assert int(t['holding_days'])==20 and t['exit_session']=='close'
            expected=float(t['exit_price'])/float(t['entry_price'])*(1-fee)/(1+fee)-1
            assert math.isclose(expected,float(t['net_return']),abs_tol=1e-12)
            if previous_exit:assert previous_exit<entry
            previous_exit=exit;checked+=1
        equity=list(csv.DictReader((root/f'{prefix}-equity.csv').open()))
        first=equity[0]['date']
        for e in equity:
            close=float(signals[e['date']]['close'])
            assert math.isclose(float(e['equity']),float(e['cash'])+float(e['quantity'])*close,abs_tol=1e-12)
            assert math.isclose(float(e['benchmark']),close/(float(signals[first]['open'])*(1+fee)),abs_tol=1e-12)
    result={'runs':len(list(root.glob('*-trades.csv'))),'closed_trade_records_checked':checked,'status':'pass'}
    (root/'ledger-audit.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':print(verify())
