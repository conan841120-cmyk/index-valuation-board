"""Shared-strategy history adapter. Personal preview consumes a verified frozen version."""
import argparse
import datetime as dt
import json
from pathlib import Path
from timing.data import calendar, freshness, SYMBOLS
from timing.strategy import VERSION

FIELDS = ('date','close','eligible','ma200','prior_ma200','ma5','r5','volatility','threshold',
          'deviation','trend_change','multiple','kind','trend','near','conflict','first_date','consecutive','start_known')


def history_payload(series, symbol, source, source_sha256, generated_at):
    """Series already computed by strategy.signals on full calendar-validated history."""
    schedule=calendar(series[0]['date'],series[-1]['date'])
    return dict(schema_version=1,strategy=VERSION,symbol=symbol,source=source,source_sha256=source_sha256,
                generated_at=generated_at,price_start=series[0]['date'],price_end=series[-1]['date'],
                eligible_start=next((r['date'] for r in series if r['eligible']),None),
                sessions=[x.date().isoformat() for x in schedule.index],
                rows=[{k:r.get(k) for k in FIELDS} for r in series])


def preview(version, destination):
    from timing.backtest import load_version
    series,freeze,manifest=load_version(version)
    now=dt.datetime.now(dt.timezone.utc)
    data=dict(schema_version=1,strategy=VERSION,checked_at=now.isoformat(),**freshness(now),indices={},
              preview_notice='本地个人历史快照，尚未接入生产日更',
              data_version=freeze['data_version'])
    for key,symbol in SYMBOLS.items():
        source=manifest['data'][key]
        data['indices'][key]=dict(symbol=symbol,latest=series[key][-1],successful_at=manifest['verified_at'],error=None,
            history=history_payload(series[key],symbol,source['source'],source['sha256'],now.isoformat()))
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default='research/timing-v1')
    parser.add_argument('--out',default='data/timing/latest.json')
    args=parser.parse_args();preview(args.version,args.out)
