import datetime as dt
import unittest
from unittest.mock import patch
from timing.strategy import classify, signals, simulate, exit_tags, metrics


def row(i,close=100,opening=100,kind=None,ma5=110):
    return dict(date=(dt.date(2020,1,1)+dt.timedelta(days=i)).isoformat(),open=opening,close=close,kind=kind,ma5=ma5,eligible=True,trend=False,high=200,low=10)

class TimingTests(unittest.TestCase):
    def test_formula_boundaries(self):
        self.assertIsNone(classify(101,100,100,101,-.0301,.015)['kind'])
        self.assertIsNone(classify(100,100,99,100,-.0301,.015)['kind'])
        self.assertIsNone(classify(101,100,99,100,-.03,.015)['kind'])
        self.assertEqual(classify(101,100,99,100,-.0301,.015)['kind'],'A')
        self.assertIsNone(classify(101,100,99,100,.10,.015)['kind'])
        self.assertEqual(classify(90,100,99,100,.1,.015)['kind'],'B')
        self.assertIsNone(classify(90.01,100,99,100,-.2,.015)['kind'])
        self.assertIsNone(classify(90,100,101,100,-.2,.015)['kind'])
        for c in [98,102]:self.assertTrue(classify(c,100,99,100,-.1,.01)['near'])
        for c in [97.9999,102.0001]:self.assertFalse(classify(c,100,99,100,-.1,.01)['near'])
        self.assertTrue(classify(101,100,99,100,-.04,.015)['conflict'])
        self.assertFalse(classify(101,100,99,101,-.04,.015)['conflict'])
        self.assertEqual(classify(101,100,99,101,-.00001,0)['kind'],'A')
    def test_windows_and_no_future(self):
        raw=[dict(date=str(i),open=100+i,close=100+i) for i in range(260)]
        out=signals(raw)
        self.assertFalse(out[218]['eligible']);self.assertTrue(out[219]['eligible'])
        self.assertAlmostEqual(out[219]['ma200'],sum(range(120,320))/200)
        self.assertAlmostEqual(out[219]['prior_ma200'],sum(range(100,300))/200)
        self.assertAlmostEqual(out[219]['volatility'],sum(abs((100+j)/(95+j)-1) for j in range(159,219))/60)
        self.assertEqual(out[:240],signals(raw[:240]))
    def test_continuity_and_unknown_start(self):
        raw=[dict(date=str(i),open=100,close=100) for i in range(226)]
        seq=iter(['A','B',None,'A','A','A',None])
        with patch('timing.strategy.classify',side_effect=lambda *a:dict(kind=next(seq),trend=True,near=False,conflict=False)):
            out=signals(raw)[219:]
        self.assertEqual([x['consecutive'] for x in out],[1,2,0,1,2,3,0])
        self.assertIsNone(out[0]['first_date']);self.assertFalse(out[1]['start_known'])
        self.assertEqual(out[3]['first_date'],'222')
    def test_signal_conflict_does_not_cancel_and_gap_fill(self):
        rows=[row(0,101,100,'A',90),row(1,98,95,None,100),row(2,100,96,None,90),row(3,97,80)]
        run=simulate(rows)
        t=run['trades'][0]
        self.assertEqual(t['entry_price'],95);self.assertEqual(t['entry_date'],rows[1]['date'])
        # Entry close +3.15% triggers profit, next open 96 rather than threshold.
        self.assertEqual(t['exit_price'],96)
        rows[1]=row(1,94,95,None,100)
        run=simulate(rows);self.assertEqual(run['trades'][0]['exit_price'],80)
    def test_exit_boundaries_close_only_and_reasons(self):
        self.assertEqual(exit_tags(row(0,102.5,ma5=90),100),['profit','ma5'])
        self.assertEqual(exit_tags(row(0,85,ma5=80),100),['stop','ma5'])
        self.assertEqual(exit_tags(row(0,100,ma5=100),100),[])
        rows=[row(0,kind='A')]+[row(i,100) for i in range(1,5)]
        self.assertEqual(simulate(rows)['trades'],[]) # highs/lows cross both, close does not
    def test_expiry_and_open_exit_priority(self):
        rows=[row(0,kind='A')]+[row(i) for i in range(1,23)]
        run=simulate(rows);t=run['trades'][0]
        self.assertEqual(t['exit_date'],rows[20]['date']);self.assertEqual(t['holding_days'],20)
        self.assertEqual(t['exit_session'],'close');self.assertEqual(t['primary'],'expiry')
        rows[19]=row(19,103)
        run=simulate(rows);self.assertEqual(run['trades'][0]['exit_session'],'open')
        self.assertEqual(run['trades'][0]['exit_date'],rows[20]['date'])
    def test_reentry_and_costs_and_terminal(self):
        rows=[row(0,kind='B'),row(1,103,100,'B'),row(2,100,120,'B'),row(3,100,100,'B')]
        for f in [0,.0005,.001]:
            run=simulate(rows,f);self.assertEqual(run['trades'][0]['exit_price'],120)
            self.assertAlmostEqual(run['trades'][0]['net_return'],1.2*(1-f)/(1+f)-1)
            self.assertEqual(run['orders'][2]['signal_date'],rows[2]['date'])
            self.assertEqual(run['open_position']['entry_date'],rows[3]['date'])
            self.assertTrue(all(e['cash']>=0 and e['quantity']>=0 for e in run['equity']))
            self.assertAlmostEqual(run['equity'][-1]['benchmark'],1/(1+f))
        self.assertEqual(simulate([row(0,kind='A')])['trades'],[])
        self.assertIsNone(simulate([row(0,kind='A')])['open_position'])
        self.assertIsNotNone(simulate([row(0,kind='A')])['pending_order'])
    def test_modes_and_no_addition_trend_exit(self):
        rows=[row(0,kind='B')]+[row(i,kind='B') for i in range(1,7)]
        self.assertEqual(simulate(rows,mode='A')['equity'][-1]['equity'],1)
        run=simulate(rows);self.assertEqual(len(run['orders']),1);self.assertEqual(run['trades'],[])
        self.assertIsNone(metrics(run)['win_rate'])

if __name__=='__main__':unittest.main()
