"""Candidate acceptance regressions; synthetic sources and isolated business files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pandas as pd
from compute import run_all
from fetch import fetch_csindex


class CandidateFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.raw_path = self.root / 'raw_inputs.json'
        self.csv = self.root / 'indicator_001.csv'
        self.cfg = {'key': 'test', 'name': 'test', 'metric': 'pe', 'sources': {'csindex': '001'}}
        self.days = ['2026-10-01', '2026-10-02', '2026-10-08']
        self.perf = [{'date': d, 'close': 100, 'pe_official': 12} for d in self.days]
        self.official = [{'date': d, 'pe1': 12, 'pe2': 13, 'dy1': 2, 'dy2': 3,
                          'fetched_at': '2026-10-08 18:00:00'} for d in self.days]
        self.old = {'test': {'csindex_perf': self.perf, 'official': self.official}}
        self.raw_path.write_text(json.dumps(self.old))
        pd.DataFrame(self.official).to_csv(self.csv, index=False)
        self.csv_before = self.csv.read_bytes()
        for target, name, value in [(run_all, 'INDICES', [self.cfg]), (run_all, 'SERIES', str(self.root)),
                                    (run_all, 'RAW_INPUTS', str(self.raw_path)),
                                    (fetch_csindex, 'SNAPSHOTS', str(self.root))]:
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def fetch(self, perf=None, official=None):
        with mock.patch.object(fetch_csindex, 'fetch_perf', return_value=self.perf if perf is None else perf), \
             mock.patch.object(fetch_csindex, 'fetch_indicator', return_value=self.official if official is None else official):
            return run_all.fetch_all(self.old)

    def rejected(self, out, part):
        self.assertEqual(out['test'][part], self.old['test'][part])
        self.assertFalse(out['test']['_status'][part]['ok'])
        self.assertTrue(out['test']['_status'][part]['fallback'])

    def indicator_frame(self, missing_pe=False):
        return pd.DataFrame([[d.replace('-', ''), 0, 0, 0, 0, 0,
                              None if missing_pe else 14, 15, 2, 3] for d in self.days], columns=range(10))


class TestCandidateAcceptance(CandidateFixture):
    def test_old_valid_response_cannot_replace_recent_cache(self):
        out = self.fetch(perf=[dict(self.perf[0], date='2026-09-01')])
        self.rejected(out, 'csindex_perf')
        self.assertEqual(out['test']['_status']['csindex_perf']['last_data_date'], '2026-10-08')

    def test_full_history_cannot_lose_prefix_middle_or_tail(self):
        for missing in range(3):
            with self.subTest(missing=missing):
                candidate = [r for i, r in enumerate(self.perf) if i != missing]
                candidate.append(dict(self.perf[-1], date='2026-10-09'))
                self.rejected(self.fetch(perf=candidate), 'csindex_perf')

    def test_complete_history_extension_and_same_date_revision_are_accepted(self):
        for candidate in [self.perf + [dict(self.perf[-1], date='2026-10-09')],
                          [dict(r, close=101, pe_official=13) for r in self.perf]]:
            with self.subTest(candidate=candidate):
                out = self.fetch(perf=candidate)
                self.assertEqual(out['test']['csindex_perf'], candidate)
                self.assertTrue(out['test']['_status']['csindex_perf']['ok'])

    def test_real_adapter_missing_required_pe_does_not_pollute_csv(self):
        with mock.patch.object(fetch_csindex, 'fetch_perf', return_value=self.perf), \
             mock.patch.object(fetch_csindex, 'fetch') as fetch, \
             mock.patch.object(pd, 'read_excel', return_value=self.indicator_frame(missing_pe=True)):
            fetch.return_value.content = b'synthetic xls'
            out = run_all.fetch_all(self.old)
        self.rejected(out, 'official')
        self.assertEqual(self.csv.read_bytes(), self.csv_before)
        self.assertEqual(json.loads(self.raw_path.read_text())['test']['official'], self.official)

    def test_adapter_returns_candidate_without_committing_csv(self):
        with mock.patch.object(fetch_csindex, 'fetch') as fetch, \
             mock.patch.object(pd, 'read_excel', return_value=self.indicator_frame()):
            fetch.return_value.content = b'synthetic xls'
            candidate = fetch_csindex.fetch_indicator('001')
        self.assertEqual(len(candidate), 3)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_official_middle_gap_is_rejected_and_csv_stays_unchanged(self):
        candidate = [self.official[0], self.official[2], dict(self.official[-1], date='2026-10-09')]
        out = self.fetch(official=candidate)
        self.rejected(out, 'official')
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_official_window_rolls_without_losing_accumulated_history(self):
        candidate = self.official[1:] + [dict(self.official[-1], date='2026-10-09', pe1=14)]
        out = self.fetch(official=candidate)
        self.assertTrue(out['test']['_status']['official']['ok'])
        rows = fetch_csindex.load_indicator_csv('001')
        self.assertEqual([r['date'] for r in rows], self.days + ['2026-10-09'])
        self.assertEqual(rows[-1]['pe1'], 14)

    def test_official_shorter_window_and_same_end_prefix_loss_are_rejected(self):
        for candidate in [self.official[1:],
                          [self.official[-1], dict(self.official[-1], date='2026-10-09')]]:
            with self.subTest(candidate=candidate):
                self.rejected(self.fetch(official=candidate), 'official')
                self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_official_same_date_revision_updates_both_business_files(self):
        candidate = [dict(r, pe1=16) for r in self.official]
        out = self.fetch(official=candidate)
        self.assertEqual(out['test']['official'], candidate)
        self.assertEqual([r['pe1'] for r in fetch_csindex.load_indicator_csv('001')], [16] * 3)

    def test_danjuan_current_date_and_each_history_are_checked(self):
        self.cfg['sources'] = {'danjuan': 'test'}
        good = {'current': {'pe': 12, 'pb': 2, 'dy': 1, 'date': '10-08'},
                'pe': [[d, 12] for d in self.days], 'pb': [[d, 2] for d in self.days]}
        self.old['test']['danjuan'] = good
        candidates = [dict(copy.deepcopy(good), current=dict(good['current'], date='09-01')),
                      dict(copy.deepcopy(good), pb=good['pb'][:-1])]
        for candidate in candidates:
            with self.subTest(candidate=candidate), \
                 mock.patch.object(run_all.fetch_danjuan, 'fetch_index', return_value=candidate):
                self.rejected(run_all.fetch_all(self.old), 'danjuan')

    def test_tencent_pair_rejects_one_regression_and_middle_loss(self):
        self.cfg['sources'] = {'tencent': 'test'}
        self.old['test']['tencent_week'] = self.perf
        self.old['test']['tencent_day'] = self.perf
        fresh = self.perf + [dict(self.perf[-1], date='2026-10-09')]
        for day in [[dict(self.perf[0], date='2026-09-01')],
                    [self.perf[0], self.perf[2], fresh[-1]]]:
            with self.subTest(day=day), mock.patch.object(run_all.fetch_tencent, 'fetch_kline', side_effect=[fresh, day]):
                out = run_all.fetch_all(self.old)
            self.assertEqual(out['test']['tencent_week'], self.perf)
            self.assertEqual(out['test']['tencent_day'], self.perf)
            self.assertFalse(out['test']['_status']['tencent']['ok'])

    def test_tencent_rolling_window_can_drop_only_old_prefix(self):
        self.cfg['sources'] = {'tencent': 'test'}
        self.old['test']['tencent_week'] = self.perf
        self.old['test']['tencent_day'] = self.perf
        fresh = self.perf[1:] + [dict(self.perf[-1], date='2026-10-09')]
        with mock.patch.object(run_all.fetch_tencent, 'fetch_kline', side_effect=[fresh, fresh]):
            out = run_all.fetch_all(self.old)
        self.assertTrue(out['test']['_status']['tencent']['ok'])
        self.assertEqual(out['test']['tencent_day'], fresh)


    def test_current_date_supports_year_boundary_and_leap_day(self):
        for day, anchor, expected in [('01-02', '2026-12-31', '2027-01-02'),
                                     ('12-31', '2027-01-02', '2026-12-31'),
                                     ('02-29', '2028-02-29', '2028-02-29')]:
            with self.subTest(day=day):
                data = {'current': {'date': day}, 'pe': [[anchor, 12]], 'pb': [[anchor, 2]]}
                self.assertEqual(run_all._current_date(data), expected)

    def test_noncanonical_date_cannot_bypass_chronology(self):
        self.rejected(self.fetch(perf=[dict(self.perf[-1], date='2026-W01-1')]), 'csindex_perf')

    def test_accumulated_csv_blocks_regression_without_raw_official_window(self):
        self.old['test'].pop('official')
        candidate = [dict(self.official[-1], date='2026-09-01')]
        out = self.fetch(official=candidate)
        self.assertNotIn('official', out['test'])
        self.assertFalse(out['test']['_status']['official']['ok'])
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_weekly_unfinished_bar_date_revision_is_accepted(self):
        self.cfg['sources'] = {'tencent': 'test'}
        week = [{'date': d, 'close': 100} for d in ['2026-09-25', '2026-10-02', '2026-10-07']]
        revised = week[:-1] + [dict(week[-1], date='2026-10-09')]
        self.old['test'].update(tencent_week=week, tencent_day=self.perf)
        with mock.patch.object(run_all.fetch_tencent, 'fetch_kline', side_effect=[revised, self.perf]):
            out = run_all.fetch_all(self.old)
        self.assertTrue(out['test']['_status']['tencent']['ok'])
        self.assertEqual(out['test']['tencent_week'], revised)


class TestCacheCommitRecovery(CandidateFixture):
    def candidate(self):
        return [dict(r, pe1=16) for r in self.official]

    def test_json_serialization_failure_leaves_all_business_files_unchanged(self):
        raw_before = self.raw_path.read_bytes()
        self.old['test']['unused'] = float('nan')
        with self.assertRaises(ValueError):
            self.fetch(official=self.candidate())
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_csv_replace_failure_restores_both_files(self):
        self.inject_failure(self.csv)

    def test_raw_replace_failure_after_csv_replace_restores_both_files(self):
        self.inject_failure(self.raw_path)

    def test_intent_write_failure_leaves_business_files_unchanged(self):
        from compute import cache_commit
        raw_before = self.raw_path.read_bytes()
        with mock.patch.object(cache_commit, 'atomic_write', side_effect=OSError('intent failed')):
            with self.assertRaises(OSError):
                self.fetch(official=self.candidate())
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)
        self.assertFalse(cache_commit.journal_path(self.raw_path).exists())

    def test_multiple_official_csvs_are_restored_after_raw_failure(self):
        second = self.root / 'indicator_002.csv'
        second.write_bytes(self.csv_before)
        cfg = dict(self.cfg, key='second', sources={'csindex': '002'})
        self.old['second'] = copy.deepcopy(self.old['test'])
        self.raw_path.write_text(json.dumps(self.old))
        with mock.patch.object(run_all, 'INDICES', [self.cfg, cfg]):
            self.inject_failure(self.raw_path, [(second, self.csv_before)])
        # The retry inside inject_failure committed new data to both CSVs.
        self.assertEqual(second.read_bytes(), self.csv.read_bytes())

    def inject_failure(self, target, other_files=()):
        raw_before = self.raw_path.read_bytes()
        replace = run_all.os.replace
        fired = []
        def fail_once(source, destination):
            if Path(destination) == target and not fired:
                fired.append(True)
                raise OSError('injected replacement failure')
            return replace(source, destination)
        with mock.patch.object(run_all.os, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.fetch(official=self.candidate())
        self.assertTrue(fired)
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)
        for path, before in other_files:
            self.assertEqual(path.read_bytes(), before)
        self.assertFalse(run_all.recover_cache())
        out = self.fetch(official=self.candidate())
        self.assertTrue(out['test']['_status']['official']['ok'])

    def interrupt(self, target):
        replace = run_all.os.replace
        def stop(source, destination):
            if Path(destination) == target:
                raise SystemExit('injected process interruption')
            return replace(source, destination)
        with mock.patch.object(run_all.os, 'replace', side_effect=stop):
            with self.assertRaises(SystemExit):
                self.fetch(official=self.candidate())

    def test_interruption_after_csv_is_recovered_before_retry(self):
        raw_before = self.raw_path.read_bytes()
        self.interrupt(self.raw_path)
        self.assertNotEqual(self.csv.read_bytes(), self.csv_before)
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertTrue(run_all.recover_cache())
        self.assertEqual(self.csv.read_bytes(), self.csv_before)
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertFalse(run_all.recover_cache())
        out = self.fetch(official=self.candidate())
        self.assertTrue(out['test']['_status']['official']['ok'])

    def test_fetch_recovers_and_reloads_disk_instead_of_stale_argument(self):
        self.interrupt(self.raw_path)
        stale = {'test': {'official': [dict(self.official[0], date='2026-09-01')]}}
        with mock.patch.object(fetch_csindex, 'fetch_perf', side_effect=ValueError('offline')), \
             mock.patch.object(fetch_csindex, 'fetch_indicator', side_effect=ValueError('offline')):
            out = run_all.fetch_all(stale)
        self.assertEqual(out['test']['official'], self.official)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_recovery_can_resume_after_another_process_interruption(self):
        from compute import cache_commit
        raw_before = self.raw_path.read_bytes()
        self.interrupt(self.raw_path)
        with mock.patch.object(cache_commit, '_complete', side_effect=SystemExit('interrupted recovery')):
            with self.assertRaises(SystemExit):
                run_all.recover_cache()
        self.assertTrue(run_all.recover_cache())
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_interruption_after_all_targets_before_completion_rolls_back(self):
        from compute import cache_commit
        raw_before = self.raw_path.read_bytes()
        with mock.patch.object(cache_commit, '_complete', side_effect=SystemExit('interrupted')):
            with self.assertRaises(SystemExit):
                self.fetch(official=self.candidate())
        self.assertNotEqual(self.raw_path.read_bytes(), raw_before)
        self.assertTrue(run_all.recover_cache())
        self.assertEqual(self.raw_path.read_bytes(), raw_before)
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_rollback_failure_keeps_intent_for_later_recovery(self):
        from compute import cache_commit
        raw_before = self.raw_path.read_bytes()
        write = cache_commit.atomic_write
        def fail(path, data):
            if Path(path) == self.raw_path or (Path(path) == self.csv and data == self.csv_before):
                raise OSError('disk failure')
            return write(path, data)
        with mock.patch.object(cache_commit, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.fetch(official=self.candidate())
        self.assertNotEqual(self.csv.read_bytes(), self.csv_before)
        self.assertTrue(run_all.recover_cache())
        self.assertEqual(self.csv.read_bytes(), self.csv_before)
        self.assertEqual(self.raw_path.read_bytes(), raw_before)

    def test_recovery_refuses_third_party_change_before_restoring_any_file(self):
        self.interrupt(self.raw_path)
        changed_csv = self.csv.read_bytes()
        self.raw_path.write_text('third party data')
        with self.assertRaisesRegex(RuntimeError, 'third-party'):
            run_all.recover_cache()
        self.assertEqual(self.raw_path.read_text(), 'third party data')
        self.assertEqual(self.csv.read_bytes(), changed_csv)

    def test_recovery_refuses_unknown_journal_target(self):
        from compute import cache_commit
        self.interrupt(self.raw_path)
        path = cache_commit.journal_path(self.raw_path)
        intent = json.loads(path.read_text())
        intent['files'][0]['path'] = str(self.root / 'unrelated.csv')
        path.write_text(json.dumps(intent))
        with self.assertRaisesRegex(ValueError, 'outside accepted outputs'):
            run_all.recover_cache()
        self.assertFalse((self.root / 'unrelated.csv').exists())

    def test_new_csv_created_before_interruption_is_removed_on_recovery(self):
        # New output paths are isolated in this temporary directory.
        self.cfg['sources'] = {'csindex': '002'}
        new_csv = self.root / 'indicator_002.csv'
        self.interrupt(self.raw_path)
        self.assertTrue(new_csv.exists())
        self.assertTrue(run_all.recover_cache())
        self.assertFalse(new_csv.exists())
        self.assertEqual(self.csv.read_bytes(), self.csv_before)

    def test_rebuild_recovers_before_loading_any_business_file(self):
        raw_before = self.raw_path.read_bytes()
        self.interrupt(self.raw_path)
        def build():
            self.assertEqual(self.raw_path.read_bytes(), raw_before)
            self.assertEqual(self.csv.read_bytes(), self.csv_before)
            return {'indices': []}
        with mock.patch('sys.argv', ['run_all.py', '--rebuild']), \
             mock.patch.object(run_all.build_dataset, 'main', side_effect=build) as rebuilt:
            run_all.main()
        rebuilt.assert_called_once()


if __name__ == '__main__':
    unittest.main()
