"""Publishing either section must preserve the other section's inputs."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowSeparation(unittest.TestCase):
    def test_daily_does_not_download_or_recalculate_macro(self):
        text = (ROOT / '.github/workflows/daily.yml').read_text()
        self.assertNotIn('macro/hsi/update.py', text)
        self.assertNotIn('python update.py', text)
        self.assertNotIn('release_watch.py', text)
        self.assertNotIn('hsi-official-raw-', text)
        self.assertIn('python compute/run_all.py', text)

    def test_macro_rebuilds_valuation_without_fetching(self):
        text = (ROOT / '.github/workflows/macro.yml').read_text()
        self.assertIn('python compute/run_all.py --rebuild', text)
        self.assertNotIn('python tools/watch_rule.py', text)
        config = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertEqual(config['on']['schedule'][0]['cron'], '30 10 * * *')
        plan = next(s for s in config['jobs']['build']['steps'] if s.get('id') == 'plan')
        self.assertIn('--plan', plan['run'])
        gate = next(s for s in config['jobs']['build']['steps'] if s.get('id') == 'monitor')
        self.assertEqual(gate['if'], "steps.plan.outputs.needs_check == 'true'")

    def test_shared_publish_lock_and_latest_branch(self):
        configs = [yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader) for name in ('daily.yml', 'macro.yml', 'us-market.yml')]
        self.assertEqual(configs[0]['concurrency'], configs[1]['concurrency'])
        self.assertEqual(configs[0]['concurrency'], configs[2]['concurrency'])
        self.assertEqual(configs[0]['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(configs[0]['concurrency']['queue'], 'max')
        for config in configs:
            checkout = config['jobs']['build']['steps'][0]
            self.assertEqual(checkout['with']['ref'], 'main')

    def test_all_publishers_build_the_complete_site(self):
        for name in ('daily.yml', 'macro.yml', 'us-market.yml'):
            text = (ROOT / '.github/workflows' / name).read_text()
            self.assertIn('python tools/load_us_market.py', text)
            self.assertIn('python web/build_site.py', text)
            self.assertNotIn('web/render.py --out docs/index.html', text)
        config = yaml.load((ROOT / '.github/workflows/us-market.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(config['on']['push']['branches'], ['us-market-data'])
        self.assertEqual(config['permissions']['contents'], 'read')

    def test_alarm_happens_after_page_is_published(self):
        config = yaml.load((ROOT / '.github/workflows/macro.yml').read_text(), Loader=yaml.BaseLoader)
        steps = config['jobs']['deploy']['steps']
        self.assertEqual(steps[0]['uses'], 'actions/deploy-pages@v4')
        self.assertEqual(steps[1]['if'], "needs.build.outputs.new_alarm == 'true'")
        self.assertIn('exit 1', steps[1]['run'])
