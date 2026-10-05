"""真实本地 Git 分支验证跨仓库数据读取，不调用云端接口。"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.load_us_market import load


class PublicBranchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.origin = base / 'origin.git'; self.writer = base / 'writer'; self.reader = base / 'reader'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.origin)], check=True)
        self.writer.mkdir()
        self.git(self.writer, 'init', '-q', '-b', 'main')
        self.git(self.writer, 'config', 'user.name', 'test')
        self.git(self.writer, 'config', 'user.email', 'test@example.invalid')
        (self.writer / 'seed').write_text('public code')
        self.git(self.writer, 'add', 'seed'); self.git(self.writer, 'commit', '-qm', 'main')
        self.git(self.writer, 'remote', 'add', 'origin', str(self.origin))
        self.git(self.writer, 'push', '-q', 'origin', 'main')
        subprocess.run(['git', 'clone', '-q', '-b', 'main', str(self.origin), str(self.reader)], check=True)

    def git(self, root, *args):
        return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)

    def publish(self, dates=('2026-10-02',), sp500=None):
        self.git(self.writer, 'switch', '-qc', 'us-market-data')
        data = self.writer / 'data/us_market'; data.mkdir(parents=True)
        (data / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'date_timezone': 'Asia/Shanghai', 'dates': list(dates)}))
        (data / '2026-10-02.json').write_text(json.dumps({'schema_version': 1, 'date': '2026-10-02', 'digest': [], 'alerts': []}))
        if sp500 is not None:
            (data / 'sp500.json').write_text(json.dumps(sp500))
        (self.writer / 'do-not-execute.py').write_text('raise AssertionError("untrusted data-branch code")')
        self.git(self.writer, 'add', '.'); self.git(self.writer, 'commit', '-qm', 'public data')
        self.git(self.writer, 'push', '-q', 'origin', 'us-market-data')

    def test_absent_branch_is_explicit_initial_state(self):
        load(self.reader)
        self.assertFalse((self.reader / 'data/us_market').exists())

    def test_only_manifest_dates_are_read_without_switching_code(self):
        self.publish(); load(self.reader)
        self.assertEqual(json.loads((self.reader / 'data/us_market/manifest.json').read_text())['dates'], ['2026-10-02'])
        self.assertFalse((self.reader / 'do-not-execute.py').exists())
        self.assertEqual(self.git(self.reader, 'branch', '--show-current').stdout.strip(), b'main')

    def test_path_traversal_is_rejected_before_writing(self):
        self.publish(dates=('../../secret',))
        with self.assertRaises(ValueError): load(self.reader)
        self.assertFalse((self.reader / 'data/us_market').exists())

    def test_missing_referenced_day_aborts_instead_of_hiding_failure(self):
        self.publish(dates=('2026-10-01',))
        with self.assertRaises(subprocess.CalledProcessError): load(self.reader)
        self.assertFalse((self.reader / 'data/us_market').exists())

    def test_optional_sp500_data_is_read_without_branch_code(self):
        payload = {'schema_version': 1, 'symbol': '^GSPC', 'queries': {}}
        self.publish(sp500=payload); load(self.reader)
        self.assertEqual(json.loads((self.reader / 'data/us_market/sp500.json').read_text()), payload)
        self.assertFalse((self.reader / 'do-not-execute.py').exists())

    def test_wrong_sp500_identity_aborts_before_any_output(self):
        self.publish(sp500={'schema_version': 1, 'symbol': 'SPY'})
        with self.assertRaises(ValueError): load(self.reader)
        self.assertFalse((self.reader / 'data/us_market').exists())
