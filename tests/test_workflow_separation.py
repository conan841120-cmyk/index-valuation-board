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
        plan = next(s for s in config['jobs']['collect']['steps'] if s.get('id') == 'plan')
        self.assertIn('--plan', plan['run'])
        gate = next(s for s in config['jobs']['collect']['steps'] if s.get('id') == 'monitor')
        self.assertEqual(gate['if'], "steps.plan.outputs.needs_check == 'true'")

    def test_shared_publish_lock_and_latest_branch(self):
        configs = [yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader) for name in ('daily.yml', 'macro.yml', 'us-market.yml')]
        self.assertEqual(configs[0]['concurrency'], configs[1]['concurrency'])
        self.assertEqual(configs[0]['concurrency'], configs[2]['concurrency'])
        self.assertEqual(configs[0]['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(configs[0]['concurrency']['queue'], 'max')
        for config in configs:
            resolver = config['jobs']['resolve']
            self.assertEqual(resolver['steps'][0]['with']['ref'], "${{ github.event_name == 'workflow_dispatch' && github.ref || 'main' }}")
            self.assertEqual(resolver['outputs']['code_ref'], '${{ steps.code.outputs.sha }}')
            self.assertIn('git rev-parse HEAD', resolver['steps'][1]['run'])
            self.assertEqual(len(resolver['steps']), 2)
            for job in ('collect', 'build'):
                checkout = config['jobs'][job]['steps'][0]
                self.assertEqual(checkout['with']['ref'], '${{ needs.resolve.outputs.code_ref }}')

    def test_all_publishers_build_the_complete_site(self):
        for name in ('daily.yml', 'macro.yml', 'us-market.yml'):
            text = (ROOT / '.github/workflows' / name).read_text()
            self.assertRegex(text, r'python3? tools/load_us_market.py')
            self.assertIn('python web/build_site.py', text)
            self.assertNotIn('web/render.py --out docs/index.html', text)
        config = yaml.load((ROOT / '.github/workflows/us-market.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(config['permissions']['contents'], 'read')

    def test_data_branch_signals_main_without_deploying(self):
        config = yaml.load((ROOT / '.github/workflows/us-market.yml').read_text(), Loader=yaml.BaseLoader)
        relay = yaml.load((ROOT / '.github/workflows/us-market-data.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(relay['on']['push']['branches'], ['us-market-data'])
        self.assertEqual(relay['permissions'], {'contents': 'read'})
        self.assertNotIn('actions/checkout', str(relay['jobs']))
        self.assertNotIn('deploy', relay['jobs'])
        self.assertNotIn('push', config['on'])
        self.assertEqual(config['on']['workflow_run'], {'workflows': [relay['name']], 'types': ['completed'], 'branches': ['us-market-data']})
        self.assertIn("github.event.workflow_run.conclusion == 'success'", config['jobs']['resolve']['if'])
        self.assertEqual(config['jobs']['collect']['steps'][0]['with']['ref'], '${{ needs.resolve.outputs.code_ref }}')

    def test_alarm_happens_after_page_is_published(self):
        config = yaml.load((ROOT / '.github/workflows/macro.yml').read_text(), Loader=yaml.BaseLoader)
        steps = config['jobs']['deploy']['steps']
        self.assertEqual(steps[0]['uses'], 'actions/deploy-pages@v4')
        self.assertEqual(steps[1]['if'], "needs.collect.outputs.new_alarm == 'true'")
        self.assertIn('exit 1', steps[1]['run'])

    def test_parsers_have_only_read_permissions_and_no_persisted_credentials(self):
        for name in ('daily.yml', 'macro.yml', 'us-market.yml'):
            config = yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)
            self.assertEqual(config['permissions'], {'contents': 'read'})
            for job_name in ('resolve', 'collect', 'build'):
                job = config['jobs'][job_name]
                self.assertEqual(job.get('permissions', config['permissions']), {'contents': 'read'})
                self.assertNotIn('environment', job)
                self.assertNotIn('secrets.', str(job))
            for job in config['jobs'].values():
                for step in job['steps']:
                    if step.get('uses', '').startswith('actions/checkout@'):
                        self.assertEqual(step['with']['persist-credentials'], 'false')
            self.assertEqual(config['jobs']['deploy']['permissions'], {'pages': 'write', 'id-token': 'write'})
            self.assertIn("github.ref == 'refs/heads/main'", config['jobs']['deploy']['if'])
            self.assertFalse(any('checkout' in step.get('uses', '') for step in config['jobs']['deploy']['steps']))

    def test_data_is_validated_before_build_and_write_jobs_never_build(self):
        for name, kind in (('daily.yml', 'daily'), ('macro.yml', 'macro'), ('us-market.yml', 'us-market')):
            text = (ROOT / '.github/workflows' / name).read_text()
            config = yaml.load(text, Loader=yaml.BaseLoader)
            build = config['jobs']['build']
            self.assertEqual(build['needs'], ['resolve', 'collect'])
            download = build['steps'][1]
            self.assertEqual(download['with']['name'], kind + '-collected-data')
            self.assertEqual(download['with']['path'], '${{ runner.temp }}/collected')
            self.assertIn('workflow_data.py unpack ' + kind, build['steps'][2]['run'])
            self.assertNotIn('always()', text)
            self.assertNotIn('failure()', text)
            self.assertNotIn('git add -A', text)
            if kind != 'us-market':
                commit = config['jobs']['commit']
                self.assertEqual(commit['permissions'], {'contents': 'write'})
                self.assertIn('build', commit['needs'])
                self.assertIn('commit', config['jobs']['deploy']['needs'])
                self.assertIn("github.ref == 'refs/heads/main'", commit['if'])
                self.assertEqual(commit['steps'][0]['with']['ref'], '${{ needs.resolve.outputs.code_ref }}')
                self.assertEqual(commit['steps'][1]['with']['name'], kind + '-validated-data')
                self.assertEqual(commit['steps'][1]['with']['path'], '${{ runner.temp }}/validated')
                self.assertIn('--stage', commit['steps'][2]['run'])
                self.assertNotIn('pip install', str(commit))
                self.assertNotIn('compute/', str(commit))
                self.assertNotIn('web/', str(commit))
                self.assertNotIn('env', commit['steps'][2])
                self.assertEqual(commit['steps'][3]['env'], {'PUBLISH_TOKEN': '${{ github.token }}'})
                self.assertIn('git ls-remote origin refs/heads/main', commit['steps'][3]['run'])
