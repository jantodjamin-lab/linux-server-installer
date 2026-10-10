"""Offline bounds for isolated CI orchestration; never starts a VM."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'lib'))
from core import BASE


spec = importlib.util.spec_from_file_location('fault_matrix', BASE/'tools/make-fault-matrix.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class CIHarnessTests(unittest.TestCase):
    def evidence(self, root):
        for profile, count in [('APP', 3), ('DB', 2), ('APP+DB', 4)]:
            file = root/('layer3-'+profile)/'case-000/artifacts/result.json'
            file.parent.mkdir(parents=True)
            file.write_text(json.dumps(dict(profile=profile, status='PASS', fault_event=0, journal_events=count)))

    def test_each_observed_event_has_one_fresh_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.evidence(root)
            rows = helper.matrix(root)['include']
            self.assertEqual(len(rows), 9)
            self.assertEqual(len({(row['profile'], row['event']) for row in rows}), 9)
            self.assertEqual([row['event'] for row in rows if row['profile']=='APP+DB'], [1, 2, 3, 4])

    def test_missing_failed_or_unbounded_evidence_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError): helper.matrix(root)
            self.evidence(root)
            file = root/'layer3-DB/case-000/artifacts/result.json'
            data = json.loads(file.read_text())
            for key, value in [('status', 'FAIL'), ('journal_events', 81), ('journal_events', True), ('fault_event', 1)]:
                invalid = dict(data); invalid[key] = value; file.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError): helper.matrix(root)

    def test_ci_setup_refuses_local_host_before_commands(self):
        before = dict(os.environ)
        result = subprocess.run(['/bin/sh', str(BASE/'tools/ci-vm.sh')], env={}, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Refusing: disposable GitHub-hosted Linux runner required', result.stderr)
        self.assertEqual(dict(os.environ), before)
