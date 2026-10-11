import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from infrastructure.installer import remote_preflight as r
from infrastructure.installer import preflight as p


class RemotePreparationTests(unittest.TestCase):
    def setUp(self):
        self.target = dict(host='fixture.invalid', port=2222, user='fixture',
                           provider_instance='fictional-instance', generation='fixture-1',
                           hostname='fixture', machine_id='fictional-machine', boot_id='fictional-boot')
        wire = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + b'x'*32
        self.pin = '[fixture.invalid]:2222 ssh-ed25519 ' + base64.b64encode(wire).decode()
        self.verification = dict(target=self.target, independent=True, source='fictional-console',
                                 reviewer='fictional-operator', verified_at='2026-10-10T00:00:00Z',
                                 fingerprint='SHA256:' + base64.b64encode(hashlib.sha256(wire).digest()).decode().rstrip('='))
        self.proposal = r.prepare(self.target, self.pin, self.verification, profile='APP', max_age_seconds=300)
        observations = dict(os={'ID': 'ubuntu'}, kernel={'system': 'Linux', 'release': 'fictional'},
                            cpu=1, memory={'ram_mib': 843, 'swap_mib': 0},
                            disk={'path': '/', 'free_gib': 40}, services=[], ssh_sockets=[], ports=[],
                            ssh_binary=None, sudo_binary=None, identity={'uid': 1000, 'euid': 1000, 'group_ids': [1000]})
        report = p.evaluate('APP', observations, {})
        report['timestamp_utc'] = '2026-10-10T00:00:01Z'
        self.payload = dict(nonce=self.proposal['nonce'], observations=observations, errors={}, timestamp_utc=report['timestamp_utc'],
                            identity={k:self.target[k] for k in ('hostname','machine_id','boot_id','user')})

    def assess(self, payload=None, **kwargs):
        arguments = dict(started_at='2026-10-10T00:00:00Z', received_at='2026-10-10T00:00:02Z',
                         now='2026-10-10T00:00:03Z', returncode=0)
        arguments.update(kwargs)
        return r.assess(self.proposal, json.dumps(payload or self.payload), **arguments)

    def test_pure_proposal_strict_transport_and_stdin(self):
        with patch('subprocess.run', side_effect=AssertionError('No transport')), \
             patch('socket.socket', side_effect=AssertionError('No network')):
            proposal = r.prepare(self.target, self.pin, self.verification, profile='DB', max_age_seconds=300)
        self.assertIn('StrictHostKeyChecking=yes', proposal['argv'])
        self.assertIn('UpdateHostKeys=no', proposal['argv'])
        self.assertEqual(proposal['argv'][-1], 'env LC_ALL=C PYTHONDONTWRITEBYTECODE=1 python3 -B -')
        compile(proposal['stdin'], '<fictional-stdin>', 'exec')
        self.assertNotIn('def save_evidence', proposal['stdin'])
        self.assertFalse(proposal['execution_authorized'])

    def test_independent_verification_pin_and_target_required(self):
        for field, value in [('independent', False), ('fingerprint', 'wrong'), ('target', {}), ('source', '')]:
            verification = {**self.verification, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.prepare(self.target, self.pin, verification, profile='APP', max_age_seconds=300)
        for pin in [self.pin.replace('[fixture.invalid]:2222', '*'), self.pin+'\n'+self.pin,
                    self.pin.replace('ssh-ed25519', 'ssh-rsa')]:
            with self.assertRaises(ValueError):
                r.prepare(self.target, pin, self.verification, profile='APP', max_age_seconds=300)
        for change in [dict(host='-option'), dict(user='root'), dict(port=True), dict(host='host;cmd')]:
            with self.assertRaises(ValueError):
                r.prepare({**self.target, **change}, self.pin, self.verification, profile='APP', max_age_seconds=300)

    def test_freshness_replay_drift_and_consistency_fail_closed(self):
        self.assertEqual(self.assess()['status'], 'WARN')
        for path, value in [(('nonce',), 'old'), (('identity', 'boot_id'), 'changed'),
                            (('observations', 'cpu'), 'invalid'),
                            (('timestamp_utc',), '2026-10-10T00:00:10Z'),
                            (('observations', 'identity', 'euid'), 0)]:
            payload = copy.deepcopy(self.payload)
            node = payload
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            self.assertEqual(self.assess(payload)['status'], 'FAIL')
        for kwargs in [dict(now='2026-10-10T00:06:00Z'), dict(received_at='2026-10-09T23:59:59Z'),
                       dict(now='2026-10-10T00:00:03'), dict(returncode=255, stderr='fictional error')]:
            self.assertEqual(self.assess(**kwargs)['status'], 'FAIL')

    def test_sorted_probe_failure_roundtrip_and_fail_report(self):
        observations = self.payload['observations']
        errors = {'ports': {'returncode': 1, 'stdout': 'fictional', 'stderr': 'failure'}}
        report = p.evaluate('APP', observations, errors)
        report['timestamp_utc'] = '2026-10-10T00:00:01Z'
        self.payload['errors'] = errors
        result = self.assess()
        self.assertEqual(result['status'], 'WARN')
        self.assertNotIn('error', result)
        observations['cpu'] = 0
        report = p.evaluate('APP', observations, {})
        report['timestamp_utc'] = '2026-10-10T00:00:01Z'
        self.payload['errors'] = {}
        result = self.assess()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('payload', result)

    def test_malformed_and_failed_evidence_preserved(self):
        evidence = r.assess(self.proposal, 'not json', started_at='bad', received_at='bad', now='bad', returncode=255)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertEqual(evidence['stdout'], 'not json')
        self.assertFalse(evidence['installation_authorized'])
        with tempfile.TemporaryDirectory(dir=p.ROOT) as temp, patch.object(r, 'STORE_ROOT', Path(temp)):
            destination = Path(temp)/'fixture'
            r.save(evidence, destination)
            self.assertEqual(json.loads((destination/'evidence.json').read_text()), evidence)
            self.assertEqual((destination/'evidence.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                r.save(evidence, destination)
            with self.assertRaises(ValueError):
                r.save(evidence, Path(temp).parent/'escape')
            (Path(temp)/'link').symlink_to(Path(temp)/'fixture', target_is_directory=True)
            with self.assertRaises(ValueError):
                r.save(evidence, Path(temp)/'link'/'new')


if __name__ == '__main__':
    unittest.main()
