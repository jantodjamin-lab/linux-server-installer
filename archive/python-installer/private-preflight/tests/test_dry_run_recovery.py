"""Local fault injection only: forked Python fixtures, no command executor."""
import multiprocessing
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import unittest
import test_dry_run as fixtures
from infrastructure.installer import dry_run as d


def crash_fixture(path, task, committed):
    journal = d.Journal(path)
    journal.recover(task, review_acknowledged=True)
    journal.start(task)
    if committed:
        journal.advance(task)
    else:
        original = journal._seal

        def stop_before_commit():
            original()
            os._exit(23)
        journal._seal = stop_before_commit
        journal.advance(task)
    os._exit(23)


class RecoveryTests(unittest.TestCase):
    evidence = fixtures.DryRunTests.evidence
    setUp = fixtures.DryRunTests.setUp
    tearDown = fixtures.DryRunTests.tearDown
    plan = fixtures.DryRunTests.plan
    complete = fixtures.DryRunTests.complete

    def test_legacy_upgrade_is_explicit_and_preserves_checkpoints(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        before = self.store.snapshot(task)
        self.store.db.execute('DROP TABLE seals')
        self.store.db.execute('PRAGMA user_version=1')
        self.store.close()
        with self.assertRaises(ValueError):
            d.Journal(self.path)
        self.store = d.Journal(self.path, approve_legacy_upgrade=True)
        self.assertEqual(self.store.snapshot(task), before)
        with self.assertRaises(ValueError):
            self.store.advance(task)
        self.store.recover(task, review_acknowledged=True)
        self.complete(self.store, task)
    def test_process_loss_before_and_after_commit(self):
        for committed in (False, True):
            path = self.path.parent / ('crash-' + str(committed))
            journal = d.Journal(path, create=True)
            task = journal.create_task(self.plan())
            journal.start(task)
            journal.close()
            process = multiprocessing.get_context('fork').Process(
                target=crash_fixture, args=(path, task, committed))
            process.start()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join()
                self.fail('Fault fixture did not exit')
            self.assertEqual(process.exitcode, 23)
            journal = d.Journal(path)
            try:
                snapshot = journal.snapshot(task)
                self.assertEqual(snapshot['state'], 'RUNNING')
                self.assertEqual(sum(e['event'] == 'SIMULATED' for e in snapshot['events']), int(committed))
                with self.assertRaises(ValueError):
                    journal.advance(task)
                with self.assertRaises(ValueError):
                    journal.recover(task)
                journal.recover(task, review_acknowledged=True)
                self.complete(journal, task)
                events = journal.snapshot(task)['events']
                steps = [e['step'] for e in events if e['event'] == 'SIMULATED']
                self.assertEqual(steps, [s['id'] for s in self.plan()['steps']])
            finally:
                journal.close()

    def test_seal_write_failure_rolls_back_status_and_history(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        before = self.store.snapshot(task)
        original = self.store._seal

        def fail():
            original()
            raise sqlite3.OperationalError('fictional disk full')
        with patch.object(self.store, '_seal', side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.advance(task)
        self.assertEqual(self.store.snapshot(task), before)

    def test_corruption_blocks_reads_mutations_and_recovery(self):
        mutations = ["UPDATE tasks SET state='SIMULATED'",
                     "DELETE FROM events", "UPDATE events SET code='changed'",
                     "UPDATE tasks SET owner='changed'",
                     "UPDATE tasks SET plan_id='changed'",
                     "DELETE FROM seals"]
        for index, sql in enumerate(mutations):
            path = self.path.parent / ('corrupt-' + str(index))
            journal = d.Journal(path, create=True)
            task = journal.create_task(self.plan())
            journal.start(task)
            journal.db.execute(sql)
            for action in (journal.snapshot, journal.advance,
                           lambda t: journal.recover(t, review_acknowledged=True)):
                with self.assertRaises(ValueError):
                    action(task)
            journal.close()
            with self.assertRaises(ValueError):
                d.Journal(path)

    def test_two_connections_duplicate_and_target_claim(self):
        other = d.Journal(self.path)
        try:
            plan = self.plan()
            task = self.store.create_task(plan)
            self.assertEqual(task, other.create_task(plan))
            changed = self.evidence('DB')
            second = other.create_task(d.build_dry_run(changed, 'fictional_target'))
            self.store.start(task)
            with self.assertRaises(ValueError):
                other.start(task)
            with self.assertRaises(ValueError):
                other.start(second)
            with self.assertRaises(ValueError):
                other.advance(task)
            other.db.execute('BEGIN IMMEDIATE')
            self.store.db.execute('PRAGMA busy_timeout=1')
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    self.store.advance(task)
            finally:
                other.db.execute('ROLLBACK')
            self.store.interrupt(task)
            with self.assertRaises(ValueError):
                other.start(second)
            self.store.recover(task, review_acknowledged=True)
            other.start(second)
        finally:
            other.close()

    def test_disconnect_and_restart_need_literal_human_ack(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        self.store.close()  # Lost connection/server restart fixture, no remote actions.
        self.store = d.Journal(self.path)
        before = self.store.snapshot(task)
        for ack in (False, None, 1, 'yes'):
            with self.assertRaises(ValueError):
                self.store.recover(task, review_acknowledged=ack)
        self.assertEqual(before, self.store.snapshot(task))
        self.store.recover(task, review_acknowledged=True)
        self.assertEqual(self.store.snapshot(task)['state'], 'PENDING')
        with self.assertRaises(ValueError):
            self.store.advance(task)
        self.complete(self.store, task)

    def test_simultaneous_starts_have_one_owner(self):
        task = self.store.create_task(self.plan())
        barrier = threading.Barrier(2)

        def contender():
            journal = d.Journal(self.path)
            try:
                barrier.wait(timeout=5)
                try:
                    journal.start(task)
                    journal.advance(task)
                    return 'claimed'
                except ValueError:
                    return 'refused'
            finally:
                journal.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            self.assertEqual(sorted(f.result(timeout=10) for f in futures), ['claimed', 'refused'])
        events = self.store.snapshot(task)['events']
        self.assertEqual(sum(e['event'] == 'STARTED' for e in events), 1)
        self.assertEqual(sum(e['event'] == 'SIMULATED' for e in events), 1)
