import ast
from pathlib import Path
import subprocess
import unittest

BASE = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_cli_rejects_live_and_remote_options(self):
        for option in ('--execute', '--host', '--ssh'):
            result = subprocess.run(['sh', str(BASE / 'install.sh'), '--profile', 'DB', option], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
    def test_static_syntax_and_no_shell_execution(self):
        for path in (BASE/'lib').glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    self.assertFalse(any(k.arg == 'shell' and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords))
        result = subprocess.run(['sh', '-n', str(BASE/'install.sh')], timeout=10)
        self.assertEqual(result.returncode, 0)
