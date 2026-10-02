from datetime import date
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from web.render import current_macro_monitor

ROOT = Path(__file__).resolve().parents[1]


class MacroRenderCalendar(unittest.TestCase):
    def test_render_updates_rounds_without_network_or_saved_state_mutation(self):
        path = ROOT / 'data/hsi_macro_monitor.json'
        original = path.read_bytes()
        previous = json.loads(original)
        with patch('socket.create_connection', side_effect=AssertionError('No network when rendering')):
            before = current_macro_monitor(previous, date(2026, 10, 7))
            after = current_macro_monitor(previous, date(2026, 10, 8))
        ppi_before = next(s for s in before['sources'] if s['dataset'] == 'ppi')
        ppi_after = next(s for s in after['sources'] if s['dataset'] == 'ppi')
        self.assertEqual(ppi_before['current_round']['window_start'], '2026-09-08')
        self.assertEqual(ppi_before['next_round']['window_start'], '2026-10-08')
        self.assertEqual(ppi_after['current_round']['window_start'], '2026-10-08')
        self.assertEqual(ppi_after['next_round']['window_start'], '2026-11-08')
        self.assertEqual(ppi_after['current_round']['status'], 'awaiting')
        self.assertEqual(path.read_bytes(), original)
