import hashlib
import tempfile
from pathlib import Path
import unittest
from test_core import fixture
from core import PROFILES
from engine import Engine, LiveRunner, actions, verify_bundle


class FakeRunner:
    def __init__(self):
        self.installed = {}; self.calls = []; self.fail = False; self.reboot = False
    def version(self, name): return self.installed.get(name)
    def install(self, step):
        self.calls.append(step['id'])
        if self.fail: raise RuntimeError('secret should never enter journal')
        self.installed[step['id']] = step['version']
    def validate(self, step): return self.version(step['id']) == step['version']
    def reboot_required(self): return self.reboot


def bundle(root, profile):
    packages = []
    versions = {'nodejs': '22.12.0', 'angular-cli': '20.0.0', 'dotnet-sdk-10.0': '10.0.1', 'postgresql-18': '18.0'}
    names = list(PROFILES[profile]['packages']) + ([] if profile == 'DB' else ['angular-cli'])
    for name in names:
        path = root / (name + '.deb'); path.write_bytes(name.encode())
        packages.append({'name': name, 'version': versions.get(name, '1.0'), 'file': path.name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'source': 'https://archive.ubuntu.com/ubuntu/', 'kind': 'deb'})
    return {'schema': 1, 'os': 'ubuntu-26.04', 'arch': 'amd64', 'packages': packages, 'updates': [], 'development': False}


class EngineTests(unittest.TestCase):
    def test_all_profiles_and_idempotence(self):
        for profile in PROFILES:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); manifest = bundle(root, profile)
                binding = verify_bundle(manifest, root, profile)
                runner = FakeRunner(); engine = Engine(runner, root / 'state.json', binding)
                self.assertEqual(engine.run(actions(manifest))['status'], 'PASS')
                count = len(runner.calls)
                self.assertEqual(Engine(runner, root / 'state.json', binding).run(actions(manifest))['status'], 'PASS')
                self.assertEqual(len(runner.calls), count)
    def test_interruption_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = bundle(root, 'DB'); runner = FakeRunner(); runner.fail = True
            engine = Engine(runner, root / 'state.json', 'binding')
            with self.assertRaises(RuntimeError): engine.run(actions(manifest))
            self.assertNotIn('secret', (root / 'state.json').read_text())
            runner.fail = False
            reopened = Engine(runner, root / 'state.json', 'binding')
            with self.assertRaises(ValueError): reopened.run(actions(manifest))
            self.assertEqual(reopened.run(actions(manifest), review=True)['status'], 'PASS')
    def test_source_checksum_traversal(self):
        for field, value in [('source', 'https://evil.invalid/'), ('file', '../secret'), ('sha256', '0'*64), ('version', '1;id')]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); manifest = bundle(root, 'DB'); manifest['packages'][0][field] = value
                with self.assertRaises(ValueError): verify_bundle(manifest, root, 'DB')
    def test_live_disabled(self):
        with self.assertRaises(RuntimeError): LiveRunner()
