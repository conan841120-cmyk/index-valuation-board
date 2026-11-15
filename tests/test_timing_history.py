import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from timing.history import history_payload,preview,FIELDS
from timing.strategy import signals
from timing.data import calendar

BASE=Path(__file__).resolve().parents[1]/'research/timing-v1'
class HistoryAdapterTests(unittest.TestCase):
    def test_warmup_is_unknown_and_export_does_not_slice_before_calculation(self):
        dates=[d.date().isoformat() for d in calendar('2020-01-01','2022-01-01').index][:240]
        rows=[dict(date=d,open=100+i,close=100+i,high=101+i,low=99+i) for i,d in enumerate(dates)]
        series=signals(rows);history=history_payload(series,'SPX','Synthetic test fixture only','a'*64,'2026-11-15T00:00:00Z')
        self.assertFalse(history['rows'][218]['eligible']);self.assertIsNone(history['rows'][218]['kind'])
        self.assertIsNone(history['rows'][218]['ma200']);self.assertTrue(history['rows'][219]['eligible'])
        self.assertEqual(history['rows'][219]['ma200'],sum(range(120,320))/200)
        self.assertEqual(history['sessions'],dates)

    @unittest.skipUnless((BASE/'private-input/sp500.json').exists(),'Local licensed historical data required')
    def test_export_matches_every_backtest_signal_and_preserves_frozen_files(self):
        out=Path(tempfile.mkdtemp(prefix='timing-history-preview-'))/'timing.json'
        protected=[BASE/'freeze.json',BASE/'data-manifest.json',*sorted((BASE/'private-input').glob('*.json'))]
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        data=preview(BASE,out);counts={}
        for key,item in data['indices'].items():
            with (BASE/'results'/f'{key}-signals.csv').open() as f: expected=list(csv.DictReader(f))
            actual=item['history']['rows'];self.assertEqual(len(expected),len(actual))
            for a,b in zip(actual,expected):
                for f in FIELDS:self.assertEqual('' if a[f] is None else str(a[f]),b.get(f,''),(key,a['date'],f))
            signal_dates={r['date'] for r in actual if r['eligible'] and r['kind']}
            with (BASE/'results'/f'{key}-longest-AB-0.0000-trades.csv').open() as f: trades=list(csv.DictReader(f))
            self.assertTrue(signal_dates-{r['signal_date'] for r in trades})
            counts[key]=len(signal_dates)
        self.assertEqual(counts,{'sp500':40,'ndx':36})
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})
