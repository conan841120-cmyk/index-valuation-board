"""故障回归：无网络，候选数据验证失败必须保留旧缓存。"""
import copy
import json
import os
import tempfile
import unittest
from unittest import mock

from compute import run_all


class TestFetchFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'raw_inputs.json')
        self.cfg = {'key': 'test', 'name': '测试', 'metric': 'pe',
                    'sources': {'csindex': '001'}}
        self.old = {'test': {'csindex_perf': [{'date': '2026-09-28', 'close': 100,
                                              'pe_official': 12}],
                             'official': [{'date': '2026-09-28', 'pe1': 12}],
                             '_status': {'csindex_perf': {'ok': True, 'at': 'old-time'}}}}
        self.good_official = [{'date': '2026-09-29', 'pe1': 13}]

    def fetch(self, previous, perf, official=None):
        with mock.patch.object(run_all, 'INDICES', [self.cfg]), \
             mock.patch.object(run_all, 'SERIES', self.tmp.name), \
             mock.patch.object(run_all, 'RAW_INPUTS', self.path), \
             mock.patch.object(run_all.fetch_csindex, 'fetch_perf', return_value=perf), \
             mock.patch.object(run_all.fetch_csindex, 'fetch_indicator', return_value=official or self.good_official):
            return run_all.fetch_all(previous)

    def test_empty_business_error_and_invalid_values_preserve_previous(self):
        candidates = [[], {'error_code': 403},
                      [{'date': 'bad-date', 'close': 100, 'pe_official': 12}],
                      [{'date': '2026-09-29', 'close': float('nan'), 'pe_official': 12}],
                      [{'date': '2026-09-29', 'close': 100, 'pe_official': None}]]
        original = copy.deepcopy(self.old)
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                out = self.fetch(self.old, candidate)
                self.assertEqual(out['test']['csindex_perf'], self.old['test']['csindex_perf'])
                status = out['test']['_status']['csindex_perf']
                self.assertFalse(status['ok'])
                self.assertTrue(status['fallback'])
                self.assertEqual(status['last_success_at'], 'old-time')
                self.assertEqual(status['last_data_date'], '2026-09-28')
                self.assertTrue(status['at'].endswith('+08:00'))
                self.assertTrue(status['detail'])
                self.assertEqual(out['test']['official'], self.good_official)
        self.assertEqual(self.old, original)

    def test_valid_result_replaces_cache_and_records_success(self):
        perf = [{'date': '2026-09-29', 'close': 101, 'pe_official': 13}]
        out = self.fetch(self.old, perf)
        self.assertEqual(out['test']['csindex_perf'], perf)
        status = out['test']['_status']['csindex_perf']
        self.assertTrue(status['ok'])
        self.assertFalse(status['fallback'])
        self.assertEqual(status['at'], status['last_success_at'])
        self.assertEqual(status['last_data_date'], '2026-09-29')
        with open(self.path) as fh:
            self.assertEqual(json.load(fh), out)

    def test_no_previous_is_explicitly_not_fallback(self):
        out = self.fetch({}, [])
        status = out['test']['_status']['csindex_perf']
        self.assertFalse(status['ok'])
        self.assertFalse(status['fallback'])
        self.assertIsNone(status['last_data_date'])
        self.assertNotIn('csindex_perf', out['test'])

    def test_tencent_pair_stays_old_when_second_request_fails(self):
        self.cfg['sources'] = {'tencent': 'test'}
        old = {'test': {'tencent_week': [{'date': '2026-09-28', 'close': 100}],
                        'tencent_day': [{'date': '2026-09-28', 'close': 101}]}}
        for second in (RuntimeError('timeout'), []):
            with self.subTest(second=second), \
                 mock.patch.object(run_all, 'INDICES', [self.cfg]), \
                 mock.patch.object(run_all, 'SERIES', self.tmp.name), \
                 mock.patch.object(run_all, 'RAW_INPUTS', self.path), \
                 mock.patch.object(run_all.fetch_tencent, 'fetch_kline',
                                   side_effect=[[{'date': '2026-09-29', 'close': 102}], second]):
                out = run_all.fetch_all(old)
            self.assertEqual(out['test']['tencent_week'], old['test']['tencent_week'])
            self.assertEqual(out['test']['tencent_day'], old['test']['tencent_day'])
            self.assertFalse(out['test']['_status']['tencent']['ok'])
            self.assertTrue(out['test']['_status']['tencent']['fallback'])

    def test_danjuan_partial_history_cannot_replace_cache(self):
        self.cfg['sources'] = {'danjuan': 'test'}
        good = {'current': {'pe': 12, 'pb': 2, 'dy': 1, 'date': '09-28'},
                'pe': [['2026-09-28', 12]], 'pb': [['2026-09-28', 2]]}
        invalid = copy.deepcopy(good)
        invalid['pb'] = []
        old = {'test': {'danjuan': good}}
        with mock.patch.object(run_all, 'INDICES', [self.cfg]), \
             mock.patch.object(run_all, 'SERIES', self.tmp.name), \
             mock.patch.object(run_all, 'RAW_INPUTS', self.path), \
             mock.patch.object(run_all.fetch_danjuan, 'fetch_index', return_value=invalid):
            out = run_all.fetch_all(old)
        self.assertEqual(out['test']['danjuan'], good)
        self.assertFalse(out['test']['_status']['danjuan']['ok'])

    def test_failed_atomic_replace_keeps_file_and_removes_temporary(self):
        original = json.dumps(self.old)
        with open(self.path, 'w') as fh:
            fh.write(original)
        with mock.patch.object(run_all.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.fetch(self.old, [])
        with open(self.path) as fh:
            self.assertEqual(fh.read(), original)
        self.assertEqual(os.listdir(self.tmp.name), ['raw_inputs.json'])


if __name__ == '__main__':
    unittest.main()
