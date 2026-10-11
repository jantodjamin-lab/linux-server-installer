"""Offline only: ssh -G never connects; all adapter execution uses fake runner."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from infrastructure.installer import remote_preflight as r


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.target = dict(host='149.210.166.239', port=22, user='o2-admin',
                           provider_instance='widjamin-vps6', generation='review-needed',
                           hostname='cloud.example.com', machine_id='21f6df03264056c90382000028c88d41',
                           boot_id='review-needed')
        self.verification = dict(target=self.target, independent=True, source='TransIP-console',
                                 reviewer='fixture-only', verified_at='2026-10-10T00:00:00Z',
                                 fingerprint='SHA256:IwugsqszZLcsMjve5+ZLja/HaSe7ORMbc9ciWb354tg')
        self.proposal = r.test_o_proposal(self.target, self.verification, profile='APP', max_age_seconds=300)
        now = datetime.now(timezone.utc)
        self.go = dict(scope='GO-1-read-only', target=self.target, actor='FICTIONAL', reference='FICTIONAL',
                       payload_sha256=hashlib.sha256(self.proposal['stdin'].encode()).hexdigest(),
                       issued_at=(now-timedelta(seconds=1)).isoformat(),
                       expires_at=(now+timedelta(seconds=60)).isoformat())

    def test_ssh_config_without_connection(self):
        argv = self.proposal['argv']
        result = subprocess.run([argv[0], '-G', *argv[1:]], shell=False,
                                capture_output=True, text=True, timeout=5, check=True)
        config = result.stdout
        for setting in ('identitiesonly yes', 'identityfile '+r.PUBLIC_KEY,
                        'identityagent '+r.AGENT, 'userknownhostsfile '+str(r.HOSTKEY_FILE),
                        'stricthostkeychecking true', 'forwardagent no'):
            self.assertIn(setting, config)
        self.assertNotIn('def evaluate', self.proposal['stdin'])
        self.assertNotIn('def save', self.proposal['stdin'])

    def test_fake_runner_and_failed_evidence_no_retry(self):
        for error, code, stdout in ((None, 255, 'failed'), ('timeout', -1, 'partial'),
                                    ('output limit', -1, 'x'*(r.LIMIT+1))):
            with tempfile.TemporaryDirectory() as folder, patch.object(r, 'STORE_ROOT', Path(folder)), \
                 patch.object(r, 'bounded_runner', side_effect=AssertionError('Real transport forbidden')):
                calls = []
                def fake(argv, **kwargs):
                    calls.append((argv, kwargs))
                    return dict(returncode=code, stdout=stdout, stderr='fixture', error=error)
                evidence = r.run_preflight(self.proposal, go_record=self.go,
                                           directory=Path(folder)/'evidence', runner=fake)
                self.assertEqual(evidence['status'], 'FAIL')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1]['shell'], False)
                self.assertEqual(calls[0][1]['timeout'], 90)
                self.assertEqual(calls[0][1]['output_limit'], r.LIMIT)
                self.assertTrue((Path(folder)/'evidence/evidence.json').exists())

    def test_modified_command_payload_pin_and_go_rejected_before_runner(self):
        for field in ('argv', 'stdin', 'known_hosts'):
            proposal = copy.deepcopy(self.proposal)
            proposal[field] += ['sudo'] if field == 'argv' else '\nmalicious'
            with self.assertRaises(ValueError):
                r.run_preflight(proposal, go_record=self.go, directory='/unused',
                                runner=lambda *a, **k: self.fail('Runner called'))
        with self.assertRaises(ValueError):
            r.run_preflight(self.proposal, go_record={}, directory='/unused',
                            runner=lambda *a, **k: self.fail('Runner called'))
        with patch.object(r.HOSTKEY_FILE.__class__, 'read_text', return_value='bad pin'):
            with self.assertRaises(ValueError):
                r.test_o_proposal(self.target, self.verification, profile='APP', max_age_seconds=300)
        with self.assertRaises(ValueError):
            r.test_o_proposal({**self.target, 'host': 'other'}, self.verification,
                              profile='APP', max_age_seconds=300)

    def test_bounded_runner_offline_process_limits(self):
        import sys
        for code, timeout, limit in (("print('x'*10000)", 5, 100),
                                     ('import time; time.sleep(1)', 0.05, 100)):
            result = r.bounded_runner((sys.executable, '-B', '-c', code),
                                      input='', timeout=timeout, output_limit=limit, shell=False)
            self.assertEqual(result['returncode'], -1)
            self.assertTrue(result['error'])
            self.assertLessEqual(len(result['stdout'].encode()), limit)
        result = r.bounded_runner((sys.executable, '-B', '-c',
                                   "import sys; print(sys.stdin.read()); print('err', file=sys.stderr)"),
                                  input='fixture', timeout=5, output_limit=100, shell=False)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['stdout'], 'fixture\n')
