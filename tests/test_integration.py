import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_engine import FakeRunner, bundle
from engine import Engine, actions, verify_bundle

BASE = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_cli_rejects_live_and_remote_options(self):
        for option in ('--execute', '--host', '--ssh'):
            result = subprocess.run(['sh', str(BASE / 'install.sh'), '--profile', 'DB', option], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
    def test_reboot_stops_before_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner(); runner.reboot = True
            engine = Engine(runner, Path(tmp)/'state.json', 'x')
            with self.assertRaises(ValueError): engine.run(actions(bundle(Path(tmp), 'DB')))
            self.assertEqual(runner.calls, [])
    def test_version_conflict_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner(); runner.installed['git'] = '2.0'
            engine = Engine(runner, Path(tmp)/'state.json', 'x')
            with self.assertRaises(ValueError): engine.run(actions(bundle(Path(tmp), 'DB')))
            self.assertEqual(runner.calls, [])
    def test_drift_is_validated_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); runner = FakeRunner(); steps = actions(bundle(root, 'DB'))
            engine = Engine(runner, root/'state.json', 'x'); engine.run(steps)
            runner.validate = lambda step: False
            with self.assertRaises(ValueError): engine.run(steps)
    def test_postcondition_failure_and_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); runner = FakeRunner(); runner.validate = lambda step: False
            engine = Engine(runner, root/'state.json', 'x')
            with self.assertRaises(RuntimeError): engine.run(actions(bundle(root, 'DB')))
            self.assertEqual(json.loads((root/'state.json').read_text())['pending'], 'git')
            with self.assertRaises(ValueError): Engine(runner, root/'state.json', 'different')
    def test_corrupt_checkpoint_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'state.json').write_text('invalid')
            with self.assertRaises(ValueError): Engine(FakeRunner(), root/'state.json', 'x')
            (root/'link').symlink_to(root/'state.json')
            with self.assertRaises(ValueError): Engine(FakeRunner(), root/'link', 'x')
    def test_artifact_tamper_and_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = bundle(root, 'DB'); first = root/manifest['packages'][0]['file']
            first.write_bytes(b'tampered')
            with self.assertRaises(ValueError): verify_bundle(manifest, root, 'DB')
            first.unlink(); first.symlink_to(root/manifest['packages'][1]['file'])
            with self.assertRaises(ValueError): verify_bundle(manifest, root, 'DB')
    def test_static_syntax_and_no_shell_execution(self):
        for path in (BASE/'lib').glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    self.assertFalse(any(k.arg == 'shell' and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords))
        result = subprocess.run(['sh', '-n', str(BASE/'install.sh')], timeout=10)
        self.assertEqual(result.returncode, 0)
