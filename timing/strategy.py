"""strategy-v1.0: shared daily signal and execution engine; no parameter tuning."""
from decimal import Decimal as D
import math

VERSION = 'strategy-v1.0'
PARAMETERS = dict(ma=200, trend_lag=20, return_days=5, volatility_days=60,
                  a_multiple=2, b_deviation=-.10, near=.02, profit=.025, loss=-.15,
                  max_holding=20, costs=[0, .0005, .001])


def classify(close, ma200, prior_ma200, ma5, r5, volatility):
    c, m, p, m5, r, v = map(lambda x: D(str(x)), (close, ma200, prior_ma200, ma5, r5, volatility))
    trend = m > p
    kind = 'A' if trend and c > m and r < -2*v else 'B' if trend and c <= m*D('.9') else None
    return dict(kind=kind, trend=trend, near=abs(c-m) <= m*D('.02'), conflict=bool(kind and c > m5))


def signals(rows):
    """Input is calendar-validated, ordered complete price-index sessions."""
    closes = [D(str(r['close'])) for r in rows]
    ma = [sum(closes[i-199:i+1])/200 if i >= 199 else None for i in range(len(rows))]
    returns = [closes[i]/closes[i-5]-1 if i >= 5 else None for i in range(len(rows))]
    result, first, count, known = [], None, 0, False
    for i, row in enumerate(rows):
        item = dict(row, eligible=i >= 219)
        if i >= 219:
            c, m5, m, prior = closes[i], sum(closes[i-4:i+1])/5, ma[i], ma[i-20]
            v = sum(abs(x) for x in returns[i-60:i])/60
            flags = classify(c, m, prior, m5, returns[i], v)
            if flags['kind']:
                if count == 0: first = row['date'] if known else None
                count += 1
            else:
                count, first, known = 0, None, True
            item.update(flags, ma200=float(m), prior_ma200=float(prior), ma5=float(m5),
                        r5=float(returns[i]), volatility=float(v), threshold=float(-2*v),
                        deviation=float(c/m-1), trend_change=float(m/prior-1),
                        multiple=float(-returns[i]/v) if v else None,
                        first_date=first, consecutive=count, start_known=known)
        result.append(item)
    return result


def exit_tags(row, entry_price):
    c, p = D(str(row['close'])), D(str(entry_price))
    return [name for name, yes in [('stop', c <= p*D('.85')), ('profit', c >= p*D('1.025')),
                                 ('ma5', c > D(str(row['ma5'])))] if yes]


def simulate(rows, fee=0, mode='AB', start=None):
    """Orders form only at close, execute next open; day 20 executes at close."""
    cash, quantity, pending, entry = 1., 0., None, None
    trades, orders, equity = [], [], []
    active = [r for r in rows if r['eligible'] and (start is None or r['date'] >= start)]
    if not active: raise ValueError('No evaluable sessions')
    prior = [r for r in rows if r['date'] < active[0]['date'] and r['eligible']]
    if prior and prior[-1]['kind'] and prior[-1]['kind'] in mode:
        pending = dict(side='buy', signal_date=prior[-1]['date'], kind=prior[-1]['kind'])
        orders.append(pending)
    exposure = 0
    for i, row in enumerate(active):
        date, opening, close = row['date'], row['open'], row['close']
        if pending:
            order = pending
            if order['side'] == 'sell':
                cash = quantity*opening*(1-fee)
                trades.append(dict(entry, exit_date=date, exit_price=opening, exit_session='open',
                                   holding_days=i-entry['entry_index']+1, reasons=order['reasons'],
                                   primary=order['reasons'][0], price_return=opening/entry['entry_price']-1,
                                   net_return=cash/entry['capital_before']-1))
                quantity, entry = 0., None
            else:
                quantity = cash/(opening*(1+fee))
                entry = dict(signal_date=order['signal_date'], entry_date=date, entry_price=opening,
                             kind=order['kind'], entry_index=i, capital_before=cash, quantity=quantity)
                cash = 0.
            order.update(fill_date=date, fill_price=opening, fill_session='open')
            pending = None
        held_today = bool(quantity)
        if quantity:
            tags = exit_tags(row, entry['entry_price'])
            if i-entry['entry_index']+1 == 20:
                cash = quantity*close*(1-fee)
                trades.append(dict(entry, exit_date=date, exit_price=close, exit_session='close',
                                   holding_days=20, reasons=['expiry']+tags, primary='expiry',
                                   price_return=close/entry['entry_price']-1, net_return=cash/entry['capital_before']-1))
                orders.append(dict(side='sell', signal_date=date, fill_date=date, fill_price=close,
                                   fill_session='close', reasons=['expiry']+tags))
                quantity, entry = 0., None
            elif tags:
                pending = dict(side='sell', signal_date=date, reasons=tags)
                orders.append(pending)
        if not quantity and row['kind'] and row['kind'] in mode:
            pending = dict(side='buy', signal_date=date, kind=row['kind'])
            orders.append(pending)
        exposure += held_today
        equity.append(dict(date=date, equity=cash+quantity*close, cash=cash, quantity=quantity,
                           exposed=held_today))
    qbase = 1/(active[0]['open']*(1+fee))
    for e,r in zip(equity,active):e['benchmark']=qbase*r['close']
    return dict(trades=trades, orders=orders, equity=equity, open_position=entry,
                pending_order=pending, exposure=exposure/len(active))


def metrics(run):
    import datetime as dt
    eq, tr = run['equity'], run['trades']
    years = (dt.date.fromisoformat(eq[-1]['date'])-dt.date.fromisoformat(eq[0]['date'])).days/365.2425
    def stats(field):
        peak, drawdown = 1., 0.
        for e in eq:
            peak = max(peak, e[field]); drawdown = min(drawdown, e[field]/peak-1)
        return dict(total_return=eq[-1][field]-1, cagr=eq[-1][field]**(1/years)-1 if years else None, max_drawdown=drawdown)
    return dict(strategy=stats('equity'), benchmark=stats('benchmark'), closed_trades=len(tr),
                win_rate=sum(t['net_return']>0 for t in tr)/len(tr) if tr else None,
                average_return=sum(t['net_return'] for t in tr)/len(tr) if tr else None,
                average_holding=sum(t['holding_days'] for t in tr)/len(tr) if tr else None,
                exposure=run['exposure'], primary_reasons={k:sum(t['primary']==k for t in tr) for k in ['stop','profit','ma5','expiry']},
                attribution={k:dict(count=sum(t['kind']==k for t in tr), net_return_sum=sum(t['net_return'] for t in tr if t['kind']==k)) for k in 'AB'},
                open_position=run['open_position'], pending_order=run['pending_order'])
