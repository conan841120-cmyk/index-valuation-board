"""Validate genuine index OHLC against exchange sessions; never fill prices."""
import datetime as dt
from zoneinfo import ZoneInfo
import math
import exchange_calendars as xc
import pandas as pd

SYMBOLS = {'sp500':'SPX', 'ndx':'NDX'}


def calendar(start, end):
    schedule = xc.get_calendar('XNYS', start=start, end=end).schedule
    # Official Nasdaq ETA2025-1 and NYSE national-day-of-mourning notice.
    return schedule.drop(pd.Timestamp('2025-01-09'), errors='ignore')


def validate_rows(rows, now):
    if not rows:raise ValueError('Empty index history')
    dates = [r['date'] for r in rows]
    if dates != sorted(set(dates)):raise ValueError('Unordered or duplicate sessions')
    for r in rows:
        dt.date.fromisoformat(r['date'])
        o,c,h,l = (r[k] for k in ['open','close','high','low'])
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) or x <= 0 for x in (o,c,h,l)):
            raise ValueError('Invalid OHLC at '+r['date'])
        if not l <= o <= h:raise ValueError('Invalid opening/high/low bounds at '+r['date'])
        # Some index official closes are revised beyond the captured intraday range.
        # Preserve both fields; execution uses only open and close. Audit these rows.
        r['close_outside_range'] = not l <= c <= h
    schedule = calendar(dates[0], max(dates[-1], now.date().isoformat()))
    completed = schedule[schedule['close'] <= pd.Timestamp(now)]
    valid = set(x.date().isoformat() for x in completed.index)
    if any(d not in set(x.date().isoformat() for x in schedule.index) for d in dates):raise ValueError('Non-session date')
    rows = [r for r in rows if r['date'] in valid]
    if not rows:raise ValueError('No completed sessions')
    expected = [x.date().isoformat() for x in completed.loc[rows[0]['date']:rows[-1]['date']].index]
    if [r['date'] for r in rows] != expected:raise ValueError('Missing exchange session')
    return rows


def ibkr_rows(payload, now):
    if payload.get('chart_step') != 86400 or payload.get('source') != 'Last':raise ValueError('Daily last-price bars required')
    columns=['open','close','high','low']
    if any(len(payload[k]) != len(payload['time']) for k in columns):raise ValueError('OHLC length mismatch')
    rows=[dict(date=dt.datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat(),
               **{k:payload[k][i] for k in columns}) for i,t in enumerate(payload['time'])]
    return validate_rows(rows,now)


def freshness(now):
    schedule = calendar((now.date()-dt.timedelta(days=15)).isoformat(), (now.date()+dt.timedelta(days=370)).isoformat())
    complete = schedule[schedule['close'] <= pd.Timestamp(now)]
    latest = complete.iloc[-1]['close'].to_pydatetime()
    taipei = latest.astimezone(ZoneInfo('Asia/Taipei'))
    due = taipei.replace(hour=7, minute=0, second=0, microsecond=0)
    if due < taipei:due += dt.timedelta(days=1)
    return dict(expected_date=complete.index[-1].date().isoformat(), due_at=due.isoformat(),
                calendar_until=schedule.index[-1].date().isoformat(),
                sessions=[dict(date=x.date().isoformat(), close_at=r['close'].isoformat()) for x,r in schedule.iterrows()])
