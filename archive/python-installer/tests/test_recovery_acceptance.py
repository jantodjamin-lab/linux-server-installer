"""Offline completed-plan and actual socket-policy safety regressions."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from apply import completed_checkpoint, fresh_target
from core import digest
from journal import Journal, run_workflow
from local import LocalRunner
from test_core import fixture
from test_workflow import lock_for, Runner
from workflow import build_workflow, validate_plan_age


class AcceptanceTests(unittest.TestCase):
    def test_expired_completed_checkpoint_requires_exact_secure_evidence(self):
        workflow=build_workflow('DB',fixture(),lock_for('DB'),created_at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
        with self.assertRaisesRegex(ValueError,'plan-expired'):validate_plan_age(workflow)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'checkpoints'
            self.assertFalse(completed_checkpoint(path,workflow))
            with Journal(path,workflow['plan_id']) as journal:
                journal.state['done']=[step['id'] for step in workflow['steps']]
                journal.event('VALIDATED','validate')
            self.assertTrue(completed_checkpoint(path,workflow))
            runner=Runner();runner.validate=lambda step:True;runner.apply=lambda step:self.fail('completed plan must never perform effects')
            self.assertEqual(run_workflow(workflow,runner,path)['status'],'PASS')
            original=(path/'journal.json').read_text()
            for field,value in [('pending','packages'),('done',[]),('binding','wrong')]:
                envelope=json.loads(original);envelope['state'][field]=value;envelope['sha256']=digest(envelope['state'])
                (path/'journal.json').write_text(json.dumps(envelope))
                self.assertFalse(completed_checkpoint(path,workflow))
            (path/'journal.json').write_text(original);(path/'journal.json').chmod(0o644)
            self.assertFalse(completed_checkpoint(path,workflow))
            (path/'journal.json').chmod(0o600)
            envelope=json.loads(original);envelope['sha256']='0'*64
            (path/'journal.json').write_text(json.dumps(envelope))
            self.assertFalse(completed_checkpoint(path,workflow))

    def test_socket_policy_preserves_other_services_and_rejects_external_managed_ports(self):
        runner=object.__new__(LocalRunner)
        for host in ('127.0.0.1','[::1]'):
            runner.call=lambda argv,host=host:'LISTEN 0 511 '+host+':8080 *:*\nLISTEN 0 128 0.0.0.0:22 *:*\n'
            self.assertTrue(runner.loopback_listener(8080))
        for host in ('0.0.0.0','[::]','192.0.2.4','*'):
            runner.call=lambda argv,host=host:'LISTEN 0 511 127.0.0.1:8080 *:*\nLISTEN 0 511 '+host+':8080 *:*\n'
            self.assertFalse(runner.loopback_listener(8080))
        runner.call=lambda argv:'LISTEN 0 128 0.0.0.0:22 *:*\n'
        self.assertFalse(runner.loopback_listener(5432))

    def test_partial_unowned_service_refused_without_changes_owned_resume_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'etc/postgresql';directory.mkdir(parents=True)
            evidence=directory/'untouched';evidence.write_text('preserve database')
            with self.assertRaisesRegex(ValueError,'existing-service-or-data-conflict'):fresh_target(root,{'profile':'DB'})
            self.assertEqual(evidence.read_text(),'preserve database')
            marker=root/'var/lib/universal-linux-installer/ownership.json';marker.parent.mkdir(parents=True)
            marker.write_text('{}');marker.chmod(0o600)
            self.assertTrue(fresh_target(root,{'profile':'DB'}))
            self.assertEqual(evidence.read_text(),'preserve database')
