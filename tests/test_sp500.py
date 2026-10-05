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
            self.assertIn('低于均线多少后', page)
            self.assertNotIn('cdn.', page)
            self.assertTrue((out / 'echarts.min.js').is_file())
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
