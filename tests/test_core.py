import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from core import PROFILES, plan


def fixture():
    return {'kernel': 'Linux', 'os': {'ID': 'ubuntu', 'VERSION_ID': '26.04'}, 'arch': 'x86_64', 'cpu': 2, 'ram_mib': 4096, 'disk_gib': 40, 'packages': {}, 'errors': []}


class PolicyTests(unittest.TestCase):
    def test_profiles_deterministic_and_no_mutation(self):
        for profile in PROFILES:
            source = fixture()
            before = copy.deepcopy(source)
            self.assertEqual(plan(profile, source), plan(profile, source))
            self.assertEqual(source, before)
            self.assertFalse(plan(profile, source)['installation_authorized'])
    def test_unsupported(self):
        for key, value in [('kernel', 'Windows'), ('arch', 'mips'), ('cpu', 0), ('ram_mib', 842), ('disk_gib', 0), ('os', {})]:
            source = fixture(); source[key] = value
            self.assertEqual(plan('APP', source)['status'], 'FAIL')
    def test_inventory_failure(self):
        source = fixture(); source['errors'] = ['package-inventory']
        self.assertEqual(plan('DB', source)['status'], 'FAIL')
