"""已确认问题的回归：锚值日期、分红基数、独立官方历史和行情日期。"""
import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compute.build_dataset import build_index, rule_watch_payload
from compute.config import INDEX_BY_KEY
from compute.normalize import attach_level, to_weekly
from compute.provenance import input_digest, code_digest
from fetch.derive_yield import calibrate, current_date, derive, full_return
from fetch import fetch_csindex
import pandas as pd


class TestYieldIntegrity(unittest.TestCase):
    def yield_raw(self):
        end = datetime.date(2026, 9, 21)
        days = [end - datetime.timedelta(days=i) for i in range(420)][::-1]
        days = [d.isoformat() for d in days if d.weekday() < 5]
        return {'csindex_perf': [{'date':d,'close':100.0} for d in days],
                'csindex_tr': [{'date':d,'close':100.0 + i * 0.02} for i,d in enumerate(days)],
                'danjuan': {'fetched_at':'2026-09-29 06:00:00',
                            'current':{'date':'09-28','pe':8.0,'dy':4.42},
                            'pe':[['2026-09-14',8.0],['2026-09-21',8.1],['2026-09-28',8.0]]},
                'official': [{'date':'2026-09-21','dy1':4.2,'fetched_at':'2026-09-22'}]}

    def test_one_cash_dividend_uses_previous_price_and_exact_window(self):
        price = [{'date':'2026-09-01','value':100}, {'date':'2026-09-02','value':90}]
        total = [{'date':p['date'],'value':100} for p in price]
        rows = full_return(price, total, window=1)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['value'], 10 / 90 * 100)
        self.assertEqual(full_return(price[:1], total[:1], window=1), [])

    def test_calibration_requires_exact_observation_date(self):
        points = [{'date':'2026-09-21','value':4.0}]
        for target_date in (None, '2026-09-28', '2026-09-18'):
            self.assertEqual(calibrate(points, 4.42, 1825, target_date), points)
        self.assertEqual(calibrate(points, 4.42, 1825, '2026-09-21')[-1]['value'], 4.42)
        self.assertEqual(points[-1]['value'], 4.0)

    def test_month_day_needs_response_date_and_handles_new_year(self):
        self.assertEqual(current_date({'date':'2026-09-28'}), '2026-09-28')
        self.assertIsNone(current_date({'date':'09-28'}))
        self.assertEqual(current_date({'date':'12-31','fetched_at':'2027-01-02 08:00:00'}), '2026-12-31')
        self.assertIsNone(current_date({'date':'02-30','fetched_at':'2026-03-01'}))

    def test_new_anchor_is_not_written_to_older_terminal_week(self):
        raw = self.yield_raw()
        raw['csindex_tr'] = [r for r in raw['csindex_tr'] if r['date'] <= '2026-09-21']
        index = build_index(INDEX_BY_KEY['dividend_low_vol'], raw)
        self.assertEqual(index['data_date'], '2026-09-21')
        self.assertEqual(index['value_meta']['anchor_observation']['date'], '2026-09-28')
        self.assertFalse(index['value_meta']['calibration']['applied'])
        self.assertFalse(index['value_meta']['current_is_observed'])
        self.assertNotAlmostEqual(index['series'][-1]['value'], raw['danjuan']['current']['dy'])
        self.assertEqual(index['series'][-1]['kind'], 'derived')

    def test_missing_danjuan_uses_unanchored_return_and_keeps_official_separate(self):
        raw = self.yield_raw()
        rows, meta = derive(INDEX_BY_KEY['dividend_low_vol'], [],
            [{'date':r['date'],'value':r['close']} for r in raw['csindex_perf']],
            [{'date':r['date'],'value':r['close']} for r in raw['csindex_tr']],
            raw['official'], {})
        self.assertTrue(rows)
        self.assertEqual(meta['method'], 'full_return')
        self.assertIsNone(meta['anchor_observation'])
        self.assertFalse(meta['current_is_observed'])
        self.assertFalse(meta['calibration']['applied'])

    def test_accumulated_official_history_never_changes_main_estimator(self):
        raw = self.yield_raw()
        history = [{'date':'2026-09-18','dy1':4.1,'fetched_at':'2026-09-19'}]
        earlier = dict(history[0], date='2026-08-14', dy1=99.0)
        plain = build_index(INDEX_BY_KEY['dividend_low_vol'], raw)
        accumulated = build_index(INDEX_BY_KEY['dividend_low_vol'], raw, [earlier] + history)
        self.assertEqual(plain['series'], accumulated['series'])
        alternate = accumulated['alternates']['official_dy']
        self.assertEqual(alternate['series'][0]['date'], earlier['date'])
        self.assertEqual(alternate['series'][0]['value'], 99.0)
        self.assertEqual(alternate['flag'], 'real')
        self.assertEqual(alternate['source'], 'csindex')
        self.assertEqual(alternate['value_meta']['real_window_start'], earlier['date'])

    def test_us_long_window_has_prior_or_exact_levels(self):
        end = datetime.date(2026, 9, 25)
        weekly = [{'date':(end - datetime.timedelta(weeks=i)).isoformat(), 'close':100.0+i}
                  for i in range(600)][::-1]
        valuations = [[p['date'], 20.0+i/100] for i,p in enumerate(weekly[-512:])]
        for key in ('nasdaq100','sp500'):
            with self.subTest(key=key):
                raw = {'tencent_week':weekly, 'tencent_day':[dict(p,close=999.0) for p in weekly[-10:]],
                       'danjuan':{'pe':valuations}}
                index = build_index(INDEX_BY_KEY[key], raw)
                points = index['series'][index['views']['10Y']['start']:]
                self.assertEqual(len(points), 512)
                self.assertEqual(points[0]['level'], weekly[-512]['close'])
                self.assertEqual(points[-1]['level'], 999.0)
                for point in points:
                    self.assertIsNotNone(point['level'])
                    self.assertEqual(point['level_date'], point['date'])

    def test_weekly_order_and_level_join_do_not_look_forward(self):
        rows = [{'date':'2026-09-04','value':4}, {'date':'2026-09-01','value':1}]
        self.assertEqual(to_weekly(rows), rows[:1])
        joined = attach_level([{'date':'2026-09-04','value':1}], {'2026-09-01':100,'2026-09-05':200})
        self.assertEqual(joined[0]['level'], 100)
        self.assertEqual(joined[0]['level_date'], '2026-09-01')
        missing = attach_level([{'date':'2026-09-04','value':1}], {'2026-08-01':100,'2026-09-05':200})
        self.assertIsNone(missing[0]['level'])

    def test_projection_recomputes_unique_match_count(self):
        rows = [{'index_key':'nasdaq100','author_metric':'市盈率TTM','match':True}] * 5
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'check.json'
            path.write_text(json.dumps({'matched':5,'mismatched':0,'rows':rows}))
            result = rule_watch_payload(str(path))
        self.assertEqual(result['state'], 'incomplete')
        self.assertEqual(result['matched'], 0)

    def test_official_invalid_response_cannot_overwrite_cumulative_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / 'indicator_H30269.csv'
            csv.write_text('prior-valid-cache')
            frame = pd.DataFrame([['20260928',0,0,0,0,0,8,9,None,4]], columns=range(10))
            with patch.object(fetch_csindex,'SNAPSHOTS',tmp), \
                 patch.object(fetch_csindex,'fetch') as fetch, \
                 patch.object(fetch_csindex.pd,'read_excel',return_value=frame):
                fetch.return_value.content = b'invalid-candidate'
                with self.assertRaisesRegex(ValueError, '股息率1无效'):
                    fetch_csindex.fetch_indicator('H30269')
            self.assertEqual(csv.read_text(), 'prior-valid-cache')

    def test_fingerprint_changes_with_input_and_code_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('data/series/raw_inputs.json','compute/stats.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('before')
            a, b = input_digest(root), code_digest(root)
            (root / 'data/series/raw_inputs.json').write_text('after')
            self.assertNotEqual(input_digest(root), a)
            self.assertEqual(code_digest(root), b)
            (root / 'compute/stats.py').write_text('after')
            self.assertNotEqual(code_digest(root), b)


if __name__ == '__main__':
    unittest.main()
