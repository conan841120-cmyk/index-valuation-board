"""Exercise the real frozen runner using copies; never write the delivered baseline."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from timing.backtest import REPO, run, initialize

BASE=REPO/'research/timing-v1'

@unittest.skipUnless(all((BASE/'private-input'/f'{key}.json').exists() for key in ['sp500','ndx']), 'Local licensed inputs required; never replace them with public or synthetic market data')
class FrozenReplayTests(unittest.TestCase):
    def copy_version(self):
        root=Path(tempfile.mkdtemp(prefix='timing-frozen-test-'))/'version'
        (root/'private-input').mkdir(parents=True)
        for name in ['freeze.json','data-manifest.json']:shutil.copyfile(BASE/name,root/name)
        for key in ['sp500','ndx']:shutil.copyfile(BASE/'private-input'/f'{key}.json',root/'private-input'/f'{key}.json')
        (root/'results').mkdir();(root/'results/existing.txt').write_text('preserve existing results')
        return root

    def digest_tree(self,root):
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

    def test_changed_either_input_rejected_without_any_writes(self):
        for key in ['sp500','ndx']:
            with self.subTest(index=key):
                root=self.copy_version();path=root/'private-input'/f'{key}.json'
                value=json.loads(path.read_text());value['close'][-1]+=1;path.write_text(json.dumps(value))
                before=self.digest_tree(root)
                with self.assertRaisesRegex(ValueError,'Frozen input SHA256 mismatch: '+key):run(root,root/'new-output')
                self.assertEqual(before,self.digest_tree(root));self.assertFalse((root/'new-output').exists())

    def test_frozen_versions_identity_and_coverage_checked_before_output(self):
        for file,key,value in [('freeze.json','strategy','wrong-version'),('freeze.json','parameters',{}),('freeze.json','engine_sha256','bad'),('freeze.json','prd_sha256','bad'),('data-manifest.json','strategy','wrong-version')]:
            with self.subTest(field=key):
                root=self.copy_version();path=root/file;data=json.loads(path.read_text());data[key]=value;path.write_text(json.dumps(data))
                before=self.digest_tree(root)
                with self.assertRaises(ValueError):run(root,root/'new-output')
                self.assertEqual(before,self.digest_tree(root))
        for key,value in [('contract_id',416904),('sessions',999)]:
            root=self.copy_version();path=root/'data-manifest.json';data=json.loads(path.read_text());data['data']['ndx'][key]=value;path.write_text(json.dumps(data))
            before=self.digest_tree(root)
            with self.assertRaises(ValueError):run(root,root/'new-output')
            self.assertEqual(before,self.digest_tree(root))

    def test_same_inputs_all_36_runs_match_and_annotations_are_preserved(self):
        root=self.copy_version();before=self.digest_tree(root);output=root.parent/'replay'
        summary=run(root,output)
        self.assertEqual(len(summary),36);self.assertEqual(before,self.digest_tree(root))
        expected=[*sorted((BASE/'results').glob('*.csv')),BASE/'results/summary.json']
        for path in expected:
            with self.subTest(file=path.name):self.assertEqual(path.read_bytes(),(output/path.name).read_bytes())
        self.assertTrue(json.loads((root/'data-manifest.json').read_text())['data_quality']['corroboration_addendum'])
        with self.assertRaisesRegex(ValueError,'already exists'):run(root,output)

    def test_new_input_requires_separate_explicit_initialization(self):
        root=self.copy_version();before=self.digest_tree(root)
        source=root.parent/'new-input';shutil.copytree(root/'private-input',source)
        path=source/'sp500.json';data=json.loads(path.read_text());data['close'][-1]+=1;path.write_text(json.dumps(data))
        provenance=root.parent/'reviewed-provenance.json'
        metadata=json.loads((root/'data-manifest.json').read_text());metadata['data_quality']={'review_note':'New version fixture, not baseline evidence'};provenance.write_text(json.dumps(metadata))
        new=root.parent/'data-v2';initialize(new,source,provenance,root)
        self.assertEqual(before,self.digest_tree(root))
        manifest=json.loads((new/'data-manifest.json').read_text());self.assertEqual(manifest['data_version'],'data-v2')
        self.assertEqual(manifest['data_quality']['review_note'],'New version fixture, not baseline evidence')
        self.assertNotEqual(manifest['data']['sp500']['sha256'],metadata['data']['sp500']['sha256'])
        self.assertEqual(len(run(new,new.parent/'new-replay')),36)
        state=self.digest_tree(new)
        with self.assertRaisesRegex(ValueError,'already exists'):initialize(new,source,provenance,root)
        self.assertEqual(state,self.digest_tree(new))
