"""Bulk dpkg snapshots retain exact pins without per-package subprocesses."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from local import LocalRunner


class SnapshotTests(unittest.TestCase):
    def checker(self,pins,rows='',simulation='',downgrade=False):
        runner=object.__new__(LocalRunner);runner.root='/fixture';runner.workflow={'arch':'x86_64'}
        calls=[]
        def call(argv):
            calls.append(argv)
            if argv[0].endswith('dpkg-query'):return rows
            if '--compare-versions' in argv and downgrade:raise RuntimeError('older')
            if argv[0].endswith('apt-get'):return simulation
            return ''
        runner.call=call;runner.check_sources=lambda:True
        return runner,calls

    def preflight(self,runner,pins):
        with patch('node.verify_key'),patch('node.verify_releases'),patch('node.package_records',return_value={}):
            return runner.package_preflight(pins)

    def test_400_pins_one_snapshot_and_fresh_validation(self):
        pins={'package-'+str(i):'1.0-1' for i in range(400)}
        rows=''.join(n+'\t'+v+'\tinstall ok installed\tamd64\n' for n,v in pins.items())
        runner,calls=self.checker(pins,rows)
        self.preflight(runner,pins)
        self.assertEqual(sum(a[0].endswith('dpkg-query') for a in calls),1)
        self.assertTrue(runner.validate({'kind':'apt','pins':pins}))
        self.assertEqual(sum(a[0].endswith('dpkg-query') for a in calls),2)
        runner.call=lambda argv:''
        self.assertFalse(runner.validate({'kind':'apt','pins':pins}))

    def test_downgrade_and_incomplete_simulation_still_refused(self):
        pins={'example':'1.0'}
        runner,_=self.checker(pins,'example\t2.0\tinstall ok installed\tamd64\n',downgrade=True)
        with self.assertRaisesRegex(ValueError,'package-downgrade-refused'):self.preflight(runner,pins)
        runner,_=self.checker(pins)
        with self.assertRaisesRegex(ValueError,'apt-simulation-incomplete'):self.preflight(runner,pins)
        runner,_=self.checker(pins,simulation='Inst example (1.0 Ubuntu [amd64])\n')
        self.preflight(runner,pins)

    def test_invalid_and_ambiguous_inventory_refused(self):
        for rows,code in [('bad-row','apt-simulation-format'),
                ('example\t1.0\tmalformed\tamd64\n','apt-simulation-format'),
                ('example\t1.0\tinstall ok installed\tarm64\n','foreign-architecture-package-refused'),
                ('example\t1.0\tinstall ok installed\tamd64\n'*2,'foreign-architecture-package-refused')]:
            runner,_=self.checker({'example':'1.0'},rows)
            with self.assertRaisesRegex(ValueError,code):runner.installed_snapshot({'example':'1.0'})
        runner,_=self.checker({'example':'1.0'},'example\t1.0\tinstall ok unpacked\tamd64\n')
        self.assertEqual(runner.installed_snapshot({'example':'1.0'}),{})
        runner,_=self.checker({'example':'1.0'},'example\t1.0\thold ok installed\tall\n')
        self.assertEqual(runner.installed_snapshot({'example':'1.0'}),{'example':'1.0'})

    def test_native_suffix_normalized_but_duplicate_bare_name_refused(self):
        runner,_=self.checker({'example':'1.0'},'example:amd64\t1.0\tinstall ok installed\tamd64\n')
        self.assertEqual(runner.installed_snapshot({'example':'1.0'}),{'example':'1.0'})
        runner,_=self.checker({'example':'1.0'},'example:amd64\t1.0\tinstall ok installed\tamd64\nexample\t1.0\tinstall ok installed\tamd64\n')
        with self.assertRaisesRegex(ValueError,'foreign-architecture-package-refused'):runner.installed_snapshot({'example':'1.0'})

    def test_held_installed_package_requires_explicit_update_opt_in(self):
        from test_rc5 import RC5ResolverTests
        from test_workflow import sources
        from test_core import fixture
        from resolve import resolve
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root)
            base,_=RC5ResolverTests().transport(root,'DB',installed={'git':'0.1'})
            def call(argv):
                result=base(argv)
                if argv[0].endswith('dpkg-query'):result=result.replace('git\t0.1\tinstall ok installed','git\t0.1\thold ok installed')
                return result
            with self.assertRaisesRegex(ValueError,'system-update-approval-required'):
                resolve('DB',fixture(),call,root=root,refresh_metadata=True)
            workflow=resolve('DB',fixture(),call,root=root,refresh_metadata=True,system_updates=True)
            self.assertIn('git',workflow['lock']['updates'])
            self.assertNotIn('git',workflow['lock']['apt'])
            self.assertEqual(workflow['resolution']['updates'],1)

    def test_audit_inventory_keeps_held_installed_version(self):
        from core import inventory
        from test_rc4 import audit_tree, Probe
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);probe=Probe()
            def call(argv):
                if argv[0].endswith('dpkg-query'):return 'git\t2.0-1\thold ok installed\n'
                return probe(argv)
            self.assertEqual(inventory(root,call)['packages']['git'],'2.0-1')
