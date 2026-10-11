import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from infrastructure.installer import preflight as p


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.observed = {
            'os': {'ID': '"ubuntu"'},
            'kernel': {'system': 'Linux', 'release': 'fixture-kernel'},
            'cpu': 4, 'memory': {'ram_mib': 8192, 'swap_mib': 4096},
            'disk': {'path': '/fixture', 'free_gib': 40},
            'services': [{'unit': 'ssh.service', 'load': 'loaded', 'active': 'active', 'sub': 'running'}],
            'ports': [{'protocol': 'tcp', 'address': '[::]', 'port': 22}],
            'ssh_binary': '/fixture/sshd', 'sudo_binary': '/fixture/sudo',
        }

    def statuses(self, report):
        return {c['name']: c['status'] for c in report['checks']}

    def test_all_profiles_and_safety_warnings(self):
        for profile in p.PROFILES:
            with self.subTest(profile=profile):
                report = p.evaluate(profile, self.observed, {})
                statuses = self.statuses(report)
                self.assertEqual(report['status'], 'WARN')
                for name in ('cpu', 'ram', 'disk', 'kernel', 'ports', 'ssh_service'):
                    self.assertEqual(statuses[name], 'PASS')
                self.assertEqual(statuses['sudo_passwordless'], 'WARN')

    def test_profile_minimum_boundaries(self):
        for profile, policy in p.PROFILES.items():
            for name, key, amount in [('cpu', 'cpu', policy['cpu']),
                                      ('ram', 'ram_mib', policy['ram_mib']),
                                      ('disk', 'free_gib', policy['disk_gib'])]:
                for delta, expected in [(0, 'PASS'), (-1, 'FAIL' if name == 'disk' else 'WARN')]:
                    observed = copy.deepcopy(self.observed)
                    target = observed if name == 'cpu' else observed['memory' if name == 'ram' else 'disk']
                    target[key] = amount + delta
                    self.assertEqual(self.statuses(p.evaluate(profile, observed, {}))[name], expected)

    def test_missing_swap_conflicts_and_unknown_os(self):
        self.observed['memory']['swap_mib'] = 0
        self.observed['os']['ID'] = 'other'
        self.observed['ports'].append({'protocol': 'tcp', 'address': '0.0.0.0', 'port': 5432})
        statuses = self.statuses(p.evaluate('DB', self.observed, {}))
        for name in ('swap', 'os', 'ports'):
            self.assertEqual(statuses[name], 'WARN')
        self.assertEqual(self.statuses(p.evaluate('APP', self.observed, {}))['ports'], 'PASS')

    def test_non_linux_fails(self):
        self.observed['kernel']['system'] = 'Other'
        self.assertEqual(p.evaluate('APP', self.observed, {})['status'], 'FAIL')

    def test_unavailable_observations_warn(self):
        report = p.evaluate('APP', {}, {'memory': 'PermissionError', 'ports': 'TimeoutExpired'})
        self.assertEqual(report['status'], 'WARN')
        self.assertEqual(report['errors']['ports'], 'TimeoutExpired')
        self.assertEqual(self.statuses(report)['swap'], 'WARN')

    def test_parsers(self):
        self.assertEqual(p.parse_memory('MemTotal: 2097152 kB\nSwapTotal: 0 kB\n'),
                         {'ram_mib': 2048, 'swap_mib': 0})
        self.assertEqual(p.parse_ports('tcp LISTEN 0 128 [::]:22 [::]:*\nudp UNCONN 0 0 0.0.0.0:53 0.0.0.0:*\n')[1]['port'], 53)
        self.assertEqual(p.parse_services('ssh.service loaded active running OpenSSH server\n')[0]['unit'], 'ssh.service')
        for parser, value in [(p.parse_memory, 'MemTotal: x kB'),
                              (p.parse_ports, 'invalid'), (p.parse_services, 'invalid')]:
            with self.assertRaises((ValueError, KeyError)):
                parser(value)

    def test_queries_are_fixed_local_and_bounded(self):
        with patch.object(p.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'fixture')) as run:
            for name, command in p.QUERIES.items():
                self.assertEqual(p.query(name), 'fixture')
                args, kwargs = run.call_args
                self.assertEqual(args[0], command)
                self.assertEqual(kwargs['timeout'], 5)
                self.assertNotIn('shell', kwargs)
                self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
                self.assertNotIn(command[0], ('sudo', 'ssh', 'apt'))
        with self.assertRaises(KeyError):
            p.query('sudo')
        with patch.object(p.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '')):
            with self.assertRaises(RuntimeError):
                p.query('ports')

    def test_collection_continues_after_read_and_query_failure(self):
        with patch.object(p.Path, 'read_text', side_effect=PermissionError('fixture')), \
             patch.object(p, 'query', side_effect=subprocess.TimeoutExpired('fixture', 5)), \
             patch.object(p.platform, 'system', return_value='Linux'), \
             patch.object(p.platform, 'release', return_value='fixture'), \
             patch.object(p.os, 'cpu_count', return_value=4), \
             patch.object(p.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 40 * 1024**3})()), \
             patch.object(p.shutil, 'which', return_value='/fixture/program'):
            observations, errors = p.collect(Path('/fixture'))
        self.assertEqual(observations['cpu'], 4)
        self.assertEqual(set(errors), {'os', 'memory', 'services', 'ssh_sockets', 'ports'})
        self.assertEqual(observations['disk']['free_gib'], 40)

    def test_failed_checks_still_saved_and_no_overwrite(self):
        self.observed['cpu'] = 0
        with tempfile.TemporaryDirectory(dir=p.ROOT) as folder, patch.object(p, 'ROOT', Path(folder)), \
             patch.object(p, 'collect', return_value=(self.observed, {})), \
             patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
            output = Path(folder) / 'evidence.json'
            self.assertEqual(p.main(['--profile', 'APP', '--output', str(output)]), 1)
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'FAIL')
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                p.save_evidence(report, output)
            self.assertEqual(before, output.read_bytes())

    def test_output_failure_preserves_json_on_stdout(self):
        with patch.object(p, 'collect', return_value=(self.observed, {})), \
             patch.object(p, 'save_evidence', side_effect=OSError('fixture')), \
             patch('sys.stdout', new_callable=io.StringIO) as stdout, \
             patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(p.main(['--profile', 'APP']), 1)
            self.assertEqual(json.loads(stdout.getvalue())['status'], 'FAIL')

    def test_output_path_limits_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=p.ROOT) as folder, patch.object(p, 'ROOT', Path(folder)):
            root = Path(folder)
            for output in (root.parent / 'outside.json', root / '.git' / 'file.json'):
                with self.assertRaises(ValueError):
                    p.save_evidence({}, output)
            (root / 'escape').symlink_to(root.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                p.save_evidence({}, root / 'escape' / 'file.json')

    def test_otest_resources_and_production_advice(self):
        for profile in p.PROFILES:
            for ram in (843, 843.0625):
                with self.subTest(profile=profile, ram=ram):
                    observed = copy.deepcopy(self.observed)
                    observed['cpu'] = 1
                    observed['memory']['ram_mib'] = ram
                    report = p.evaluate(profile, observed, {})
                    self.assertEqual(report['status'], 'WARN')
                    self.assertEqual(self.statuses(report)['cpu'], 'WARN')
                    self.assertEqual(self.statuses(report)['ram'], 'WARN')
                    self.assertEqual(report['policy']['production_recommendation'], p.PROFILES[profile])

    def test_otest_floor_and_swap_independent(self):
        for profile in p.PROFILES:
            for resource, value in (('cpu', 0), ('ram', 842)):
                observed = copy.deepcopy(self.observed)
                if resource == 'cpu':
                    observed['cpu'] = value
                else:
                    observed['memory']['ram_mib'] = value
                self.assertEqual(self.statuses(p.evaluate(profile, observed, {}))[resource], 'FAIL')
        for memory, ram_status, swap_status in (
            ({'ram_mib': 843, 'swap_mib': 0}, 'WARN', 'WARN'),
            ({'ram_mib': 843}, 'WARN', 'WARN'),
            ({'swap_mib': 4096}, 'WARN', 'PASS'),
            ({'ram_mib': 8192, 'swap_mib': 0}, 'PASS', 'WARN'),
        ):
            self.observed['memory'] = memory
            statuses = self.statuses(p.evaluate('APP', self.observed, {}))
            self.assertEqual(statuses['ram'], ram_status)
            self.assertEqual(statuses['swap'], swap_status)
        self.assertEqual(p.parse_memory('MemTotal: 863232 kB'), {'ram_mib': 843})

    def test_not_found_services_are_informational(self):
        observed = copy.deepcopy(self.observed)
        observed['services'] = [
            {'unit': 'optional.service', 'load': 'not-found',
             'active': 'inactive', 'sub': 'dead'},
            {'unit': 'ssh.service', 'load': 'loaded',
             'active': 'active', 'sub': 'running'},
        ]
        report = p.evaluate('APP', observed, {})
        self.assertEqual(self.statuses(report)['services'], 'PASS')
        self.assertEqual(self.statuses(report)['ssh_service'], 'PASS')

        observed['services'][0]['load'] = 'bad-setting'
        self.assertEqual(
            self.statuses(p.evaluate('APP', observed, {}))['services'],
            'WARN'
        )

    def test_failed_services_and_ssh_states(self):
        services = p.parse_services('● broken.service loaded failed failed Broken\n'
                                    'ssh.service loaded active exited SSH\n')
        self.observed['services'] = services
        self.observed['ssh_sockets'] = p.parse_services(
            'ssh.socket loaded active listening SSH\n', '.socket')
        statuses = self.statuses(p.evaluate('APP', self.observed, {}))
        self.assertEqual(statuses['services'], 'WARN')
        self.assertEqual(statuses['ssh_service'], 'WARN')
        self.assertEqual(statuses['ssh_socket'], 'PASS')
        self.observed['ssh_sockets'][0]['active'] = 'inactive'
        self.assertEqual(self.statuses(p.evaluate('APP', self.observed, {}))['ssh_socket'], 'WARN')
        self.assertIn('--all', p.QUERIES['services'])
        self.assertNotIn('--state=active', p.QUERIES['services'])

    def test_port22_and_sudo_presence_do_not_prove_access(self):
        for binary in (None, '/fixture/sudo'):
            self.observed['sudo_binary'] = binary
            self.observed['identity'] = {'uid': 0, 'euid': 0, 'group_ids': [0, 27]}
            statuses = self.statuses(p.evaluate('APP', self.observed, {}))
            self.assertEqual(statuses['sudo_binary'], 'PASS' if binary else 'WARN')
            self.assertEqual(statuses['sudo_context'], 'PASS')
            self.assertEqual(statuses['sudo_passwordless'], 'WARN')
            self.assertEqual(statuses['ssh_security'], 'WARN')
        self.observed['ports'][0]['protocol'] = 'udp'
        self.assertEqual(self.statuses(p.evaluate('APP', self.observed, {}))['ssh_listener'], 'WARN')

    def test_query_failure_details_preserved_in_json(self):
        with patch.object(p.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 1, 'partial fixture output', 'fixture systemd unavailable')):
            observations, errors = p.collect(p.ROOT)
        report = p.evaluate('APP', observations, errors)
        for name in p.QUERIES:
            self.assertEqual(report['errors'][name]['returncode'], 1)
            self.assertEqual(report['errors'][name]['stdout'], 'partial fixture output')
            self.assertEqual(report['errors'][name]['stderr'], 'fixture systemd unavailable')
        with tempfile.TemporaryDirectory(dir=p.ROOT) as folder:
            output = Path(folder) / 'errors.json'
            p.save_evidence(report, output)
            self.assertEqual(json.loads(output.read_text())['errors'], errors)

    def test_parse_failure_preserves_raw_output(self):
        with patch.object(p, 'query', return_value='invalid fixture output'):
            observations, errors = p.collect(p.ROOT)
        for name in p.QUERIES:
            self.assertIn(name, errors)
            self.assertEqual(observations[name + '_raw'], 'invalid fixture output')
        json.dumps(p.evaluate('APP', observations, errors))

    def test_timeout_partial_output_is_json_serializable(self):
        with patch.object(p, 'query', side_effect=subprocess.TimeoutExpired(
                'fixture', 5, output=b'partial', stderr=b'fixture error')):
            observations, errors = p.collect(p.ROOT)
        self.assertEqual(errors['services']['stdout'], 'partial')
        self.assertEqual(errors['services']['stderr'], 'fixture error')
        self.assertEqual(errors['services']['timeout_seconds'], 5)
        json.dumps(p.evaluate('APP', observations, errors))

    def test_invalid_profile_rejected_before_collection(self):
        with patch.object(p, 'collect') as collect, patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                p.main(['--profile', 'OTHER'])
            collect.assert_not_called()

    def test_missing_inventory_is_explicit_warn(self):
        statuses = self.statuses(p.evaluate('APP', {}, {}))
        for name in ('os', 'kernel', 'services', 'ssh_sockets', 'ports',
                     'ssh_binary', 'sudo_binary', 'identity'):
            self.assertEqual(statuses[name], 'WARN')

    def test_protected_evidence_directories(self):
        with tempfile.TemporaryDirectory(dir=p.ROOT) as folder, patch.object(p, 'ROOT', Path(folder)):
            for directory in ('references', '.aws', '.codex', '.agents'):
                with self.subTest(directory=directory), self.assertRaises(ValueError):
                    p.save_evidence({}, Path(folder) / directory / 'new.json')
                self.assertFalse((Path(folder) / directory).exists())


if __name__ == '__main__':
    unittest.main()
