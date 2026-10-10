import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from test_core import fixture
from core import PROFILES
from workflow import build_workflow, validate_lock
from journal import Journal, run_workflow
from local import LocalRunner, NGINX, PGCONF, validate_sources, check_npm_lock, approve_uri
from cli import read_json


def lock_for(profile):
    versions = {'dotnet-sdk-10.0': '10.0.100-0ubuntu1', 'nodejs': '22.12.0-0ubuntu1', 'postgresql-18': '18.0-1'}
    apt = {name: versions.get(name, '1.0-1') for name in [*PROFILES[profile]['packages'], 'ca-certificates']}
    return {'schema': 2, 'apt': apt, 'updates': {}, 'npm': {} if profile == 'DB' else
            {'@angular/cli': {'version': '20.3.0', 'lock_sha256': 'a'*64}}}


def sources(root):
    path = root/'etc/apt/sources.list.d/ubuntu.sources'; path.parent.mkdir(parents=True)
    path.write_text('Types: deb\nURIs: http://archive.ubuntu.com/ubuntu/\nSuites: resolute resolute-updates resolute-security\nComponents: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
    key = root/'usr/share/keyrings/ubuntu-archive-keyring.gpg'; key.parent.mkdir(parents=True); key.write_bytes(b'fixture-key')


class Runner:
    def __init__(self): self.done = set(); self.fail = None; self.reboot = False; self.calls = []
    def apply(self, step):
        self.calls.append(step['id'])
        if step['id'] == self.fail: raise RuntimeError('PRIVATE_CREDENTIAL')
        self.done.add(step['id'])
    def validate(self, step): return step['id'] in self.done
    def reboot_required(self): return self.reboot


class WorkflowTests(unittest.TestCase):
    def test_all_profiles_repeat_and_no_input_mutation(self):
        for profile in PROFILES:
            observed = fixture(); lock = lock_for(profile); before = copy.deepcopy(lock)
            workflow = build_workflow(profile, observed, lock)
            self.assertEqual(lock, before)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)/'private'; runner = Runner()
                self.assertEqual(run_workflow(workflow, runner, root)['status'], 'PASS')
                count = len(runner.calls)
                self.assertEqual(run_workflow(workflow, runner, root)['status'], 'PASS')
                self.assertEqual(len(runner.calls), count)
    def test_development_only_codex(self):
        lock = lock_for('APP'); lock['npm']['@openai/codex'] = {'version': '0.128.0', 'lock_sha256': 'b'*64}
        self.assertIn('codex', [s['id'] for s in build_workflow('APP', fixture(), lock, True)['steps']])
        with self.assertRaises(ValueError): build_workflow('APP', fixture(), lock, False)
        with self.assertRaises(ValueError): build_workflow('DB', fixture(), lock_for('DB'), True)
    def test_updates_require_explicit_opt_in(self):
        lock = lock_for('DB'); lock['updates']['openssl'] = '3.0-1'
        with self.assertRaises(ValueError): build_workflow('DB', fixture(), lock)
        self.assertIn('system-updates', [s['id'] for s in build_workflow('DB', fixture(), lock, system_updates=True)['steps']])
    def test_node_compatibility_and_injection(self):
        for version in ('22.0.0', '23.0.0', '22.12.0;id', 'latest'):
            lock = lock_for('APP'); lock['apt']['nodejs'] = version
            with self.assertRaises(ValueError): validate_lock(lock, 'APP', False)
    def test_conflicts_and_bad_inventory(self):
        observed = fixture(); observed['packages']['git'] = '0.1'
        with self.assertRaises(ValueError): build_workflow('DB', observed, lock_for('DB'))
        observed = fixture(); observed['errors'] = ['inventory']
        with self.assertRaises(ValueError): build_workflow('DB', observed, lock_for('DB'))
    def test_interrupted_recovery_and_sanitized_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = build_workflow('DB', fixture(), lock_for('DB')); runner = Runner(); runner.fail = 'packages'
            root = Path(tmp)/'private'
            with self.assertRaises(RuntimeError): run_workflow(workflow, runner, root)
            self.assertNotIn('PRIVATE_CREDENTIAL', (root/'journal.json').read_text())
            runner.fail = None
            with self.assertRaises(ValueError): run_workflow(workflow, runner, root)
            with self.assertRaises(ValueError): run_workflow(workflow, runner, root, recovery_review=1)
            self.assertEqual(run_workflow(workflow, runner, root, recovery_review=True)['status'], 'PASS')
    def test_corruption_binding_lock_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'private'
            with Journal(root, 'x') as first:
                first.save()
                with self.assertRaises(BlockingIOError):
                    with Journal(root, 'x'): pass
            with self.assertRaises(ValueError):
                with Journal(root, 'other'): pass
            data=json.loads((root/'journal.json').read_text()); data['state']['done'].append('forged')
            (root/'journal.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                with Journal(root, 'x'): pass
            root.chmod(0o755)
            with self.assertRaises(ValueError):
                with Journal(root, 'x'): pass
    def test_drift_and_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = build_workflow('DB', fixture(), lock_for('DB')); runner = Runner(); runner.reboot = True
            self.assertEqual(run_workflow(workflow, runner, Path(tmp)/'p')['status'], 'WARN')
            self.assertFalse(runner.calls)
            runner.reboot=False; run_workflow(workflow, runner, Path(tmp)/'p'); runner.done.remove('packages')
            with self.assertRaises(ValueError): run_workflow(workflow, runner, Path(tmp)/'p')
    def test_source_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sources(root); self.assertTrue(validate_sources(root))
            source=root/'etc/apt/sources.list.d/ubuntu.sources'
            source.write_text(source.read_text().replace('archive.ubuntu.com','evil.invalid'))
            with self.assertRaises(ValueError): validate_sources(root)
        for url in ('https://user:secret@archive.ubuntu.com/ubuntu/', 'file:///tmp/repo', 'https://archive.ubuntu.com/ubuntu/?token=secret'):
            with self.assertRaises(ValueError): approve_uri(url)
    def test_duplicate_json_and_no_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json'; path.write_text('{"apt":1,"apt":2}')
            with self.assertRaises(ValueError): read_json(path)
            workflow=build_workflow('DB', fixture(), lock_for('DB'))
            with self.assertRaises(ValueError): LocalRunner(workflow, '', root=tmp)

    def test_node24_and_listener_conflict(self):
        lock=lock_for('APP'); lock['apt']['nodejs']='24.0.0-1'
        self.assertEqual(build_workflow('APP',fixture(),lock)['status'],'WARN')
        observed=fixture(); observed['tcp_ports']=[8080]
        with self.assertRaises(ValueError): build_workflow('APP',observed,lock)

    def test_process_exit_preserves_pending(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private'
            script = "import os,sys; from journal import Journal; j=Journal(sys.argv[1], 'crash'); j.__enter__(); j.state['pending']='packages'; j.event('STARTED','packages'); os._exit(17)"
            result=subprocess.run([sys.executable,'-B','-c',script,str(root)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'lib')},timeout=10)
            self.assertEqual(result.returncode,17)
            with Journal(root,'crash') as journal:
                self.assertEqual(journal.state['pending'],'packages')
