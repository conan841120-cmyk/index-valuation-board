import copy
import json
from pathlib import Path
import tempfile
import unittest

from web import sp500
from web.navigation import navigation


class SP500PageTests(unittest.TestCase):
    def test_standalone_build_has_three_local_entries_and_only_bundled_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'sp500-deviation'
            page = sp500.build(Path(temporary) / 'missing.json', out).read_text()
            for href in ('../', '../us-market/', '../sp500-deviation/'):
                self.assertIn('href="' + href + '"', page)
            self.assertIn('aria-current="page"', page)
            self.assertIn('id="sp500-app"', page)
            self.assertNotIn('cdn.', page)
            self.assertTrue((out / 'sp500.js').is_file())
            data = json.loads((out / 'snapshot.json').read_text())
            self.assertEqual(sum(len(q['rows']) for q in data['queries'].values()), 20837)

    def test_bad_dates_or_identity_stop_publication(self):
        value = json.loads((sp500.ROOT / 'data/sp500/bootstrap.json').read_text())
        for change in ('order', 'end', 'symbol'):
            data = copy.deepcopy(value)
            if change == 'order': data['queries']['daily']['rows'][1]['date'] = data['queries']['daily']['rows'][0]['date']
            if change == 'end': data['research']['data_end'] = '2099-01-01'
            if change == 'symbol': data['symbol'] = 'SPY'
            with self.assertRaises(ValueError): sp500.validate(data)

    def test_navigation_relative_paths_are_correct_for_all_three_pages(self):
        self.assertIn('href="./"', navigation('valuation'))
        self.assertIn('href="us-market/"', navigation('valuation'))
        for current in ('us', 'sp500'):
            html = navigation(current)
            self.assertEqual(html.count('aria-current="page"'), 1)
            self.assertEqual(html.count('<a '), 3)

    def test_optional_timing_json_does_not_need_to_decode_during_build(self):
        from unittest.mock import patch
        root=Path(tempfile.mkdtemp(prefix='timing-optional-build-'))
        timing=root/'data/timing/latest.json';timing.parent.mkdir(parents=True);timing.write_bytes(b'{invalid-json-\xff')
        source=sp500.ROOT/'data/sp500/bootstrap.json'
        with patch.object(sp500,'ROOT',root):sp500.build(source,root/'site')
        self.assertEqual((root/'site/timing.json').read_bytes(),timing.read_bytes())
        self.assertIn('sp500-app',(root/'site/index.html').read_text())

    def test_unreadable_optional_timing_file_keeps_old_dashboard(self):
        from unittest.mock import patch
        root=Path(tempfile.mkdtemp(prefix='timing-unreadable-build-'))
        timing=root/'data/timing/latest.json';timing.parent.mkdir(parents=True);timing.write_text('{}')
        source=sp500.ROOT/'data/sp500/bootstrap.json';copyfile=sp500.shutil.copyfile
        def copy_optional(src,dst,*args,**kwargs):
            if Path(src)==timing:raise PermissionError('unreadable optional snapshot')
            return copyfile(src,dst,*args,**kwargs)
        with patch.object(sp500,'ROOT',root),patch.object(sp500.shutil,'copyfile',side_effect=copy_optional):sp500.build(source,root/'site')
        self.assertIn('error',json.loads((root/'site/timing.json').read_text()))
        self.assertTrue((root/'site/sp500.js').exists());self.assertTrue((root/'site/snapshot.json').exists())
