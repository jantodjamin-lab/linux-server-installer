"""Explicit sudo delegates before probes or opening root-private plans."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from test_core import fixture
from cli import main


class CLISudoOrderTests(unittest.TestCase):
    def modes(self):
        return [
            ['--apply'],
            ['--resolve','--out','/root/private-plan','--refresh-metadata'],
            ['--execute','--plan','/root/private-plan/plan.json',
             '--approval','INSTALL:'+'a'*64,'--snapshot-confirmed','--allow-unvalidated'],
        ]

    def test_explicit_sudo_first_for_all_execution_modes(self):
        for mode in self.modes():
            with self.subTest(mode=mode):
                argv=['installer','--profile','DB',*mode,'--sudo']
                with patch('sys.argv',argv),patch('cli.os.geteuid',return_value=1000), \
                     patch('privilege.interactive_execute',return_value=17) as authorize, \
                     patch('cli.inventory') as inventory,patch('cli.read_json') as read_plan, \
                     patch('cli.LocalRunner') as runner:
                    self.assertEqual(main(),17)
                authorize.assert_called_once();inventory.assert_not_called()
                read_plan.assert_not_called();runner.assert_not_called()

    def test_nonroot_without_sudo_refused_without_opening_plan(self):
        for mode in self.modes():
            with self.subTest(mode=mode):
                out=io.StringIO()
                with patch('sys.argv',['installer','--profile','DB',*mode,'--json']), \
                     patch('cli.os.geteuid',return_value=1000), \
                     patch('privilege.interactive_execute') as authorize, \
                     patch('cli.inventory') as inventory,patch('cli.read_json') as read_plan, \
                     contextlib.redirect_stdout(out):
                    self.assertEqual(main(),1)
                self.assertEqual(json.loads(out.getvalue())['code'],
                                 'root-required-use-interactive-sudo')
                authorize.assert_not_called();inventory.assert_not_called();read_plan.assert_not_called()

    def test_noninteractive_sudo_stops_before_inventory_or_subprocess(self):
        out=io.StringIO()
        with patch('sys.argv',['installer','--profile','DB','--apply','--sudo','--json']), \
             patch('cli.os.geteuid',return_value=1000), \
             patch('privilege.sys.stdin.isatty',return_value=False), \
             patch('privilege.subprocess.run') as run,patch('cli.inventory') as inventory, \
             contextlib.redirect_stdout(out):
            self.assertEqual(main(),1)
        self.assertEqual(json.loads(out.getvalue())['code'],'sudo-interactive-terminal-required')
        run.assert_not_called();inventory.assert_not_called()

    def test_invalid_mirror_refused_before_sudo(self):
        out=io.StringIO()
        with patch('sys.argv',['installer','--profile','DB','--apply','--sudo','--json',
                               '--allow-mirror','https://user:password@example.org/ubuntu']), \
             patch('cli.os.geteuid',return_value=1000), \
             patch('privilege.interactive_execute') as authorize, \
             patch('cli.inventory') as inventory,contextlib.redirect_stdout(out):
            self.assertEqual(main(),1)
        authorize.assert_not_called();inventory.assert_not_called()
        self.assertNotIn('password',out.getvalue())
        self.assertEqual(json.loads(out.getvalue())['code'],'mirror-uri-invalid')

    def test_root_child_still_audits_and_checks_plan(self):
        mode=self.modes()[2];out=io.StringIO()
        with patch('sys.argv',['installer','--profile','DB',*mode,'--json']), \
             patch('cli.os.geteuid',return_value=0), \
             patch('privilege.interactive_execute') as authorize, \
             patch('cli.inventory',return_value=fixture()) as inventory, \
             patch('cli.read_json',side_effect=ValueError('saved-plan-integrity')) as read_plan, \
             patch('cli.LocalRunner') as runner,contextlib.redirect_stdout(out):
            self.assertEqual(main(),1)
        authorize.assert_not_called();inventory.assert_called_once()
        read_plan.assert_called_once_with('/root/private-plan/plan.json')
        runner.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())['code'],'saved-plan-integrity')

    def test_unprivileged_audit_does_not_authorize(self):
        out=io.StringIO()
        with patch('sys.argv',['installer','--profile','DB','--audit','--json']), \
             patch('cli.os.geteuid',return_value=1000), \
             patch('privilege.interactive_execute') as authorize, \
             patch('cli.inventory',return_value=fixture()) as inventory, \
             contextlib.redirect_stdout(out):
            self.assertEqual(main(),0)
        authorize.assert_not_called();inventory.assert_called_once()
        self.assertFalse(json.loads(out.getvalue())['installation_authorized'])


if __name__=='__main__':
    unittest.main()
