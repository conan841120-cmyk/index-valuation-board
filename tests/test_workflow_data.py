"""Normal data controls and defensive validation of job handoff contracts."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools import workflow_data as transfer


class WorkflowData(unittest.TestCase):
    def setUp(self):
        # Keep this stage's scratch controls available for review.
        self.scratch = Path(tempfile.mkdtemp(prefix='b03-data-'))
        self.destination = self.scratch / 'checkout'
        self.destination.mkdir()
        self.bundle = self.scratch / 'bundle.json'

    def test_real_daily_and_macro_snapshots_round_trip_exactly(self):
        for kind in ('daily', 'macro'):
            transfer.pack(transfer.ROOT, kind, self.bundle)
            transfer.unpack(self.destination, kind, self.bundle)
            rows = json.loads(self.bundle.read_text())['files']
            self.assertTrue(rows)
            for row in rows:
                self.assertTrue(transfer.allowed(kind, row['path']))
                self.assertEqual((transfer.ROOT / row['path']).read_bytes(),
                                 (self.destination / row['path']).read_bytes())

    def test_empty_us_handoff_preserves_first_collection_waiting(self):
        transfer.pack(self.destination, 'us-market', self.bundle)
        transfer.unpack(self.destination, 'us-market', self.bundle)
        self.assertEqual(json.loads(self.bundle.read_text())['files'], [])

    def test_us_json_round_trip_preserves_chinese(self):
        path = self.destination / 'data/us_market/manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text('{"label":"正常控制","dates":[]}', encoding='utf-8')
        transfer.pack(self.destination, 'us-market', self.bundle)
        target = self.scratch / 'second'
        target.mkdir()
        transfer.unpack(target, 'us-market', self.bundle)
        self.assertEqual(path.read_bytes(), (target / 'data/us_market/manifest.json').read_bytes())

    def test_unlisted_or_duplicate_record_rejected_before_any_write(self):
        transfer.pack(transfer.ROOT, 'daily', self.bundle)
        original = json.loads(self.bundle.read_text())
        for extra in ({'path': 'notes.txt', 'base64': base64.b64encode(b'ordinary note').decode()},
                      original['files'][0]):
            value = dict(original, files=original['files'] + [extra])
            self.bundle.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                transfer.unpack(self.destination, 'daily', self.bundle)
            self.assertEqual(list(self.destination.iterdir()), [])

    def test_missing_file_wrong_identity_or_bad_encoding_is_rejected(self):
        transfer.pack(transfer.ROOT, 'macro', self.bundle)
        original = json.loads(self.bundle.read_text())
        variants = [dict(original, files=original['files'][1:]),
                    dict(original, kind='daily'),
                    dict(original, files=original['files'][:-1] + [dict(original['files'][-1], base64='bad encoding')])]
        for value in variants:
            self.bundle.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                transfer.unpack(self.destination, 'macro', self.bundle)
            self.assertEqual(list(self.destination.iterdir()), [])

    def test_linked_data_path_is_rejected_and_control_is_preserved(self):
        transfer.pack(transfer.ROOT, 'daily', self.bundle)
        target = self.scratch / 'ordinary-control.json'
        target.write_text('normal control')
        watch = self.destination / 'data/watch'
        watch.mkdir(parents=True)
        (watch / 'rule_check.json').symlink_to(target)
        with self.assertRaises(ValueError):
            transfer.unpack(self.destination, 'daily', self.bundle)
        self.assertEqual(target.read_text(), 'normal control')
        self.assertFalse((self.destination / 'data/series/raw_inputs.json').exists())

    def test_staging_is_an_explicit_file_list(self):
        transfer.pack(transfer.ROOT, 'daily', self.bundle)
        subprocess.run(['git', 'init', '--quiet'], cwd=self.destination, check=True)
        (self.destination / 'notes.txt').write_text('ordinary unrelated file')
        transfer.unpack(self.destination, 'daily', self.bundle, stage=True)
        names = [row['path'] for row in json.loads(self.bundle.read_text())['files']]
        staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'],
                                         cwd=self.destination).decode().rstrip('\0').split('\0')
        self.assertEqual(sorted(staged), sorted(names))
        self.assertNotIn('notes.txt', staged)

    def test_snapshot_date_must_be_real(self):
        self.assertTrue(transfer.allowed('daily', 'data/official_snapshots/indicator_000510_2026-10-11.xls'))
        self.assertFalse(transfer.allowed('daily', 'data/official_snapshots/indicator_000510_2026-02-30.xls'))
        self.assertTrue(transfer.allowed('us-market', 'data/us_market/2026-10-11.json'))
        self.assertFalse(transfer.allowed('us-market', 'data/us_market/2026-02-30.json'))
