#!/usr/bin/env python3
"""Read-only compact audit; optional JSON and explicitly approved execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from core import PROFILES, PUBLIC_CODES, inventory, plan, digest
from workflow import build_workflow
from journal import run_workflow
from local import LocalRunner

CLI_CODES = PUBLIC_CODES | {
    'saved-plan-integrity','saved-plan-schema','saved-plan-options','saved-plan-target-or-actions',
    'root-required-use-interactive-sudo','sudo-execute-only','sudo-interactive-terminal-required',
    'sudo-trusted-executable-required','sudo-start-failed','preflight-failed','lock-schema',
    'node-angular-compatibility','profile-package-set','existing-version-conflict',
    'existing-listener-conflict','system-update-approval-required','uncertain-effects-review-required',
    'action-failed-see-private-journal','duplicate-json-key','nonfinite-json',
}


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate-json-key')
        result[key]=value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(),object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite-json')))


def render_summary(report):
    lines=[f"Universal Linux Installer RC4 | {report.get('profile','operation')} | {report['status']}"]
    for item in report.get('checks',[]):
        lines.append(f"{item['status']:4} {item['id']}: {item['detail']}")
    for item in report.get('diagnostics',[]):
        suffix=f" (exit {item['exit_code']})" if 'exit_code' in item else ''
        lines.append(f"FAIL {item['stage']}: {item['code']}"+suffix)
    if report.get('failures'): lines.append('FAIL reasons: '+', '.join(report['failures']))
    if report.get('code'): lines.append('FAIL reason: '+report['code'])
    # Retain physical-capacity warning in the compact report, even though RAM
    # already has its own WARN row. This prevents swap concealing reliability.
    for warning in report.get('warnings',[]):
        if 'insufficient for reliable' in warning: lines.append('WARN '+warning)
    if report.get('mode')=='dry-run':
        lines.append('Read-only: no package/source/swap/fstab changes. --json shows details.')
    elif 'plan_id' in report: lines.append('Plan: '+report['plan_id'])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description='Universal Linux Installer 1.0.0-rc.4 — NOT LIVE VALIDATED')
    parser.add_argument('--profile',choices=PROFILES,required=True)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--audit',action='store_true');modes.add_argument('--dry-run',action='store_true');modes.add_argument('--execute',action='store_true')
    parser.add_argument('--json',action='store_true',help='Machine-readable details; lock planning always emits JSON')
    parser.add_argument('--sudo',action='store_true',help='Interactive sudo for approved --execute only; no password storage')
    parser.add_argument('--lock',help='Exact package lock, schema 2')
    parser.add_argument('--plan',help='Reviewed RC4 workflow JSON, schema 4')
    parser.add_argument('--npm-bundle',help='Reviewed Angular/Codex npm lock directories')
    parser.add_argument('--development',action='store_true');parser.add_argument('--system-updates',action='store_true')
    parser.add_argument('--approval',help='INSTALL:<plan_id>');parser.add_argument('--snapshot-confirmed',action='store_true')
    parser.add_argument('--allow-unvalidated',action='store_true');parser.add_argument('--recovery-reviewed',action='store_true')
    parser.add_argument('--state-dir',default='/var/lib/universal-linux-installer/checkpoints')
    args=parser.parse_args()
    if args.execute and (not args.plan or args.lock or not args.approval or not args.snapshot_confirmed or not args.allow_unvalidated):
        parser.error('--execute requires --plan, --approval, --snapshot-confirmed and --allow-unvalidated; --lock is planning-only')
    if not args.execute and any((args.sudo,args.approval,args.snapshot_confirmed,args.allow_unvalidated,args.recovery_reviewed,args.plan)):
        parser.error('sudo and execution arguments require --execute')
    try:
        observed=inventory()
        observed['target']=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        observed['managed']=Path('/var/lib/universal-linux-installer/ownership.json').is_file()
        if args.execute:
            workflow=read_json(args.plan)
            if workflow.get('schema')!=4: raise ValueError('saved-plan-schema')
            body={k:v for k,v in workflow.items() if k!='plan_id'}
            if digest(body)!=workflow['plan_id'] or workflow['profile']!=args.profile or args.approval!='INSTALL:'+workflow['plan_id']:
                raise ValueError('saved-plan-integrity')
            if args.development!=workflow['development'] or args.system_updates!=workflow['system_updates']:
                raise ValueError('saved-plan-options')
            expected=build_workflow(args.profile,observed,workflow['lock'],args.development,args.system_updates)
            if expected['steps']!=workflow['steps'] or observed['target']!=workflow['target'] or expected['arch']!=workflow['arch']:
                raise ValueError('saved-plan-target-or-actions')
            if os.geteuid()!=0:
                if not args.sudo: raise ValueError('root-required-use-interactive-sudo')
                from privilege import interactive_execute
                return interactive_execute(args)
            runner=LocalRunner(workflow,args.approval,args.snapshot_confirmed,args.allow_unvalidated,bundle=args.npm_bundle)
            report=run_workflow(workflow,runner,args.state_dir,args.recovery_reviewed)
            report['profile']=args.profile
        elif args.lock:
            report=build_workflow(args.profile,observed,read_json(args.lock),args.development,args.system_updates)
        else: report=plan(args.profile,observed)
        print(json.dumps(report,sort_keys=True,indent=2) if args.json or args.lock else render_summary(report))
        return int(report['status']=='FAIL')
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
        code=error.args[0] if isinstance(error,ValueError) and error.args and isinstance(error.args[0],str) and error.args[0] in CLI_CODES else 'operation-refused-or-failed'
        report={'schema':4,'profile':args.profile,'status':'FAIL','code':code,'error_type':type(error).__name__,'live_validated':False}
        print(json.dumps(report,sort_keys=True) if args.json or args.lock else render_summary(report))
        return 1
    except KeyboardInterrupt:
        print('FAIL cancelled; inspect checkpoints before any approved retry',file=sys.stderr)
        return 130


if __name__=='__main__': raise SystemExit(main())
