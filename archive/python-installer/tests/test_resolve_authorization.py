"""Resolve-only metadata approval never authorizes APT source configuration edits."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_core import fixture
from test_workflow import sources
from test_rc4 import Probe, snapshot
from apply import authorized_resolution, request, request_summary
from errors import PackageError, WorkflowError
from journal import Journal, private_directory


class ResolveAuthorizationTests(unittest.TestCase):
    def setup(self, root, mode='resolve'):
        sources(root)
        path=root/'etc/apt/sources.list.d/ubuntu.sources'
        path.write_text(path.read_text().replace('Components: main universe','Components: main'))
        args=argparse.Namespace(profile='APP',development=False,system_updates=False,
             allow_mirror=[],allow_proxy_env=False,no_wait_cloud_init=True,
             max_new_packages=1000,max_updates=100,npm_bundle=None,recovery_reviewed=False)
        data=dict(fixture(),target='offline-target')
        return args,data,request(args,data,mode=mode,root=root)

    def test_missing_universe_resolve_never_edits_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args,data,intent=self.setup(root)
            before=snapshot(root/'etc/apt');directory=private_directory(root/'state')
            def unavailable(*args,**kwargs):
                self.assertTrue(kwargs['refresh_metadata'])
                self.assertEqual(before,snapshot(root/'etc/apt'))
                raise PackageError('nodejs')
            with patch('apply.prepare_sources') as prepare,patch('apply.resolve',side_effect=unavailable):
                with self.assertRaises(WorkflowError) as error:
                    authorized_resolution(args,data,intent,directory,Probe(),root)
            prepare.assert_not_called()
            self.assertEqual(before,snapshot(root/'etc/apt'))
            self.assertEqual(error.exception.metadata['code'],'pinned-package-unavailable')
            self.assertEqual(error.exception.metadata['package'],'nodejs')
            self.assertFalse((root/'etc/apt/sources.list.d/universal-node-universe.sources').exists())
            self.assertIn('configuration remains unchanged',request_summary(intent,data))
            self.assertNotIn('may be appended',request_summary(intent,data))

    def test_resolve_source_failure_autoclears_and_retries_without_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args,data,intent=self.setup(root)
            directory=private_directory(root/'state');before=snapshot(root/'etc/apt')
            def no_key(argv):
                if Path(argv[0]).name=='gpg':raise FileNotFoundError()
                return Probe()(argv)
            with self.assertRaises(WorkflowError) as error:
                authorized_resolution(args,data,intent,directory,no_key,root)
            self.assertEqual(error.exception.metadata['code'],'archive-key-gpg-required')
            state=json.loads((directory/'preparation/journal.json').read_text())['state']
            self.assertIsNone(state['pending'])
            self.assertEqual(state['events'][-1]['event'],'AUTO_CLEARED')
            with patch('apply.resolve',side_effect=PackageError('nodejs')):
                with self.assertRaises(WorkflowError) as resumed:
                    authorized_resolution(args,data,intent,directory,Probe(),root)
            self.assertEqual(resumed.exception.metadata['code'],'pinned-package-unavailable')
            self.assertEqual(before,snapshot(root/'etc/apt'))

    def test_interrupted_resolve_source_stage_needs_no_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args,data,intent=self.setup(root)
            directory=private_directory(root/'state')
            with Journal(directory/'preparation',intent['request_id']) as journal:
                journal.state['pending']='sources';journal.event('STARTED','sources')
            with patch('apply.resolve',side_effect=PackageError('nodejs')):
                with self.assertRaises(WorkflowError):
                    authorized_resolution(args,data,intent,directory,Probe(),root)
            events=json.loads((directory/'preparation/journal.json').read_text())['state']['events']
            self.assertTrue(any(row['event']=='AUTO_CLEARED' and row['step']=='sources' for row in events))

    def test_apply_source_interruption_remains_effectful(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args,data,intent=self.setup(root,'apply')
            directory=private_directory(root/'state');before=snapshot(root/'etc/apt')
            with Journal(directory/'preparation',intent['request_id']) as journal:
                journal.state['pending']='sources';journal.event('STARTED','sources')
            with self.assertRaisesRegex(ValueError,'uncertain-effects-review-required'):
                authorized_resolution(args,data,intent,directory,Probe(),root)
            self.assertEqual(before,snapshot(root/'etc/apt'))
            self.assertIn('may be appended',request_summary(intent,data))


if __name__=='__main__':
    unittest.main()
