import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from web import build_site, us_market


class USMarketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root / 'source'; self.source.mkdir()
        self.out = self.root / 'site'
        self.run = {'run_id': 'digest-20261002T100000-1234abcd', 'mode': 'digest', 'date': '2026-10-02',
                    'started_at': '2026-10-02T10:00:00+00:00', 'finished_at': '2026-10-02T10:01:00+00:00',
                    'data_status': 'partial', 'quotes': {}, 'sources': [],
                    'news': [{'title': '</script><script>alert(1)</script>', 'link': 'javascript:alert(1)', 'points': []}]}

    def fixture(self):
        (self.source / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'date_timezone': 'Asia/Shanghai', 'dates': ['2026-10-02']}))
        (self.source / '2026-10-02.json').write_text(json.dumps({'schema_version': 1, 'date': '2026-10-02', 'digest': [self.run], 'alerts': []}))

    def test_no_data_renders_explicit_waiting(self):
        page = us_market.build(self.source, self.out).read_text()
        self.assertIn('首次交接后', page)
        self.assertIn('"dates": []', page)
        self.assertTrue((self.out / 'data').is_dir())

    def test_script_payload_escape_and_markdown_link_safety(self):
        self.fixture(); page = us_market.build(self.source, self.out).read_text()
        self.assertNotIn('</script><script>alert(1)</script>', page)
        self.assertIn('\\u003c/script>', page)
        report = (self.out / 'reports' / (self.run['run_id'] + '.md')).read_text()
        self.assertNotIn('javascript:', report)
        self.assertIn('未取得核验正文', report)
        self.assertTrue((self.out / 'data/2026-10-02.json').exists())

    def test_invalid_dates_or_payload_fail_instead_of_empty_publish(self):
        self.fixture()
        manifest = json.loads((self.source / 'manifest.json').read_text())
        for date in ('../../secret', '2026-99-99'):
            manifest['dates'] = [date]
            (self.source / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): us_market.build(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_missing_day_aborts_publication(self):
        self.fixture(); (self.source / '2026-10-02.json').unlink()
        with self.assertRaises(FileNotFoundError): us_market.build(self.source, self.out)

    def test_cloud_config_is_embedded_and_invalid_config_aborts(self):
        self.fixture()
        manifest_path = self.source / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['watchlist'] = {'symbols': ['COST', 'BRK.B'], 'revision': 'a' * 64}
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn('"symbols": ["COST", "BRK.B"]', us_market.build(self.source, self.out).read_text())
        for bad in ({'symbols': ['<script>'], 'revision': 'a'*64}, {'symbols': [], 'revision': 'bad'}, {'symbols': 'COST', 'revision': 'a'*64}):
            manifest['watchlist'] = bad; manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): us_market.build(self.source, self.out)

    def test_complete_build_retains_valuation_macro_and_us_entry(self):
        # 实际渲染既有估值和宏观输入；US 使用测试数据目录。
        self.fixture()
        original = us_market.build
        with patch.object(us_market, 'build', side_effect=lambda source, out: original(self.source, out)):
            build_site.build(self.out)
        page = (self.out / 'index.html').read_text()
        self.assertIn('window.DASHBOARD', page)
        self.assertIn('window.HSI_MACRO', page)
        self.assertIn('us-market/', page)
        self.assertTrue((self.out / 'us-market/index.html').exists())
        self.assertTrue((self.out / 'sp500-deviation/index.html').exists())
        self.assertIn('sp500-deviation/', page)
        self.assertTrue((self.out / '.nojekyll').exists())
