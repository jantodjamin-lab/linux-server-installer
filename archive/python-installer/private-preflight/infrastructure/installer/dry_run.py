"""Offline state simulation only. No execution adapters or command payloads.

SQLite transactions commit task state and journal entries together. The sole
write destination is a newly owned directory below logs/wp002.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from infrastructure.installer.plan import build_plan, canonical

ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = ROOT / 'logs' / 'wp002'
APP_ID = 0x57503032


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_dry_run(evidence, simulation_target):
    """Pure builder; target is a fictional label, never a hostname/address."""
    if not isinstance(simulation_target, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', simulation_target):
        raise ValueError('Expected bounded fictional target label')
    review = build_plan(evidence)
    steps = []

    def add(name, dependencies, privileges, conditions):
        steps.append({'id': name, 'depends_on': dependencies,
                      'required_privileges': privileges, 'privileges_granted': False,
                      'preconditions': conditions,
                      'postconditions': ['record simulated completion only'],
                      'operation': 'describe-only'})

    add('review', [], ['none: local simulation'], review['stop_conditions'])
    for component in review['components']:
        role = component['role'].lower()
        add(role + '.prepare', ['review'], component['required_privileges'], component['preconditions'])
        add(role + '.validate', [role + '.prepare'], ['none: independent validation design'], component['postconditions'])
    # Combined profile validates the connection contract only after both roles.
    add('final-review', [c['role'].lower() + '.validate' for c in review['components']],
        ['none: local simulation'], ['review all OPEN decisions; no installation GO'])
    result = {'schema_version': 1, 'kind': 'offline-dry-run', 'profile': review['profile'],
              'simulation_target': simulation_target, 'review_contract': review,
              'installation_authorized': False, 'executable': False, 'steps': steps}
    result['plan_id'] = digest(result)
    for step in steps:
        step['idempotency_key'] = digest({'plan_id': result['plan_id'], 'step': step})
    return result


def validate_plan(plan):
    """Strict input: only the builder's declarative schema is accepted."""
    if not isinstance(plan, dict):
        raise ValueError('Expected dry-run plan')
    try:
        raw = json.loads(canonical(plan))
        keys = {'schema_version', 'kind', 'profile', 'simulation_target', 'review_contract',
                'installation_authorized', 'executable', 'steps', 'plan_id'}
        if set(raw) != keys or raw['schema_version'] != 1 or raw['kind'] != 'offline-dry-run':
            raise ValueError('Invalid dry-run schema')
        if raw['installation_authorized'] is not False or raw['executable'] is not False:
            raise ValueError('Execution disabled')
        review = raw['review_contract']
        if review['kind'] != 'installation-review-contract' or review['executable'] is not False or review['installation_authorized'] is not False:
            raise ValueError('Invalid review contract')
        if raw['profile'] not in ('APP', 'DB', 'APP-DB') or raw['profile'] != review['profile']:
            raise ValueError('Invalid profile')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', raw['simulation_target']):
            raise ValueError('Invalid target label')
        plan_id = raw.pop('plan_id')
        seen = set()
        for step in raw['steps']:
            key = step.pop('idempotency_key')
            if set(step) != {'id', 'depends_on', 'required_privileges', 'privileges_granted',
                             'preconditions', 'postconditions', 'operation'}:
                raise ValueError('Unexpected step field')
            if step['operation'] != 'describe-only' or step['privileges_granted'] is not False:
                raise ValueError('Execution disabled')
            if not isinstance(step['id'], str) or step['id'] in seen:
                raise ValueError('Duplicate/invalid step')
            if any(not isinstance(step[field], list) or not all(isinstance(v, str) and v for v in step[field])
                   for field in ('depends_on', 'required_privileges', 'preconditions', 'postconditions')):
                raise ValueError('Invalid declarations')
            if not step['required_privileges'] or not set(step['depends_on']) <= seen:
                raise ValueError('Missing privilege or invalid dependency order/cycle')
            seen.add(step['id'])
            if key != digest({'plan_id': plan_id, 'step': step}):
                raise ValueError('Invalid step binding')
        if not seen or digest(raw) != plan_id:
            raise ValueError('Invalid plan binding')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed dry-run plan') from exc
    return json.loads(canonical(plan))


class Journal:
    """One local SQLite store. Caller closes it; reopening never auto-recovers.

    Transactions serialize writers. No arbitrary file destination, callback,
    worker, subprocess, network client, or live execution mode is exposed.
    """
    def __init__(self, directory, *, create=False, approve_legacy_upgrade=False):
        self.session = str(uuid4())
        directory = Path(directory).absolute()
        # Refuse symlink components, including a redirected logs directory.
        if any(p.is_symlink() for p in (directory, *directory.parents)):
            raise ValueError('Symlink journal paths forbidden')
        directory = directory.resolve()
        if not directory.is_relative_to(STORE_ROOT) or directory == STORE_ROOT:
            raise ValueError('Journal must own a directory below logs/wp002')
        if create:
            STORE_ROOT.mkdir(parents=True, exist_ok=True)
            directory.mkdir(mode=0o700)  # Exclusive: never adopt existing evidence.
        path = directory / 'journal.sqlite3'
        if path.is_symlink() or (not create and not path.is_file()):
            raise ValueError('Missing or unsafe journal')
        self.db = sqlite3.connect(path.as_uri() + '?mode=rw' if not create else str(path),
                                  uri=not create, isolation_level=None)
        try:
            self.db.execute('PRAGMA synchronous=FULL')
            if not create and approve_legacy_upgrade is True:
                if (self.db.execute('PRAGMA application_id').fetchone()[0] == APP_ID and
                        self.db.execute('PRAGMA user_version').fetchone()[0] == 1 and
                        self.db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'):
                    # Explicitly approved baseline of legacy bytes, not proof of their history.
                    self.db.execute('BEGIN IMMEDIATE')
                    try:
                        self.db.execute('CREATE TABLE seals (task TEXT PRIMARY KEY, checksum TEXT NOT NULL)')
                        self._seal()
                        self.db.execute('PRAGMA user_version=2')
                        self.db.execute('COMMIT')
                    except BaseException:
                        self.db.execute('ROLLBACK')
                        raise
            if create:
                self.db.executescript(f'''
                    PRAGMA application_id={APP_ID};
                    PRAGMA user_version=2;
                    CREATE TABLE tasks (id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL,
                                        plan TEXT NOT NULL, state TEXT NOT NULL, owner TEXT);
                    CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT,
                                         task TEXT NOT NULL, event TEXT NOT NULL,
                                         step TEXT, code TEXT,
                                         timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
                    CREATE TABLE seals (task TEXT PRIMARY KEY, checksum TEXT NOT NULL);
                ''')
            elif (self.db.execute('PRAGMA application_id').fetchone()[0] != APP_ID or
                  self.db.execute('PRAGMA user_version').fetchone()[0] != 2 or
                  self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok'):
                raise ValueError('Invalid journal format/integrity')
            self._change(lambda: None)
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _event(self, task, event, step=None, code=None):
        self.db.execute('INSERT INTO events(task,event,step,code) VALUES (?,?,?,?)',
                        (task, event, step, code))

    def _change(self, function):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self._verify()
            result = function()
            self._seal()
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _checksums(self):
        """Bind complete state and ordered history; not an external trust anchor."""
        checksums = {}
        for row in self.db.execute('SELECT id,plan_id,plan,state,owner FROM tasks ORDER BY id'):
            plan = validate_plan(json.loads(row[2]))
            if row[1] != plan['plan_id']:
                raise ValueError('Journal plan binding mismatch')
            events = list(self.db.execute(
                'SELECT seq,event,step,code,timestamp FROM events WHERE task=? ORDER BY seq', (row[0],)))
            checksums[row[0]] = digest({'task': row, 'events': events})
        if self.db.execute('SELECT COUNT(*) FROM events WHERE task NOT IN (SELECT id FROM tasks)').fetchone()[0]:
            raise ValueError('Orphan journal events')
        return checksums

    def _verify(self):
        if self._checksums() != dict(self.db.execute('SELECT task,checksum FROM seals')):
            raise ValueError('Journal state/history integrity mismatch; recovery forbidden')

    def _seal(self):
        for task, checksum in self._checksums().items():
            self.db.execute('INSERT INTO seals VALUES (?,?) ON CONFLICT(task) DO UPDATE SET checksum=excluded.checksum WHERE checksum<>excluded.checksum',
                            (task, checksum))

    def create_task(self, plan):
        plan = validate_plan(plan)

        def change():
            existing = self.db.execute('SELECT id FROM tasks WHERE plan_id=?', (plan['plan_id'],)).fetchone()
            if existing:
                return existing[0]  # Same plan/target: same task, no duplicate events.
            task = str(uuid4())
            state = 'BLOCKED' if plan['review_contract']['status'] == 'FAIL' else 'PENDING'
            self.db.execute('INSERT INTO tasks VALUES (?,?,?,?,NULL)', (task, plan['plan_id'], canonical(plan), state))
            self._event(task, 'CREATED', code=state)
            return task
        return self._change(change)

    def _task(self, task):
        row = self.db.execute('SELECT plan,state FROM tasks WHERE id=?', (task,)).fetchone()
        if row is None:
            raise ValueError('Unknown task')
        return validate_plan(json.loads(row[0])), row[1]

    def snapshot(self, task):
        def read():
            plan, state = self._task(task)
            events = [dict(zip(('sequence', 'event', 'step', 'code', 'timestamp_utc'), row))
                      for row in self.db.execute('SELECT seq,event,step,code,timestamp FROM events WHERE task=? ORDER BY seq', (task,))]
            return {'task_id': task, 'state': state, 'mode': 'dry-run',
                    'installation_authorized': False, 'executable': False,
                    'plan_id': plan['plan_id'], 'events': events}
        return self._change(read)

    def start(self, task):
        def change():
            plan, state = self._task(task)
            if state != 'PENDING':
                raise ValueError('Task requires PENDING; explicit recovery if interrupted')
            for other, serialized in self.db.execute(
                    "SELECT id,plan FROM tasks WHERE state IN ('RUNNING','INTERRUPTED','FAILED') AND id<>?", (task,)):
                if json.loads(serialized)['simulation_target'] == plan['simulation_target']:
                    raise ValueError('Target claimed or uncertain; explicit recovery review required')
            self.db.execute('UPDATE tasks SET state=?,owner=? WHERE id=?', ('RUNNING', self.session, task))
            self._event(task, 'STARTED')
        self._change(change)

    def advance(self, task, *, simulate_failure=False):
        """Commit at most one fictional step. No callbacks or effects."""
        if type(simulate_failure) is not bool:
            raise ValueError('Expected boolean fixture failure')

        def change():
            plan, state = self._task(task)
            if state != 'RUNNING':
                raise ValueError('Task is not RUNNING')
            if self.db.execute('SELECT owner FROM tasks WHERE id=?', (task,)).fetchone()[0] != self.session:
                raise ValueError('Stale or foreign simulation session')
            done = {row[0] for row in self.db.execute('SELECT step FROM events WHERE task=? AND event=?', (task, 'SIMULATED'))}
            step = next((s for s in plan['steps'] if s['id'] not in done), None)
            if step is None or not set(step['depends_on']) <= done:
                raise ValueError('Journal/dependency inconsistency')
            if simulate_failure:
                self._event(task, 'FAILED', step['id'], 'SIMULATED_FAILURE')
                state = 'FAILED'
            else:
                self._event(task, 'SIMULATED', step['id'], step['idempotency_key'])
                state = 'SIMULATED' if len(done) + 1 == len(plan['steps']) else 'RUNNING'
            self.db.execute('UPDATE tasks SET state=? WHERE id=?', (state, task))
            return state
        return self._change(change)

    def interrupt(self, task):
        def change():
            _, state = self._task(task)
            if state != 'RUNNING':
                raise ValueError('Only RUNNING can be interrupted')
            if self.db.execute('SELECT owner FROM tasks WHERE id=?', (task,)).fetchone()[0] != self.session:
                raise ValueError('Stale or foreign simulation session')
            self.db.execute('UPDATE tasks SET state=? WHERE id=?', ('INTERRUPTED', task))
            self._event(task, 'INTERRUPTED')
        self._change(change)

    def recover(self, task, *, review_acknowledged=False):
        """Explicit offline recovery only, after closing any previous owner.

        RUNNING on reopen is uncertain: record interruption before resuming.
        A boolean acknowledgement is no operational authentication/GO.
        """
        if review_acknowledged is not True:
            raise ValueError('Explicit simulation recovery review required')

        def change():
            _, state = self._task(task)
            if state not in ('RUNNING', 'INTERRUPTED', 'FAILED'):
                raise ValueError('Task cannot be recovered')
            if state == 'RUNNING':
                self._event(task, 'INTERRUPTED', code='RESTART_REVIEW')
            self._event(task, 'RECOVERY_REVIEWED', code='OFFLINE_ONLY')
            self.db.execute('UPDATE tasks SET state=?,owner=NULL WHERE id=?', ('PENDING', task))
        self._change(change)
