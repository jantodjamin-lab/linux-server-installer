"""Iteration 3: isolated Python processes and fictional journal failures only."""
import multiprocessing
import os
import sqlite3
import unittest
from unittest.mock import patch

import test_dry_run as fixtures
from infrastructure.installer import dry_run as d


def contender(path, task, barrier, results):
    journal = d.Journal(path)
    try:
        barrier.wait(timeout=10)
        try:
            journal.start(task)
            journal.advance(task)
            results.put('claimed')
        except ValueError:
            results.put('refused')
    finally:
        journal.close()


def lock_holder(path, ready, release):
    journal = d.Journal(path)
    journal.db.execute('BEGIN IMMEDIATE')
    ready.set()
    release.wait(10)
    os._exit(24)  # OS releases SQLite lock; persistent task owner stays uncertain.


def crash_review(path, task):
    journal = d.Journal(path)
    original = journal._seal

    def crash():
        original()
        os._exit(25)
    journal._seal = crash
    journal.recover(task, review_acknowledged=True)


class FinalTests(unittest.TestCase):
    evidence = fixtures.DryRunTests.evidence
    setUp = fixtures.DryRunTests.setUp
    tearDown = fixtures.DryRunTests.tearDown
    plan = fixtures.DryRunTests.plan
    complete = fixtures.DryRunTests.complete

    def finish_process(self, process, expected):
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
            self.fail('Python fault fixture timed out')
        self.assertEqual(process.exitcode, expected)

    def test_process_race_has_one_claim_and_no_duplicate_completion(self):
        context = multiprocessing.get_context('spawn')
        task = self.store.create_task(self.plan())
        barrier, results = context.Barrier(2), context.Queue()
        processes = [context.Process(target=contender, args=(self.path, task, barrier, results))
                     for _ in range(2)]
        try:
            for process in processes:
                process.start()
            for process in processes:
                self.finish_process(process, 0)
            self.assertEqual(sorted(results.get(timeout=5) for _ in processes), ['claimed', 'refused'])
            before = self.store.snapshot(task)
            self.assertEqual(sum(e['event'] == 'STARTED' for e in before['events']), 1)
            with self.assertRaises(ValueError):
                self.store.advance(task)
            self.assertEqual(before, self.store.snapshot(task))
            self.store.recover(task, review_acknowledged=True)
            self.complete(self.store, task)
            steps = [e['step'] for e in self.store.snapshot(task)['events'] if e['event'] == 'SIMULATED']
            self.assertEqual(steps, [s['id'] for s in self.plan()['steps']])
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            results.close()
            results.join_thread()

    def test_dead_lock_owner_does_not_release_uncertain_task(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        self.store.close()
        self.store = d.Journal(self.path)
        before = self.store.snapshot(task)
        context = multiprocessing.get_context('spawn')
        ready, release = context.Event(), context.Event()
        process = context.Process(target=lock_holder, args=(self.path, ready, release))
        process.start()
        try:
            self.assertTrue(ready.wait(10))
            self.store.db.execute('PRAGMA busy_timeout=1')
            with self.assertRaises(sqlite3.OperationalError):
                self.store.recover(task, review_acknowledged=True)
            release.set()
            self.finish_process(process, 24)
            self.assertEqual(self.store.snapshot(task), before)
            with self.assertRaises(ValueError):
                self.store.advance(task)
            with self.assertRaises(ValueError):
                self.store.recover(task)
            self.assertEqual(self.store.snapshot(task), before)
            self.store.recover(task, review_acknowledged=True)
            self.complete(self.store, task)
        finally:
            release.set()
            if process.is_alive():
                process.terminate()
                process.join(5)

    def test_uncommitted_human_review_never_authorizes_resume(self):
        task = self.store.create_task(self.plan())
        self.store.start(task)
        self.store.advance(task)
        before = self.store.snapshot(task)
        self.store.close()
        context = multiprocessing.get_context('spawn')
        process = context.Process(target=crash_review, args=(self.path, task))
        process.start()
        self.finish_process(process, 25)
        self.store = d.Journal(self.path)
        self.assertEqual(self.store.snapshot(task), before)
        with self.assertRaises(ValueError):
            self.store.advance(task)
        with self.assertRaises(ValueError):
            self.store.recover(task)
        self.store.recover(task, review_acknowledged=True)
        reviewed = self.store.snapshot(task)
        self.assertEqual(reviewed['state'], 'PENDING')
        self.assertEqual(sum(e['event'] == 'RECOVERY_REVIEWED' for e in reviewed['events']), 1)
        self.store.close()  # Server restart model after durable review, before start.
        self.store = d.Journal(self.path)
        self.assertEqual(self.store.snapshot(task), reviewed)
        with self.assertRaises(ValueError):
            self.store.advance(task)
        self.complete(self.store, task)

    def test_uncertain_target_blocks_other_plans_until_durable_review(self):
        for failure in (False, True):
            path = self.path.parent / ('uncertain-' + str(failure))
            journal = d.Journal(path, create=True)
            try:
                task = journal.create_task(self.plan())
                second = journal.create_task(self.plan('DB'))
                journal.start(task)
                if failure:
                    journal.advance(task, simulate_failure=True)
                else:
                    journal.interrupt(task)
                before = journal.snapshot(second)
                with self.assertRaises(ValueError):
                    journal.start(second)
                self.assertEqual(journal.snapshot(second), before)
                original = journal._seal

                def failed_write():
                    original()
                    raise sqlite3.OperationalError('fictional partial review write')
                with patch.object(journal, '_seal', side_effect=failed_write):
                    with self.assertRaises(sqlite3.OperationalError):
                        journal.recover(task, review_acknowledged=True)
                with self.assertRaises(ValueError):
                    journal.start(second)
                journal.recover(task, review_acknowledged=True)
                journal.start(second)
                with self.assertRaises(ValueError):
                    journal.start(task)
            finally:
                journal.close()

    def test_truncated_database_and_orphan_event_fail_closed(self):
        for corruption in ('truncate', 'orphan'):
            path = self.path.parent / corruption
            journal = d.Journal(path, create=True)
            task = journal.create_task(self.plan())
            journal.start(task)
            if corruption == 'orphan':
                journal.db.execute("INSERT INTO events(task,event) VALUES ('missing','STARTED')")
                with self.assertRaises(ValueError):
                    journal.recover(task, review_acknowledged=True)
            journal.close()
            database = path / 'journal.sqlite3'
            if corruption == 'truncate':
                data = database.read_bytes()
                database.write_bytes(data[:len(data)//2])
            before = database.read_bytes()
            for approval in (False, True):
                with self.assertRaises((ValueError, sqlite3.DatabaseError)):
                    d.Journal(path, approve_legacy_upgrade=approval)
                self.assertEqual(database.read_bytes(), before)
