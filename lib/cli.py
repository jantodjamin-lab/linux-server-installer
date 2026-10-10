#!/usr/bin/env python3
"""Read-only compact audit; optional JSON and explicitly approved execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from errors import WorkflowError, CommandError, PUBLIC_FAILURE_CODES, REMEDIES
from core import BASE, PROFILES, PUBLIC_CODES, inventory, plan, digest
from workflow import build_workflow, validate_plan_age
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
    lines=[f"Universal Linux Installer RC5 | {report.get('profile','operation')} | {report['status']}"]
    for item in report.get('checks',[]):
        lines.append(f"{item['status']:4} {item['id']}: {item['detail']}")
    for item in report.get('diagnostics',[]):
        suffix=(' ['+item['package']+']' if item.get('package') else '')+(f" (exit {item['exit_code']})" if 'exit_code' in item else '')
        lines.append(f"FAIL {item.get('step',item.get('stage','operation'))}: {item['code']}"+suffix)
        if item.get('remedy'):lines.append('Remedy: '+item['remedy'])
    if report.get('failures'): lines.append('FAIL reasons: '+', '.join(report['failures']))
    if report.get('code'): lines.append(('FAIL reason: ' if report['status']=='FAIL' else 'Reason: ')+report['code'])
    if report.get('remedy'):lines.append('Remedy: '+report['remedy'])
    # Retain physical-capacity warning in the compact report, even though RAM
    # already has its own WARN row. This prevents swap concealing reliability.
    for warning in report.get('warnings',[]):
        if 'insufficient for reliable' in warning: lines.append('WARN '+warning)
    if report.get('mode')=='dry-run':
        lines.append('Read-only: no package/source/swap/fstab changes. --json shows details.')
    elif 'plan_id' in report: lines.append('Plan: '+report['plan_id'])
    if report.get('directory'):lines.append('Private evidence: '+report['directory'])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description='Universal Linux Installer 1.0.0-rc.5 — NOT LIVE VALIDATED')
    parser.add_argument('--profile',choices=PROFILES,required=True)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--audit',action='store_true');modes.add_argument('--dry-run',action='store_true');modes.add_argument('--execute',action='store_true');modes.add_argument('--apply',action='store_true');modes.add_argument('--resolve',action='store_true')
    parser.add_argument('--out',help='Private resolver output directory')
    parser.add_argument('--refresh-metadata',action='store_true',help='Explicit authorization of resolve-only metadata refresh')
    parser.add_argument('--show-diagnostics',action='store_true',help='Show redacted private failure tail on stderr')
    parser.add_argument('--allow-mirror',action='append',default=[],metavar='URI',help='Exact explicitly allowed http(s) mirror URI')
    parser.add_argument('--allow-proxy-env',action='store_true')
    parser.add_argument('--no-wait-cloud-init',action='store_true')
    parser.add_argument('--max-new-packages',type=int,default=1000)
    parser.add_argument('--max-updates',type=int,default=100)
    parser.add_argument('--json',action='store_true',help='Machine-readable details; lock planning always emits JSON')
    parser.add_argument('--sudo',action='store_true',help='Interactive sudo for apply/resolve/execute; no password storage')
    parser.add_argument('--lock',help='Exact package lock, schema 2')
    parser.add_argument('--plan',help='Reviewed RC5 workflow JSON, schema 5 (2-hour expiry)')
    parser.add_argument('--npm-bundle',help='Reviewed Angular/Codex npm lock directories')
    parser.add_argument('--development',action='store_true');parser.add_argument('--system-updates',action='store_true')
    parser.add_argument('--approval',help='INSTALL:<plan_id>');parser.add_argument('--snapshot-confirmed',action='store_true')
    parser.add_argument('--allow-unvalidated',action='store_true');parser.add_argument('--recovery-reviewed',action='store_true')
    parser.add_argument('--state-dir',default='/var/lib/universal-linux-installer/checkpoints')
    args=parser.parse_args()
    if args.execute and (not args.plan or args.lock or not args.approval or not args.snapshot_confirmed or not args.allow_unvalidated):
        parser.error('--execute requires --plan, --approval, --snapshot-confirmed and --allow-unvalidated; --lock is planning-only')
    if not (args.execute or args.apply or args.resolve) and any((args.sudo,args.approval,args.snapshot_confirmed,args.allow_unvalidated,args.recovery_reviewed,args.plan)):
        parser.error('sudo and execution arguments require --execute, --apply or --resolve')
    if args.max_new_packages<1 or args.max_updates<0:parser.error('package limits must be positive/nonnegative')
    if args.resolve and (not args.out or not args.refresh_metadata):parser.error('--resolve requires --out DIR and explicit --refresh-metadata')
    if not args.resolve and (args.out or args.refresh_metadata):parser.error('--out and --refresh-metadata require --resolve')
    if (args.apply or args.resolve) and (args.lock or args.plan):parser.error('apply/resolve cannot use --lock or --plan')
    try:
        from sources import mirror_uri
        args.allow_mirror=sorted({mirror_uri(uri) for uri in args.allow_mirror})
        observed=inventory(allow_mirrors=args.allow_mirror) if args.allow_mirror else inventory()
        observed['target']=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        observed['managed']=Path('/var/lib/universal-linux-installer/ownership.json').is_file()
        if args.apply or args.resolve:
            audit=plan(args.profile,observed)
            if audit['status']=='FAIL':
                print(json.dumps(audit,sort_keys=True,indent=2) if args.json else render_summary(audit));return 1
            if os.geteuid()!=0:
                if not args.sudo:raise ValueError('root-required-use-interactive-sudo')
                from privilege import interactive_execute
                return interactive_execute(args)
            from apply import run_apply
            report=run_apply(args,observed)
        elif args.execute:
            workflow=read_json(args.plan)
            validate_plan_age(workflow)
            body={k:v for k,v in workflow.items() if k!='plan_id'}
            if digest(body)!=workflow['plan_id'] or workflow['profile']!=args.profile or args.approval!='INSTALL:'+workflow['plan_id']:
                raise ValueError('saved-plan-integrity')
            if args.development!=workflow['development'] or args.system_updates!=workflow['system_updates']:
                raise ValueError('saved-plan-options')
            if args.allow_mirror!=workflow.get('allow_mirrors',[]) or args.allow_proxy_env!=workflow.get('allow_proxy_env',False):raise ValueError('saved-plan-options')
            expected=build_workflow(args.profile,observed,workflow['lock'],args.development,args.system_updates,created_at=workflow['created_at'],allow_mirrors=args.allow_mirror,allow_proxy_env=args.allow_proxy_env,authorization=workflow.get('authorization'))
            if expected['steps']!=workflow['steps'] or observed['target']!=workflow['target'] or expected['arch']!=workflow['arch']:
                raise ValueError('saved-plan-target-or-actions')
            if os.geteuid()!=0:
                if not args.sudo: raise ValueError('root-required-use-interactive-sudo')
                from privilege import interactive_execute
                return interactive_execute(args)
            runner=LocalRunner(workflow,args.approval,args.snapshot_confirmed,args.allow_unvalidated,bundle=args.npm_bundle or BASE/'bundle')
            report=run_workflow(workflow,runner,args.state_dir,args.recovery_reviewed)
            report['profile']=args.profile
        elif args.lock:
            report=build_workflow(args.profile,observed,read_json(args.lock),args.development,args.system_updates,allow_mirrors=args.allow_mirror,allow_proxy_env=args.allow_proxy_env)
        else: report=plan(args.profile,observed)
        print(json.dumps(report,sort_keys=True,indent=2) if args.json or args.lock else render_summary(report))
        return int(report['status']=='FAIL')
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
        code=error.args[0] if isinstance(error,ValueError) and error.args and isinstance(error.args[0],str) and error.args[0] in (CLI_CODES | PUBLIC_FAILURE_CODES) else 'operation-refused-or-failed'
        report={'schema':5,'profile':args.profile,'status':'FAIL','code':code,'error_type':type(error).__name__,'live_validated':False}
        if isinstance(error,WorkflowError):
            report['diagnostics']=[error.metadata]
            report['directory']=error.directory or str(Path(args.state_dir))
            if args.show_diagnostics and error.diagnostic_path:
                from swap import regular
                path=Path(error.diagnostic_path);regular(path,0o600)
                print(path.read_text(),file=sys.stderr)
        elif isinstance(error,CommandError):
            from errors import failure_metadata
            report['diagnostics']=[failure_metadata('operation',error)]
            if args.show_diagnostics:print(error.stderr_tail,file=sys.stderr)
        if code in REMEDIES:report['remedy']=REMEDIES[code]
        print(json.dumps(report,sort_keys=True) if args.json or args.lock else render_summary(report))
        return 1
    except KeyboardInterrupt:
        print('FAIL cancelled; inspect checkpoints before any approved retry',file=sys.stderr)
        return 130


if __name__=='__main__': raise SystemExit(main())
