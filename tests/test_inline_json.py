from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from web.inline_json import inline_json
from web import render, build_drafts


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.count += 1


class InlineJSONTests(unittest.TestCase):
    text = '中文 <普通标签> & "引号" \\ 换行\n\u2028\u2029'

    def test_round_trip_and_html_boundary(self):
        value = {'title': self.text, 'rows': [None, True, 12.5]}
        encoded = inline_json(value)
        self.assertEqual(json.loads(encoded), value)
        self.assertIn('中文', encoded)
        for character in '<>&\u2028\u2029':
            self.assertNotIn(character, encoded)
        parser = Scripts()
        parser.feed('<script>window.DATA = ' + encoded + ';</script>')
        self.assertEqual(parser.count, 1)

    def test_nonfinite_numbers_are_rejected(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                inline_json({'nested': [value]})

    def test_dashboard_macro_and_drafts_use_shared_encoder(self):
        root = Path(tempfile.mkdtemp())
        dashboard = {'generated_at': '2026-10-11', 'default_window': 'all',
                     'windows': [], 'indices': [], 'rule_watch': {'title': self.text}}
        source = root / 'dashboard.json'
        source.write_text(json.dumps(dashboard), encoding='utf-8')
        calls = []
        def encode(value):
            calls.append(value)
            return inline_json(value)
        with patch.object(render, 'DASHBOARD_JSON', source), \
             patch.object(render, 'with_fresh_rule_watch', side_effect=lambda value: value), \
             patch.object(render, 'current_macro_monitor', return_value={'label': self.text}), \
             patch.object(render, 'inline_json', side_effect=encode):
            render.build(str(root / 'index.html'))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['rule_watch']['title'], self.text)
        self.assertEqual(calls[1]['monitor']['label'], self.text)
        html = (root / 'index.html').read_text()
        self.assertNotIn('<普通标签>', html)
        templates = root / 'templates'; templates.mkdir()
        for name, _ in build_drafts.DRAFTS:
            (templates / name).write_text('<script><!--DATA--></script>')
        with patch.object(build_drafts, 'DASHBOARD_JSON', source), \
             patch.object(build_drafts, 'SRC', str(templates)), \
             patch.object(build_drafts, 'DEMOS', str(root)), \
             patch.object(build_drafts, 'inline_json', wraps=inline_json) as encoder:
            build_drafts.main()
        encoder.assert_called_once()
        for name, _ in build_drafts.DRAFTS:
            page = (root / name).read_text()
            encoded = page.split('window.DASHBOARD = ', 1)[1].rsplit(';</script>', 1)[0]
            self.assertEqual(json.loads(encoded)['rule_watch']['title'], self.text)
            parser = Scripts(); parser.feed(page)
            self.assertEqual(parser.count, 1)
