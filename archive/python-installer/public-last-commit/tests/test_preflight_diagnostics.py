"""Bounded failed audit IDs survive planning, preparation and CLI reporting."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_core import fixture
from test_workflow import lock_for, sources
from apply import authorized_resolution, request, run_apply
from cli import main, render_summary
from errors import PreflightError, WorkflowError, failure_metadata
from journal import private_directory
from workflow import build_workflow


class PreflightDiagnosticsTests(unittest.TestCase):
    def args(self, root):
        return argparse.Namespace(profile='DB',development=False,system_updates=False,
             allow_mirror=[],allow_proxy_env=False,no_wait_cloud_init=True,
             max_new_packages=1000,max_updates=100,npm_bundle=None,
             recovery_reviewed=False,state_dir=str(root/'state'))

    def test_only_fixed_ids_no_secret_details_in_metadata_or_summary(self):
        error=PreflightError({'checks':[
            {'id':'archive-key','status':'FAIL','detail':'private-password'},
            {'id':'https://operator:password@private.invalid','status':'FAIL'},
            {'id':['invalid'],'status':'FAIL'},
            {'id':'cpu','status':'PASS'}],
            'failures':['archive-key','package-source-inventory','token=PRIVATE_SECRET']})
        metadata=failure_metadata('resolve',error)
        self.assertEqual(metadata['failed_checks'],['archive-key','package-source-inventory'])
        report={'status':'FAIL','diagnostics':[metadata]}
        content=json.dumps(report)+render_summary(report)
        self.assertIn('Failed checks: archive-key, package-source-inventory',content)
        for secret in ('password','private.invalid','PRIVATE_SECRET'):
            self.assertNotIn(secret,content)
        metadata['failed_checks'].append('token=PRIVATE_SECRET')
        self.assertNotIn('PRIVATE_SECRET',render_summary(report))

    def test_workflow_error_contains_actual_failed_ids(self):
        data=fixture();data['ram_mib']=842
        with self.assertRaises(PreflightError) as error:
            build_workflow('DB',data,lock_for('DB'))
        self.assertEqual(error.exception.args,('preflight-failed',))
        self.assertEqual(error.exception.failed_checks,('ram_mib',))

    def test_initial_apply_failure_precedes_any_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=fixture();data['ram_mib']=842
            with self.assertRaises(PreflightError) as error:
                run_apply(self.args(root),data,root=root)
            self.assertEqual(error.exception.failed_checks,('ram_mib',))
            self.assertEqual(list(root.iterdir()),[])

    def test_preparation_journal_and_summary_preserve_failed_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);args=self.args(root)
            for path in root.rglob('*'):
                if path.is_file():path.chmod(0o644)
            data=dict(fixture(),target='offline-target')
            intent=request(args,data,root=root)
            directory=private_directory(root/'state')
            error=PreflightError({'checks':[{'id':'cached-signatures','status':'FAIL',
                                           'detail':'https://user:password@private.invalid'}]})
            with patch('apply.prepare_sources'),patch('apply.resolve',side_effect=error):
                with self.assertRaises(WorkflowError) as caught:
                    authorized_resolution(args,data,intent,directory,lambda argv:'',root)
            self.assertEqual(caught.exception.metadata['failed_checks'],['cached-signatures'])
            summary=(directory/'SUMMARY.txt').read_text()
            journal=(directory/'preparation/journal.json').read_text()
            self.assertIn('Failed checks: cached-signatures',summary)
            self.assertIn('cached-signatures',journal)
            for content in (summary,journal):
                self.assertNotIn('password',content);self.assertNotIn('private.invalid',content)

    def test_cli_json_preserves_ids_without_raw_detail(self):
        error=PreflightError({'checks':[{'id':'archive-key','status':'FAIL',
                                       'detail':'token=PRIVATE_SECRET'}]})
        out=io.StringIO()
        with patch('sys.argv',['installer','--profile','DB','--lock','offline.json','--json']), \
             patch('cli.inventory',return_value=fixture()), \
             patch('cli.read_json',return_value=lock_for('DB')), \
             patch('cli.build_workflow',side_effect=error), \
             contextlib.redirect_stdout(out):
            self.assertEqual(main(),1)
        result=json.loads(out.getvalue())
        self.assertEqual(result['diagnostics'][0]['failed_checks'],['archive-key'])
        self.assertNotIn('PRIVATE_SECRET',out.getvalue())


if __name__=='__main__':
    unittest.main()
