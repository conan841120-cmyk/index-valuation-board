import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from timing.data import freshness,ibkr_rows,validate_rows,calendar
from timing.update import update

UTC=dt.timezone.utc
class DataTests(unittest.TestCase):
    def test_calendar(self):
        for now,expected in [('2026-11-15T12:00:00+00:00','2026-11-13'),('2026-11-26T23:00:00+00:00','2026-11-25'),('2026-11-27T18:01:00+00:00','2026-11-27'),('2026-11-27T17:59:00+00:00','2026-11-25'),('2026-07-03T23:00:00+00:00','2026-07-02'),('2026-03-09T20:01:00+00:00','2026-03-09'),('2026-11-09T20:59:00+00:00','2026-11-06')]:
            self.assertEqual(freshness(dt.datetime.fromisoformat(now))['expected_date'],expected)
    def test_bad_and_missing_data(self):
        now=dt.datetime(2026,11,14,tzinfo=UTC)
        rows=[dict(date=d,open=100,close=101,high=102,low=99) for d in ['2026-11-11','2026-11-12','2026-11-13']]
        self.assertEqual(len(validate_rows(rows,now)),3)
        for data in [rows+rows[-1:],rows[::2],[dict(rows[0],open=0)],[dict(rows[0],close=float('nan'))],[dict(rows[0],date='2026-11-14')]]:
            with self.assertRaises(ValueError):validate_rows(data,now)
    def test_failure_isolation_and_success_time(self):
        now=dt.datetime(2026,11,14,12,tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/'latest.json'
            previous=dict(indices={'ndx':dict(latest=dict(date='2026-11-12'),successful_at='old-success')})
            dest.write_text(json.dumps(previous))
            rows=[dict(date=d.date().isoformat(),open=100+i,close=100+i,high=101+i,low=99+i) for i,d in enumerate(calendar('2025-11-13','2026-11-13').index)]
            response=Mock(content=b'fixture-only');response.json.return_value=dict(symbol='SPX',instrument_type='price_index',rows=rows)
            with patch.dict('os.environ',{'TIMING_SPX_URL':'https://example.com/spx','TIMING_PUBLIC_DISPLAY_LICENSED':'true'},clear=True),patch('timing.update.requests.get',return_value=response):
                result=update(dest,now)
            self.assertIsNone(result['indices']['sp500']['error'])
            self.assertEqual(len(result['indices']['sp500']['history']['rows']),len(rows))
            self.assertEqual(result['indices']['ndx']['successful_at'],'old-success')
            self.assertEqual(result['indices']['ndx']['latest']['date'],'2026-11-12')
            self.assertIsNotNone(result['indices']['ndx']['error'])
    def test_no_fake_empty_success(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{},clear=True):
            result=update(Path(directory)/'latest.json',dt.datetime(2026,11,14,tzinfo=UTC))
        self.assertTrue(all('successful_at' not in x and 'latest' not in x for x in result['indices'].values()))

class TransferTests(unittest.TestCase):
    def test_timing_whitelist(self):
        from tools.workflow_data import allowed, require_files, pack, unpack
        self.assertTrue(allowed('timing','data/timing/latest.json'))
        for path in ['web/sp500.js','../latest.json','data/timing/other.json']:
            self.assertFalse(allowed('timing',path))
        with self.assertRaises(ValueError):require_files('timing',set())
        # Retain temporary evidence rather than deleting files.
        root=Path(tempfile.mkdtemp(prefix='timing-transfer-'))
        (root/'data/timing').mkdir(parents=True);(root/'data/timing/latest.json').write_text('{"indices":{}}')
        bundle=root/'bundle.json';pack(root,'timing',bundle)
        dest=root/'other';dest.mkdir();unpack(dest,'timing',bundle)
        self.assertEqual((dest/'data/timing/latest.json').read_text(),'{"indices":{}}')

    def test_timing_snapshot_can_be_staged_and_recovered_after_checkout(self):
        import subprocess
        from tools.workflow_data import pack, unpack
        root=Path(tempfile.mkdtemp(prefix='timing-git-transfer-'))
        subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'.gitignore').write_text('data/timing/\n')
        source=root/'data/timing/latest.json';source.parent.mkdir(parents=True)
        source.write_text('{"indices":{"ndx":{"successful_at":"original-success","latest":{"date":"2026-11-12"}}}}')
        bundle=root/'bundle.json';pack(root,'timing',bundle)
        unpack(root,'timing',bundle,stage=True)
        staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=root,text=True)
        self.assertEqual(staged.strip(),'data/timing/latest.json')
        persisted=json.loads(subprocess.check_output(['git','show',':data/timing/latest.json'],cwd=root,text=True))
        self.assertEqual(persisted['indices']['ndx']['successful_at'],'original-success')
        subprocess.run(['git','-c','user.name=Timing test','-c','user.email=timing-test@example.invalid','commit','-qm','Persist timing snapshot'],cwd=root,check=True)
        checkout=root/'next-checkout'
        subprocess.run(['git','clone','-q','--no-hardlinks',str(root),str(checkout)],check=True)
        with patch.dict('os.environ',{},clear=True):
            restored=update(checkout/'data/timing/latest.json',dt.datetime(2026,11,14,12,tzinfo=UTC))
        self.assertEqual(restored['indices']['ndx']['successful_at'],'original-success')
        self.assertEqual(restored['indices']['ndx']['latest']['date'],'2026-11-12')
        self.assertIsNotNone(restored['indices']['ndx']['error'])
