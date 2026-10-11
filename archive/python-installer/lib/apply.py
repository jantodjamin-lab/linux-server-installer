"""One authorization of bounded intent before any metadata or target write."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
import os
from pathlib import Path
import sys
from core import BASE, digest, plan
from errors import CommandError, WorkflowError, PreflightError, failure_metadata
from journal import Journal, private_directory
from local import LocalRunner, command
from resolve import resolve, npm_pins
from sources import read_sources, mirror_uri
from workflow import validate_plan_age


def request(args, observed, mode='apply', root='/'):
    mirrors=sorted({mirror_uri(uri) for uri in args.allow_mirror})
    body={'schema':5,'mode':mode,'profile':args.profile,'development':args.development,
          'system_updates':args.system_updates,'allow_mirrors':mirrors,
          'allow_proxy_env':args.allow_proxy_env,'wait_cloud_init':not args.no_wait_cloud_init,
          'target':observed['target'],'arch':observed['arch'],
          'source_policy':[e for e in read_sources(root,mirrors)['entries'] if e['source_file']!='universal-node-universe.sources'],
          'npm':npm_pins(args.profile,args.development,args.npm_bundle),
          'limits':{'max_new_packages':args.max_new_packages,'max_updates':args.max_updates,
                    'no_remove':True,'only_profile_and_closure':True,'no_downgrade':True}}
    return {**body,'request_id':digest(body)}


def request_summary(intent, observed):
    lines=['Authorize '+intent['mode']+' | '+intent['profile'],
           'APT index will be refreshed AFTER confirmation (writes /var/lib/apt/lists).',
           ('Missing universe components may be appended to one owned source file.'
            if intent['mode']=='apply' else
            'APT source configuration remains unchanged; missing components must be reviewed separately.'),
           'Only profile packages + exact signed dependency closure; --no-remove; no downgrades.',
           'Limits: '+str(intent['limits']['max_new_packages'])+' new packages; '+str(intent['limits']['max_updates'])+' updates.',
           'Updates: '+('explicitly enabled' if intent['system_updates'] else 'forbidden; stop if closure requires updates'),
           'Mirror exceptions: '+(', '.join(intent['allow_mirrors']) or 'none'),
           'Proxy environment: '+('explicitly enabled; credentials never stored' if intent['allow_proxy_env'] else 'not forwarded'),
           'Cloud-init wait: '+str(intent['wait_cloud_init']),
           'Swap: '+str(max(0,4*2**30-observed.get('swap_bytes',0)))+' deficit bytes; existing swap preserved.',
           'npm pins: '+json.dumps(intent['npm'],sort_keys=True),
           'Authorization hash: '+intent['request_id']]
    return '\n'.join(lines)


@contextmanager
def open_terminal(path='/dev/tty'):
    # A real TTY is non-seekable: Python r+ uses BufferedRandom and fails.
    # Separate read/write streams work on a terminal without capturing passwords.
    with open(path,'r',encoding='utf-8') as reader, open(path,'w',encoding='utf-8') as writer:
        yield SimpleNamespace(readline=reader.readline,write=writer.write,flush=writer.flush)


def confirm(args, intent, tty=None):
    if args.approval:
        if args.approval!='INSTALL:'+intent['request_id']: raise ValueError('intent-approval-mismatch')
        if not args.snapshot_confirmed or not args.allow_unvalidated: raise ValueError('explicit-snapshot-and-candidate-required')
        return
    if not sys.stdin.isatty(): raise ValueError('interactive-confirmation-required')
    if tty is None:
        with open_terminal() as terminal: return confirm(args,intent,terminal)
    if not args.snapshot_confirmed:
        tty.write('Fresh restorable snapshot confirmed? Type yes or no: ');tty.flush()
        if tty.readline().strip()!='yes': raise ValueError('snapshot-not-confirmed')
    if not args.allow_unvalidated:
        tty.write('This candidate is NOT LIVE VALIDATED. Accept disposable-test risk? Type yes or no: ');tty.flush()
        if tty.readline().strip()!='yes': raise ValueError('unvalidated-candidate-not-accepted')
    token='INSTALL '+intent['request_id'][:12]
    tty.write('Authorize refresh + resolve + installation within these limits. Type '+token+': ');tty.flush()
    if tty.readline().strip()!=token: raise ValueError('installation-not-confirmed')


def private_write(directory, name, content):
    from swap import atomic, regular
    path=directory/name
    if path.exists() or path.is_symlink(): regular(path,0o600)
    atomic(path,content,0o600)


def resolution_summary(workflow):
    r=workflow['resolution']; swap=workflow['capacity']['swap']
    return ('Resolved '+workflow['profile']+'\nNew packages: '+str(r['new_packages'])+'\nUpdates: '+str(r['updates'])+
            '\nEstimated download bytes: '+str(r['download_bytes'])+'\nEstimated installed bytes: '+str(r['disk_bytes'])+
            '\nSize scope: '+r['estimate']+'\nSwap deficit bytes: '+str(swap.get('deficit_bytes'))+
            '\nnpm pins: '+json.dumps(workflow['lock']['npm'],sort_keys=True)+'\nPlan: '+workflow['plan_id']+'\n')


def prepare_sources(profile, arch, mirrors, call, root='/'):
    from node import verify_key, universe_present, universe_source, SOURCE
    from sources import validate_sources, BASE_SUITES, universe_coverage
    root=Path(root)
    validate_sources(root,mirrors);verify_key(root,call)
    if profile!='DB' and not universe_present(root,arch,mirrors):
        content=universe_source(arch,BASE_SUITES-universe_coverage(root,arch,mirrors),root,mirrors)
        path=root/SOURCE
        for item in [path,*path.parents]:
            if item.is_symlink(): raise ValueError('apt-source-symlink')
        if path.exists():
            if path.read_text()!=content: raise ValueError('existing-config-conflict')
        else:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'w') as stream: stream.write(content);stream.flush();os.fsync(stream.fileno())
        validate_sources(root,mirrors)


def authorized_resolution(args, observed, intent, directory, call, root='/'):
    source_effectful=intent['mode']=='apply'
    with Journal(directory/'preparation',intent['request_id']) as journal:
        pending=journal.state['pending']
        if pending:
            if pending=='sources' and source_effectful and not args.recovery_reviewed: raise ValueError('uncertain-effects-review-required')
            journal.state['pending']=None
            journal.event('RECOVERY_REVIEWED' if pending=='sources' and source_effectful else 'AUTO_CLEARED',pending)
        for stage in ('cloud-init','sources','resolve'):
            if stage in journal.state['done'] and stage!='resolve': continue
            journal.state['pending']=stage;journal.event('STARTED',stage)
            try:
                if stage=='cloud-init':
                    if intent['wait_cloud_init'] and (Path(root)/'usr/bin/cloud-init').is_file():
                        print('WARN waiting for cloud-init; DPkg::Lock::Timeout=600 protects package contention',file=sys.stderr)
                        try: call(['/usr/bin/cloud-init','status','--wait'])
                        except CommandError as error:
                            if error.exit_code!=2: raise
                            print('WARN cloud-init completed with recoverable errors; inspect cloud-init separately',file=sys.stderr)
                    output=call(['/usr/bin/pgrep','-f','(^|[[:space:]])(/usr/bin/)?unattended-upgrades?([[:space:]]|$)']) if (Path(root)/'usr/bin/pgrep').is_file() else ''
                    if output: print('WARN unattended-upgrades active; waiting for dpkg lock up to 600 seconds',file=sys.stderr)
                elif stage=='sources':
                    current=[e for e in read_sources(root,args.allow_mirror)['entries'] if e['source_file']!='universal-node-universe.sources']
                    if current!=intent['source_policy']:raise ValueError('source-policy-changed')
                    if source_effectful:
                        prepare_sources(args.profile,observed['arch'],args.allow_mirror,call,root)
                    else:
                        from sources import validate_sources
                        from node import verify_key
                        validate_sources(root,args.allow_mirror);verify_key(root,call)
                else:
                    workflow=resolve(args.profile,observed,call,root=root,development=args.development,
                                     system_updates=args.system_updates,allow_mirrors=args.allow_mirror,
                                     allow_proxy_env=args.allow_proxy_env,bundle=args.npm_bundle,
                                     refresh_metadata=True,max_new_packages=args.max_new_packages,
                                     max_updates=args.max_updates,authorization=intent)
                    private_write(directory,'lock.json',json.dumps(workflow['lock'],sort_keys=True,indent=2)+'\n')
                    private_write(directory,'plan.json',json.dumps(workflow,sort_keys=True,indent=2)+'\n')
                    private_write(directory,'SUMMARY.txt',request_summary(intent,observed)+'\n\n'+resolution_summary(workflow))
            except Exception as error:
                metadata=failure_metadata(stage,error)
                diagnostic_path=None
                if isinstance(error,CommandError):
                    logs=private_directory(journal.root/'diagnostics')
                    diagnostic_path=logs/(stage+'-'+str(len(journal.state['events'])+1)+'.log')
                    private_write(logs,diagnostic_path.name,error.stderr_tail)
                journal.event('FAILED',**metadata)
                if stage!='sources' or not source_effectful:
                    journal.state['pending']=None;journal.event('AUTO_CLEARED',stage)
                failed_checks=('\nFailed checks: '+', '.join(metadata['failed_checks'])) if metadata.get('failed_checks') else ''
                private_write(directory,'SUMMARY.txt',request_summary(intent,observed)+'\nFAIL '+stage+': '+metadata['code']+(' ['+metadata['package']+']' if metadata.get('package') else '')+failed_checks+'\n'+metadata.get('remedy','')+'\nSee preparation/journal.json and private diagnostics.\n')
                raise WorkflowError(metadata,diagnostic_path,directory) from None
            if stage not in journal.state['done']:journal.state['done'].append(stage)
            journal.state['pending']=None;journal.event('VALIDATED',stage)
        return workflow


def completed_checkpoint(directory, workflow):
    """Read-only expiry exception: every exact-plan step durably completed."""
    from swap import regular
    import stat
    directory=Path(directory)
    for parent in [directory,*directory.parents]:
        if parent.is_symlink():return False
    try:
        owner=directory.stat()
        if not stat.S_ISDIR(owner.st_mode) or owner.st_uid!=os.geteuid() or stat.S_IMODE(owner.st_mode)!=0o700:return False
        path=directory/'journal.json';regular(path,0o600)
        envelope=json.loads(path.read_text())
        if set(envelope)!={'state','sha256'} or digest(envelope['state'])!=envelope['sha256']:return False
        state=envelope['state']
        return (set(state)=={'schema','binding','pending','done','events'} and state['schema']==2
                and state['binding']==workflow['plan_id'] and state['pending'] is None
                and isinstance(state['events'],list) and isinstance(state['done'],list)
                and len(state['done'])==len(workflow['steps'])
                and set(state['done'])=={step['id'] for step in workflow['steps']})
    except (OSError,ValueError,TypeError,KeyError):return False


def fresh_target(root, observed):
    marker=Path(root)/'var/lib/universal-linux-installer/ownership.json'
    if marker.exists() or marker.is_symlink():
        from swap import regular
        regular(marker,0o600)
        return True
    for relative in ('etc/nginx','etc/postgresql','var/lib/postgresql','opt/universal-linux-installer','usr/sbin/policy-rc.d'):
        item=Path(root)/relative
        if item.exists() or item.is_symlink():raise ValueError('existing-service-or-data-conflict')
    ports=observed.get('tcp_ports',[])
    required=[8080] if observed.get('profile')=='APP' else [5432] if observed.get('profile')=='DB' else [8080,5432]
    if any(port in ports for port in required):raise ValueError('existing-listener-conflict')
    return False


def run_apply(args, observed, *, root='/', transport=None):
    root=Path(root).absolute()
    if root==Path('/') and os.geteuid()!=0: raise ValueError('root-required-use-interactive-sudo')
    audit=plan(args.profile,observed)
    if audit['failures']: raise PreflightError(audit)
    for check in audit['checks']:
        if check['status']=='WARN':
            print('WARN '+check['id']+': '+check['detail'],file=sys.stderr)
    for warning in audit['warnings']:
        if 'insufficient for reliable' in warning:print('WARN '+warning,file=sys.stderr)
    owned=fresh_target(root,dict(observed,profile=args.profile))
    intent=request(args,observed,'resolve' if args.resolve else 'apply',root)
    if owned and args.apply and not (Path(args.state_dir)/intent['request_id']/'plan.json').is_file():raise ValueError('ownership-binding')
    print(request_summary(intent,observed),file=sys.stderr)
    if args.resolve:
        if not args.refresh_metadata: raise ValueError('refresh-metadata-authorization-required')
    else: confirm(args,intent)
    # No directory/journal/source/cache write has occurred before this point.
    directory=private_directory(Path(args.out) if args.resolve else Path(args.state_dir)/intent['request_id'])
    call=transport or (lambda argv: command(argv,allow_proxy_env=args.allow_proxy_env))
    # pgrep's absence-of-match exit is expected, not a failed operator action.
    original=call
    def tolerant(argv):
        try:return original(argv)
        except CommandError as error:
            if Path(argv[0]).name=='pgrep' and error.exit_code==1:return ''
            raise
    # One target lock covers both resolver and execution, including source prep.
    with Journal(root/'var/lib/universal-linux-installer/execution',observed['target']):
        path=directory/'plan.json'
        if path.exists() and not args.resolve:
            from cli import read_json
            from swap import regular
            regular(path,0o600);workflow=read_json(path)
            try:validate_plan_age(workflow)
            except ValueError as error:
                if str(error)!='plan-expired' or not completed_checkpoint(directory/'checkpoints',workflow):raise
            if workflow.get('authorization')!=intent: raise ValueError('saved-plan-options')
            if digest({k:v for k,v in workflow.items() if k!='plan_id'})!=workflow['plan_id']:raise ValueError('saved-plan-integrity')
            with Journal(directory/'preparation',intent['request_id']) as preparation:
                pending=preparation.state['pending']
                if pending:
                    if pending=='sources' and not args.recovery_reviewed:raise ValueError('uncertain-effects-review-required')
                    preparation.state['pending']=None
                    preparation.event('RECOVERY_REVIEWED' if pending=='sources' else 'AUTO_CLEARED',pending)
        else: workflow=authorized_resolution(args,observed,intent,directory,tolerant,root)
        print(resolution_summary(workflow),file=sys.stderr)
        if args.resolve:return {'status':'WARN','profile':args.profile,'plan_id':workflow['plan_id'],'code':'resolved-review-required','directory':str(directory),'live_validated':False}
        runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root=root,transport=command if transport is None else lambda argv,cwd=None:transport(argv,cwd=cwd),bundle=args.npm_bundle or BASE/'bundle',completed_checkpoints=directory/'checkpoints')
        # Target lock is already held; avoid recursively acquiring it.
        from journal import _run_workflow
        report=_run_workflow(workflow,runner,directory/'checkpoints',args.recovery_reviewed)
        report.update(profile=args.profile,directory=str(directory))
        report['admission_checks']=audit['checks']
        if report['status']=='PASS':
            report['checks']=[{'id':step['id'],'status':'PASS','detail':'validated'} for step in workflow['steps']]
            report['checks'] += [check for check in audit['checks'] if check['status']=='WARN']
        return report
