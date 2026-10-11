import copy
import json
import unittest
from unittest.mock import patch

from infrastructure.installer import plan
from infrastructure.installer import preflight as p


class PlanTests(unittest.TestCase):
    def evidence(self, profile='APP'):
        return p.evaluate(profile, {
            'os': {'ID': 'ubuntu'}, 'kernel': {'system': 'Linux', 'release': 'fixture'},
            'cpu': 1, 'memory': {'ram_mib': 843, 'swap_mib': 0},
            'disk': {'free_gib': 40}, 'services': [], 'ssh_sockets': [], 'ports': [],
            'ssh_binary': None, 'sudo_binary': None,
            'identity': {'uid': 1000, 'euid': 1000, 'group_ids': [1000]},
        }, {})

    def test_profiles_open_contract_and_resources(self):
        for profile, roles in [('APP', ['APP']), ('DB', ['DB']), ('APP-DB', ['APP', 'DB'])]:
            result = plan.build_plan(self.evidence(profile))
            self.assertEqual([c['role'] for c in result['components']], roles)
            self.assertEqual(result['status'], 'WARN')
            self.assertEqual(result['preflight_status'], 'WARN')
            self.assertFalse(result['installation_authorized'])
            self.assertFalse(result['executable'])
            self.assertEqual(result['completeness'], 'OPEN')
            self.assertEqual(result['policy']['minimum']['ram_mib'], 843)
            self.assertTrue(result['open_decisions'])
            self.assertFalse(result['recovery']['proven'])
            for component in result['components']:
                self.assertIsNone(component['package_versions'])
                self.assertFalse(component['ports']['approved'])
                for field in ('dependencies', 'required_privileges', 'preconditions', 'postconditions'):
                    self.assertTrue(component[field])

    def test_deterministic_binding_and_no_io_or_mutation(self):
        evidence = self.evidence()
        before = copy.deepcopy(evidence)
        with patch.object(p, 'collect', side_effect=AssertionError('probe')), \
             patch.object(p, 'save_evidence', side_effect=AssertionError('write')), \
             patch.object(p.subprocess, 'run', side_effect=AssertionError('command')):
            first = plan.build_plan(evidence)
            self.assertEqual(first, plan.build_plan(evidence))
        self.assertEqual(evidence, before)
        evidence['timestamp_utc'] += '-different'
        self.assertNotEqual(first['evidence_binding']['sha256'], plan.build_plan(evidence)['evidence_binding']['sha256'])
        json.dumps(first, allow_nan=False)

    def test_fail_evidence_produces_reviewable_fail_plan(self):
        evidence = self.evidence()
        evidence['observations']['cpu'] = 0
        evidence = p.evaluate('APP', evidence['observations'], {})
        result = plan.build_plan(evidence)
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['installation_authorized'])
        self.assertTrue(result['components'])

    def test_missing_inventory_stays_open(self):
        evidence = p.evaluate('DB', {}, {'ports': {'message': 'fixture timeout'},
                                        'os': {'message': 'fixture denied'}})
        result = plan.build_plan(json.loads(json.dumps(evidence, sort_keys=True)))
        self.assertIn('ports', result['missing_observations'])
        self.assertIn('kernel', result['missing_observations'])
        self.assertEqual(result['status'], 'WARN')

    def test_invalid_or_inconsistent_evidence_rejected(self):
        for field, value in [('schema_version', 1), ('profile', 'OTHER'), ('scope', 'remote'),
                             ('status', 'PASS'), ('checks', []), ('policy', {}),
                             ('observations', None), ('timestamp_utc', '')]:
            evidence = self.evidence()
            evidence[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                plan.build_plan(evidence)
        with self.assertRaises(ValueError):
            plan.build_plan({})
        evidence = self.evidence()
        evidence['observations']['cpu'] = float('nan')
        with self.assertRaises(ValueError):
            plan.build_plan(evidence)

    def test_plan_storage_preserves_fail_and_rejects_overwrite(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(dir=p.ROOT) as folder:
            output = Path(folder) / 'plan.json'
            evidence = p.evaluate('DB', {'cpu': 0}, {})
            result = plan.build_plan(evidence)
            p.save_evidence(result, output)
            self.assertEqual(json.loads(output.read_text())['status'], 'FAIL')
            with self.assertRaises(FileExistsError):
                p.save_evidence(result, output)


if __name__ == '__main__':
    unittest.main()
