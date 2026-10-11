import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infrastructure.installer import dry_run as d
from infrastructure.installer import preflight as p


class DryRunTests(unittest.TestCase):
    def evidence(self, profile='APP'):
        return p.evaluate(profile, {'os': {'ID': 'ubuntu'},
                                   'kernel': {'system': 'Linux', 'release': 'fictional'},
                                   'cpu': 1, 'memory': {'ram_mib': 843, 'swap_mib': 0},
                                   'disk': {'free_gib': 40}}, {})

    def setUp(self):
        d.STORE_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=d.STORE_ROOT)
        self.path = Path(self.temp.name) / 'owned'
        self.store = d.Journal(self.path, create=True)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def plan(self, profile='APP'):
        return d.build_dry_run(self.evidence(profile), 'fictional_target')

    def complete(self, store, task):
        store.start(task)
        while store.advance(task) == 'RUNNING':
            pass

    def test_profiles_order_privileges_and_no_actions(self):
        with patch.object(p, 'collect', side_effect=AssertionError('probe')), \
             patch.object(p.subprocess, 'run', side_effect=AssertionError('command')), \
             patch('socket.socket', side_effect=AssertionError('network')):
            for profile, count in [('APP', 4), ('DB', 4), ('APP-DB', 6)]:
                plan = self.plan(profile)
                task = self.store.create_task(plan)
                self.complete(self.store, task)
                snapshot = self.store.snapshot(task)
                self.assertEqual(snapshot['state'], 'SIMULATED')
                self.assertFalse(snapshot['executable'])
                self.assertFalse(snapshot['installation_authorized'])
                events = [e['step'] for e in snapshot['events'] if e['event'] == 'SIMULATED']
                self.assertEqual(events, [s['id'] for s in plan['steps']])
                self.assertEqual(len(events), count)
                seen = set()
                for step in plan['steps']:
                    self.assertLessEqual(set(step['depends_on']), seen)
                    self.assertTrue(step['required_privileges'])
                    self.assertFalse(step['privileges_granted'])
                    seen.add(step['id'])

    def test_binding_determinism_and_no_input_mutation(self):
        evidence = self.evidence()
        before = copy.deepcopy(evidence)
        first = d.build_dry_run(evidence, 'fixture')
        self.assertEqual(first, d.build_dry_run(json.loads(json.dumps(evidence)), 'fixture'))
        self.assertEqual(evidence, before)
        self.assertNotEqual(first['plan_id'], d.build_dry_run(evidence, 'other_fixture')['plan_id'])
        self.assertEqual(len({s['idempotency_key'] for s in first['steps']}), len(first['steps']))
        self.assertEqual(first, d.validate_plan(first))

    def test_duplicate_creation_and_completion(self):
        plan = self.plan()
        task = self.store.create_task(plan)
        self.assertEqual(task, self.store.create_task(plan))
        self.complete(self.store, task)
        before = self.store.snapshot(task)
        self.assertEqual(task, self.store.create_task(plan))
        for action in (self.store.start, self.store.advance):
            with self.assertRaises(ValueError):
                action(task)
        self.assertEqual(before, self.store.snapshot(task))

    def test_interruption_requires_review_and_preserves_completed_steps(self):
        task = self.store.create_task(self.plan('APP-DB'))
        self.store.start(task)
        self.store.advance(task)
        self.store.interrupt(task)
        self.assertEqual(self.store.snapshot(task)['state'], 'INTERRUPTED')
        with self.assertRaises(ValueError):
            self.store.start(task)
        with self.assertRaises(ValueError):
            self.store.recover(task)
        self.store.recover(task, review_acknowledged=True)
        self.complete(self.store, task)
        steps = [e['step'] for e in self.store.snapshot(task)['events'] if e['event'] == 'SIMULATED']
        self.assertEqual(len(steps), 6)
        self.assertEqual(len(set(steps)), 6)

    def test_restart_recovery_and_stale_owner_fencing(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        restarted = d.Journal(self.path)
        try:
            self.assertEqual(restarted.snapshot(task)['state'], 'RUNNING')
            with self.assertRaises(ValueError):
                restarted.advance(task)
            restarted.recover(task, review_acknowledged=True)
            restarted.start(task)
            with self.assertRaises(ValueError):
                self.store.advance(task)
            while restarted.advance(task) == 'RUNNING':
                pass
            snapshot = restarted.snapshot(task)
            self.assertEqual(snapshot['state'], 'SIMULATED')
            self.assertIn('INTERRUPTED', [e['event'] for e in snapshot['events']])
        finally:
            restarted.close()
        self.store.close()
        self.store = d.Journal(self.path)
        self.assertEqual(self.store.snapshot(task), snapshot)

    def test_failure_is_durable_and_retry_is_explicit(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        self.assertEqual(self.store.advance(task, simulate_failure=True), 'FAILED')
        self.store.close()
        self.store = d.Journal(self.path)
        self.assertEqual(self.store.snapshot(task)['state'], 'FAILED')
        with self.assertRaises(ValueError):
            self.store.advance(task)
        self.store.recover(task, review_acknowledged=True)
        self.complete(self.store, task)
        events = self.store.snapshot(task)['events']
        self.assertEqual(len([e for e in events if e['event'] == 'SIMULATED']), 4)
        self.assertEqual([e['code'] for e in events if e['event'] == 'FAILED'], ['SIMULATED_FAILURE'])

    def test_transaction_rollback_keeps_state_and_events_together(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        before = self.store.snapshot(task)
        original = self.store._event

        def interrupted_write(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('fictional storage failure')
        with patch.object(self.store, '_event', side_effect=interrupted_write):
            with self.assertRaises(RuntimeError):
                self.store.advance(task)
        self.assertEqual(self.store.snapshot(task), before)
        self.store.advance(task)

    def test_fail_preflight_blocks_simulation(self):
        evidence = p.evaluate('APP', {'cpu': 0}, {})
        task = self.store.create_task(d.build_dry_run(evidence, 'fixture'))
        self.assertEqual(self.store.snapshot(task)['state'], 'BLOCKED')
        with self.assertRaises(ValueError):
            self.store.start(task)
        with self.assertRaises(ValueError):
            self.store.recover(task, review_acknowledged=True)

    def test_invalid_payloads_bindings_and_dependency_cycles(self):
        plan = self.plan()
        changes = [lambda x: x.update(executable=True),
                   lambda x: x['steps'][0].update(command='fictional shell'),
                   lambda x: x['steps'][0].update(depends_on=['final-review']),
                   lambda x: x['steps'][1].update(id='review'),
                   lambda x: x['steps'][1].update(required_privileges=[]),
                   lambda x: x.update(plan_id='bad'),
                   lambda x: x['steps'][0].update(idempotency_key='bad')]
        for change in changes:
            bad = copy.deepcopy(plan)
            change(bad)
            with self.assertRaises(ValueError):
                self.store.create_task(bad)
        for bad in (None, {}, {'steps': None}):
            with self.assertRaises(ValueError):
                d.validate_plan(bad)
        with self.assertRaises(ValueError):
            d.build_dry_run(self.evidence(), 'host.example.com')

    def test_protected_paths_existing_files_and_symlinks_rejected(self):
        for path in (d.ROOT / 'references' / 'fictional',
                     d.ROOT / 'docs' / 'installer' / 'evidence' / 'fictional',
                     d.STORE_ROOT, Path('/tmp/fictional-journal')):
            with self.assertRaises(ValueError):
                d.Journal(path, create=True)
        with self.assertRaises(FileExistsError):
            d.Journal(self.path, create=True)
        link = Path(self.temp.name) / 'link'
        link.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(ValueError):
            d.Journal(link)
        with self.assertRaises(ValueError):
            d.Journal(Path(self.temp.name) / 'absent')


if __name__ == '__main__':
    unittest.main()
