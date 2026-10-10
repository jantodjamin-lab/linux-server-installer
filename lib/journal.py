"""Private, atomic, process-locked journal. No rollback or unattended retry."""
import fcntl
from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
from core import digest


def private_directory(path):
    path = Path(path).absolute()
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError('symlink-directory')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    stat = path.stat()
    if stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
        raise ValueError('private-directory-required')
    return path


class Journal:
    def __init__(self, directory, binding):
        self.root = private_directory(directory)
        self.binding = binding
        self.fd = None
        self.state = None

    def __enter__(self):
        self.fd = os.open(self.root/'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if os.fstat(self.fd).st_nlink != 1 or os.fstat(self.fd).st_uid != os.geteuid():
                raise ValueError('lock-owner')
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = self.root/'journal.json'
            self.state = {'schema': 2, 'binding': self.binding, 'pending': None, 'done': [], 'events': []}
            if path.exists() or path.is_symlink():
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd) as stream:
                    stat = os.fstat(stream.fileno())
                    if stat.st_nlink != 1 or stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
                        raise ValueError('journal-owner')
                    envelope = json.load(stream)
                if set(envelope) != {'state', 'sha256'} or digest(envelope['state']) != envelope['sha256']:
                    raise ValueError('journal-integrity')
                self.state = envelope['state']
                if set(self.state) != {'schema', 'binding', 'pending', 'done', 'events'} or self.state['binding'] != self.binding or self.state['schema'] != 2:
                    raise ValueError('journal-binding')
                if not isinstance(self.state['done'], list) or not isinstance(self.state['events'], list):
                    raise ValueError('journal-types')
            return self
        except BaseException:
            os.close(self.fd); self.fd = None
            raise

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd); self.fd = None

    def save(self):
        fd, temporary = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'state': self.state, 'sha256': digest(self.state)}, stream, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.root/'journal.json')
            fd = os.open(self.root, os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def event(self, event, step=None, **metadata):
        self.state['events'].append({'sequence': len(self.state['events'])+1, 'event': event, 'step': step, **metadata})
        self.save()


def run_workflow(workflow, runner, directory, recovery_review=False):
    host_lock = runner.execution_lock() if hasattr(runner, 'execution_lock') else nullcontext()
    with host_lock:
        return _run_workflow(workflow, runner, directory, recovery_review)


def _run_workflow(workflow, runner, directory, recovery_review=False):
    with Journal(directory, workflow['plan_id']) as journal:
        if journal.state['pending']:
            pending = next((s for s in workflow['steps'] if s['id'] == journal.state['pending']), None)
            if pending is None: raise ValueError('journal-unknown-step')
            if pending.get('effect', 'effectful') in ('readonly', 'idempotent'):
                journal.state['pending'] = None
                journal.event('AUTO_CLEARED', pending['id'])
            else:
                if recovery_review is not True: raise ValueError('uncertain-effects-review-required')
                journal.event('RECOVERY_REVIEWED', journal.state['pending'])
                journal.state['pending'] = None
                journal.save()
        for step in workflow['steps']:
            if step['id'] in journal.state['done']:
                if not runner.validate(step):
                    raise ValueError('completed-step-drift')
                continue
            if runner.reboot_required():
                return {'status': 'WARN', 'reason': 'manual-reboot-required', 'plan_id': workflow['plan_id']}
            journal.state['pending'] = step['id']
            journal.event('STARTED', step['id'])
            try:
                runner.apply(step)
                if not runner.validate(step):
                    raise ValueError('postcondition')
            except Exception as error:
                from errors import CommandError, WorkflowError, failure_metadata
                metadata = failure_metadata(step['id'], error)
                diagnostic_path = None
                if isinstance(error, CommandError):
                    diagnostics = private_directory(journal.root/'diagnostics')
                    diagnostic_path = diagnostics/(step['id']+'-'+str(len(journal.state['events'])+1)+'.log')
                    fd = os.open(diagnostic_path, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, 'w') as stream:
                        stream.write(error.stderr_tail); stream.flush(); os.fsync(stream.fileno())
                journal.event('FAILED', **metadata)
                if step.get('effect', 'effectful') in ('readonly', 'idempotent'):
                    journal.state['pending'] = None
                    journal.event('AUTO_CLEARED', step['id'])
                raise WorkflowError(metadata, diagnostic_path) from None
            journal.state['done'].append(step['id'])
            journal.state['pending'] = None
            journal.event('VALIDATED', step['id'])
        return {'status': 'WARN' if runner.reboot_required() else 'PASS',
                'reason': 'manual-reboot-required' if runner.reboot_required() else 'validators-passed',
                'plan_id': workflow['plan_id'], 'live_validated': False,
                'swap': getattr(runner, 'swap_report', None) or (runner.swap.report() if hasattr(runner,'swap') else None),
                'warnings': workflow.get('warnings', [])}
