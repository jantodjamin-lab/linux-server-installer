#!/usr/bin/env python3
"""Default read-only CLI; apply requires a saved plan and explicit consent."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from core import PROFILES, inventory, plan, digest
from workflow import build_workflow
from journal import run_workflow
from local import LocalRunner


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate-json-key')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite-json')))


def main():
    parser = argparse.ArgumentParser(description='Universal Linux Installer 1.0.0-rc.3 — NIET LIVE GEVALIDEERD')
    parser.add_argument('--profile', choices=PROFILES, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--audit', action='store_true')
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--lock', help='Exact package lock, schema 2')
    parser.add_argument('--plan', help='Previously reviewed workflow JSON')
    parser.add_argument('--npm-bundle', help='Reviewed Angular/Codex package.json and package-lock.json directories')
    parser.add_argument('--development', action='store_true')
    parser.add_argument('--system-updates', action='store_true')
    parser.add_argument('--approval', help='INSTALL:<plan_id>')
    parser.add_argument('--snapshot-confirmed', action='store_true')
    parser.add_argument('--allow-unvalidated', action='store_true')
    parser.add_argument('--recovery-reviewed', action='store_true')
    parser.add_argument('--state-dir', default='/var/lib/universal-linux-installer/checkpoints')
    args = parser.parse_args()
    if args.execute and (not args.plan or args.lock or not args.approval or not args.snapshot_confirmed or not args.allow_unvalidated):
        parser.error('--execute requires --plan, --approval, --snapshot-confirmed and --allow-unvalidated; --lock is planning-only')
    if not args.execute and any((args.approval, args.snapshot_confirmed, args.allow_unvalidated, args.recovery_reviewed, args.plan)):
        parser.error('execution arguments require --execute')
    try:
        observed = inventory()
        observed['target'] = hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        observed['managed'] = Path('/var/lib/universal-linux-installer/ownership.json').is_file()
        if args.execute:
            workflow = read_json(args.plan)
            body = {k: v for k, v in workflow.items() if k != 'plan_id'}
            if digest(body) != workflow['plan_id'] or workflow['profile'] != args.profile:
                raise ValueError('saved-plan-integrity')
            if args.development != workflow['development'] or args.system_updates != workflow['system_updates']:
                raise ValueError('saved-plan-options')
            expected = build_workflow(args.profile, observed, workflow['lock'], args.development, args.system_updates)
            if expected['steps'] != workflow['steps'] or observed['target'] != workflow['target']:
                raise ValueError('saved-plan-target-or-actions')
            runner = LocalRunner(workflow, args.approval, args.snapshot_confirmed, args.allow_unvalidated,
                                 bundle=args.npm_bundle)
            report = run_workflow(workflow, runner, args.state_dir, args.recovery_reviewed)
        elif args.lock:
            report = build_workflow(args.profile, observed, read_json(args.lock), args.development, args.system_updates)
        else:
            report = plan(args.profile, observed)
        print(json.dumps(report, sort_keys=True, indent=2))
        return int(report['status'] == 'FAIL')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        # Do not echo arbitrary exception text, paths, package output or credentials.
        print(json.dumps({'schema': 2, 'status': 'FAIL', 'code': 'operation-refused-or-failed',
                          'error_type': type(error).__name__, 'live_validated': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
