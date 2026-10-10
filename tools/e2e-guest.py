"""ONLY inside the disposable, explicitly seeded local VM; no remote interface."""
import argparse
import hashlib
import json
import os
import errno
import fcntl
import pty
import re
import platform
import secrets
import select
import termios
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'lib'))
from apply import request
from core import inventory, plan
from cli import main
from journal import Journal
from errors import redact


def checked(argv):return subprocess.run(argv,check=True,text=True,capture_output=True).stdout


def sudo_password_prompt(output, echo_enabled=False):
    """Accept documented classic/sudo-rs prompts only when terminal echo is off."""
    clean=re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]',b'',bytes(output)).strip().lower()
    known=b'[sudo] password for ' in clean or b'[sudo: authenticate] password:' in clean
    return known and clean.endswith(b':') and not echo_enabled


def sudo_evidence(profile):
    """Actual VM-only sudo auth; deliberately invalid approval prevents effects."""
    account='e2e-password'
    checked(['/usr/sbin/useradd','--create-home','--shell','/bin/sh',account])
    secret=secrets.token_urlsafe(32)
    # Only OS fixture authentication receives the password, never the installer.
    subprocess.run(['/usr/sbin/chpasswd'],input=account+':'+secret+'\n',text=True,check=True,capture_output=True)
    policy=Path('/etc/sudoers.d/rc5-e2e-password')
    policy.write_text(account+' ALL=(root) ALL\n');policy.chmod(0o440)
    checked(['/usr/sbin/visudo','-cf',str(policy)])
    evidence={'status':'PASS','cases':{}}
    for user,password in [('rc5-operator',None),(account,secret)]:
        mode='password' if password else 'nopasswd'
        found=subprocess.run(['/usr/bin/getent','passwd',user],check=False,capture_output=True,text=True)
        if found.returncode!=0:
            evidence['status']='FAIL';evidence['cases'][mode]={'status':'FAIL','code':'fixture-user-missing'}
            continue
        master,slave=pty.openpty();output=bytearray();sent=False;process=None;status=None;failure=None
        def session():
            os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
        argv=['/usr/sbin/runuser','-u',user,'--','sh',str(BASE/'install.sh'),
              '--profile',profile,'--apply','--sudo','--system-updates',
              '--snapshot-confirmed','--allow-unvalidated','--allow-mirror',
              'https://mirror.transip.net/ubuntu/ubuntu/','--approval','INSTALL:'+'0'*64,'--json']
        if profile!='DB':argv.append('--development')
        try:
            process=subprocess.Popen(argv,stdin=slave,stdout=slave,stderr=slave,preexec_fn=session,close_fds=True)
            os.close(slave);slave=None
            deadline=time.monotonic()+90
            while True:
                if time.monotonic()>deadline:raise AssertionError('sudo-fixture-timeout')
                if select.select([master],[],[],0.1)[0]:
                    try:chunk=os.read(master,4096)
                    except OSError as error:
                        if error.errno==errno.EIO:break
                        raise
                    if not chunk:break
                    output.extend(chunk)
                    if password and not sent and sudo_password_prompt(output,bool(termios.tcgetattr(master)[3]&termios.ECHO)):
                        os.write(master,password.encode()+b'\n');sent=True
                elif process.poll() is not None:break
            status=process.wait(timeout=10)
            assert secret.encode() not in output,'sudo-fixture-secret-echoed'
            assert status==1 and b'intent-approval-mismatch' in output,'sudo-approval-refusal-not-reached'
            if password:assert sent,'sudo-password-prompt-missing'
            else:assert not any(marker in output.lower() for marker in (b'[sudo] password for ',b'[sudo: authenticate] password:')),'sudo-nopasswd-prompt-unexpected'
        except Exception as error:
            failure=str(error) if isinstance(error,AssertionError) else type(error).__name__
            evidence['status']='FAIL'
        finally:
            if process is not None and process.poll() is None:process.kill();process.wait()
            os.close(master)
            if slave is not None:os.close(slave)
        # Redact exact fixture secret BEFORE bounded general redaction. No raw
        # PTY output or password is placed in JSON, console or artifacts.
        safe=redact(output.decode(errors='replace').replace(secret,'[REDACTED]'))
        path=Path('/e2e-artifacts')/('sudo-'+mode+'.log');path.write_text(safe);path.chmod(0o600)
        evidence['cases'][mode]={'status':'FAIL' if failure else 'PASS','code':failure or 'authenticated-approval-refused-no-effects',
                                 'exit_code':status,'password_prompt_seen':sent,'diagnostic':path.name}
    Path('/e2e-artifacts/sudo-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def collect_fixture_evidence():
    if os.geteuid()!=0 or not Path('/etc/universal-installer-disposable-e2e').is_file():
        raise SystemExit('Refusing: disposable fixture required')
    directory=Path('/e2e-artifacts')
    for name in ('cloud-init.log','cloud-init-output.log'):
        source=Path('/var/log')/name
        if source.is_file():(directory/name).write_text(redact(source.read_text(errors='replace')))
    status=subprocess.run(['/usr/bin/cloud-init','status','--long'],capture_output=True,text=True,check=False)
    (directory/'cloud-init-status.log').write_text(redact(status.stdout+'\n'+status.stderr))


def args_for(profile):
    return argparse.Namespace(profile=profile,apply=True,resolve=False,development=profile!='DB',
            system_updates=True,allow_mirror=['https://mirror.transip.net/ubuntu/ubuntu/'],allow_proxy_env=False,no_wait_cloud_init=False,
            max_new_packages=1000,max_updates=100,npm_bundle=None,state_dir='/var/lib/universal-linux-installer/checkpoints')


def invoke(profile, kill_event=0, review=False, contention=False):
    data=inventory();data['target']=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
    intent=request(args_for(profile),data)
    argv=['sh',str(BASE/'install.sh'),'--profile',profile,'--apply','--system-updates',
          '--snapshot-confirmed','--allow-unvalidated','--approval','INSTALL:'+intent['request_id'],'--show-diagnostics','--json']
    argv += ['--allow-mirror','https://mirror.transip.net/ubuntu/ubuntu/']
    if profile!='DB':argv.append('--development')
    if review:argv.append('--recovery-reviewed')
    if kill_event or contention:
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--fault-child',str(kill_event),str(int(contention)),*argv[2:]]
    return subprocess.run(argv,check=False,capture_output=True,text=True)


def fault_child(event, contention, argv):
    if os.geteuid()!=0 or not Path('/etc/universal-installer-disposable-e2e').is_file() or not Path('/run/systemd/system').is_dir():
        raise SystemExit('Refusing: disposable VM marker/root/systemd required')
    # Test-only deterministic fault hook; NEVER shipped as a target CLI flag or
    # activated through a production environment variable.
    original=Journal.event;counter=0;locker=None;started=None;unattended=None;dryrun_output=None
    def fault(journal,*args,**kwargs):
        nonlocal counter,locker,started,unattended,dryrun_output
        original(journal,*args,**kwargs);counter+=1
        if event and counter==event:os.kill(os.getpid(),signal.SIGKILL)
        if contention and args==('STARTED','packages'):
            blocker="import fcntl,time;f=open('/var/lib/dpkg/lock-frontend','a');fcntl.lockf(f,fcntl.LOCK_EX);time.sleep(25)"
            locker=subprocess.Popen(['/usr/bin/python3','-c',blocker])
            time.sleep(1);started=time.monotonic()
            # Real utility dry-run, concurrently with an explicitly injected
            # frontend-lock fixture. Never disguise the fixture as a daemon.
            dryrun_output=open('/e2e-artifacts/unattended-dry-run.log','w')
            os.chmod('/e2e-artifacts/unattended-dry-run.log',0o600)
            unattended=subprocess.Popen(['/usr/bin/unattended-upgrade','--dry-run','--debug'],stdout=dryrun_output,stderr=subprocess.STDOUT)
            evidence={'lock_fixture':'python-fcntl-real-dpkg-frontend-lock','dry_run_command':['/usr/bin/unattended-upgrade','--dry-run','--debug'],
                      'dry_run_pid':unattended.pid,'simultaneous_fixture_lock':locker.poll() is None}
            Path('/e2e-artifacts/contention-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
        if contention and args==('VALIDATED','packages'):
            assert time.monotonic()-started>=23,'APT did not wait on dpkg contention'
            locker.wait(timeout=60)
            try:dry_run_exit=unattended.wait(timeout=90)
            except subprocess.TimeoutExpired:
                unattended.terminate();unattended.wait(timeout=15)
                raise AssertionError('Actual unattended-upgrade dry-run exceeded bound')
            finally:dryrun_output.close()
            evidence=json.loads(Path('/e2e-artifacts/contention-evidence.json').read_text())
            raw=Path('/e2e-artifacts/unattended-dry-run.log').read_text()
            Path('/e2e-artifacts/unattended-dry-run.log').write_text(redact(raw))
            assert dry_run_exit==0 or (dry_run_exit==1 and 'lock' in raw.lower()),'Unattended dry-run failed for an unexpected reason'
            evidence.update({'apt_step_elapsed_seconds':time.monotonic()-started,'dry_run_exit_code':dry_run_exit,
                             'dry_run_result':'completed' if dry_run_exit==0 else 'expected-lock-refusal'})
            Path('/e2e-artifacts/contention-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    Journal.event=fault
    sys.argv=['installer',*argv];raise SystemExit(main())


def postboot_proof(marker):
    """Read-only checks after the harness cold-boots the SAME disposable overlay."""
    pending=json.loads(marker.read_text());result=pending['result']
    assert result.get('status')=='PASS' and result.get('installation_status')=='PASS','cold-boot marker lacks successful initial validation'
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot!=pending['boot_id'],'cold-boot fixture reused the same kernel boot'
    from swap import active_swap
    current=active_swap(checked)
    assert sum(current.values())>=4*2**30,'persistent swap absent after cold boot'
    fstab=Path('/etc/fstab').read_text()
    if result['swap_initial_gib']:
        assert '/e2e-existing-swap' in current,'fixture swap did not survive cold boot'
        assert '/e2e-existing-swap none swap sw 0 0' in fstab,'fixture fstab entry changed'
    if result['swap_initial_gib']>=4:
        assert not Path('/var/lib/universal-linux-installer/swap/swapfile').exists()
    assert not Path('/usr/sbin/policy-rc.d').exists()
    profile=result['profile']
    if profile!='DB':
        checked(['/usr/sbin/nginx','-t'])
        assert 'Installer ready' in checked(['/usr/bin/curl','--fail','--silent','--retry','10','--retry-delay','1','--retry-connrefused','--max-time','5','http://127.0.0.1:8080/'])
    if profile!='APP':
        for attempt in range(30):
            if subprocess.run(['/usr/bin/pg_isready','-h','127.0.0.1'],capture_output=True,check=False).returncode==0:break
            time.sleep(1)
        else:raise AssertionError('PostgreSQL not ready after cold boot')
        policy=checked(['/usr/sbin/runuser','-u','postgres','--','/usr/bin/psql','-X','-A','-t','-c',"SELECT current_setting('password_encryption'),current_setting('listen_addresses')"])
        assert policy.strip()=='scram-sha-256|localhost'
    sockets=checked(['/usr/bin/ss','-H','-ltn'])
    external={line.split()[3] for line in sockets.splitlines() if not line.split()[3].startswith(('127.','[::1]:','::1:'))}
    assert external==set(pending['external_sockets']),'new listener after cold boot'
    for line in sockets.splitlines():
        address=line.split()[3]
        if address.rsplit(':',1)[-1] in ('8080','5432'):
            assert address.startswith(('127.0.0.1:','[::1]:','::1:'))
    result.update({'status':'PASS','coldboot':True,'boot_id_before':pending['boot_id'],'boot_id_after':boot,'postboot_swap_bytes':sum(current.values())})
    Path('/var/lib/universal-linux-installer/e2e-result.json').write_text(json.dumps(result,indent=2)+'\n')
    marker.unlink()
    print(json.dumps(result),flush=True)


def run(profile, swap_gib=0, fault=0, contention=False, minimum_vm=False, low_memory=False):
    if os.geteuid()!=0 or not Path('/etc/universal-installer-disposable-e2e').is_file() or not Path('/run/systemd/system').is_dir():
        raise SystemExit('Refusing: disposable VM marker/root/systemd required')
    reboot_marker=Path('/var/lib/universal-linux-installer/e2e-reboot-pending.json')
    if reboot_marker.is_file():
        postboot_proof(reboot_marker);return
    identity=platform.freedesktop_os_release()
    assert identity.get('ID')=='ubuntu' and identity.get('VERSION_ID')=='26.04',identity
    before_sockets=checked(['/usr/bin/ss','-H','-ltn'])
    def external(raw):
        return {line.split()[3] for line in raw.splitlines() if not line.split()[3].startswith(('127.','[::1]:','::1:'))}
    def audit_snapshot():
        result={}
        for directory in ('/var/lib/apt','/etc/apt','/var/lib/universal-linux-installer'):
            root=Path(directory)
            for path in [root,*root.rglob('*')] if root.exists() else []:
                st=path.lstat();result[str(path)]=(st.st_ino,st.st_mtime_ns,st.st_size)
        return result
    unchanged=audit_snapshot()
    denied=subprocess.run(['sh',str(BASE/'install.sh'),'--profile',profile,'--audit','--json'],capture_output=True,text=True)
    assert denied.returncode==1 and 'unapproved-apt-source' in denied.stdout,denied.stdout+denied.stderr
    approved=subprocess.run(['sh',str(BASE/'install.sh'),'--profile',profile,'--audit','--allow-mirror','https://mirror.transip.net/ubuntu/ubuntu/','--json'],capture_output=True,text=True)
    assert approved.returncode==0 or (minimum_vm and json.loads(approved.stdout)['failures']==['ram_mib']),approved.stdout+approved.stderr
    assert audit_snapshot()==unchanged,'audit changed target metadata'
    sudo_result=({'status':'SKIPPED-resource-admission-refusal'} if minimum_vm and 'ram_mib' in json.loads(approved.stdout)['failures'] else sudo_evidence(profile))
    assert audit_snapshot()==unchanged,'sudo approval refusal changed target metadata'
    initial=inventory(allow_mirrors=['https://mirror.transip.net/ubuntu/ubuntu/'])
    admission=plan(profile,initial)
    if low_memory:assert initial['ram_mib']>=843,'low-memory fixture has insufficient usable RAM'
    if minimum_vm:
        ram=initial['ram_mib']
        if ram<843:
            # QEMU -m843 includes reserved/kernel memory; physical MemTotal may
            # be below admission. Prove refusal, never falsify the observation.
            assert 'ram_mib' in admission['failures']
            audit=subprocess.run(['sh',str(BASE/'install.sh'),'--profile',profile,'--audit','--allow-mirror','https://mirror.transip.net/ubuntu/ubuntu/','--json'],capture_output=True,text=True)
            assert audit.returncode==1 and 'ram_mib' in json.loads(audit.stdout)['failures']
            directory=Path('/var/lib/universal-linux-installer');directory.mkdir(mode=0o700)
            result={'layer':3,'status':'PASS','scenario':'minimum-VM-physical-RAM-refusal','ram_mib':ram,'live_validated':False,'apply_executed':False,'os_release':identity,'sudo':sudo_result}
            (directory/'e2e-result.json').write_text(json.dumps(result,indent=2)+'\n')
            return
        assert next(c for c in admission['checks'] if c['id']=='ram_mib')['status']=='WARN'
    if swap_gib:
        path='/e2e-existing-swap'
        checked(['/usr/bin/dd','if=/dev/zero','of='+path,'bs=1M','count='+str(swap_gib*1024),'status=none'])
        # One dense extra system page compensates the mkswap header exactly.
        with open(path,'ab') as stream:stream.write(bytes(os.sysconf('SC_PAGE_SIZE')))
        os.chmod(path,0o600);checked(['/usr/sbin/mkswap',path]);checked(['/usr/sbin/swapon',path])
        # Fixture-owned existing swap: persistence is established BEFORE apply.
        with open('/etc/fstab','a') as stream:stream.write('\n/e2e-existing-swap none swap sw 0 0\n')
    from swap import active_swap
    swap_before_apply=sum(active_swap(checked).values())
    try:
        first=invoke(profile,fault,contention=contention)
        if fault:
            assert first.returncode in (-9,137),first.stdout+first.stderr
            # Check pending actual journals to select the required recovery class.
            pending=[]
            for file in Path('/var/lib/universal-linux-installer').rglob('journal.json'):
                state=json.loads(file.read_text())['state']
                if state.get('pending'):pending.append(state['pending'])
            safe=all(s in ('resolve','cloud-init','apt-refresh','package-preflight','system-updates') for s in pending)
            second=invoke(profile)
            if not safe:
                assert second.returncode==1,second.stdout+second.stderr
                assert 'uncertain-effects-review-required' in second.stdout
                second=invoke(profile,review=True)
            first=second
        assert first.returncode==0,first.stdout+first.stderr
        assert json.loads(first.stdout)['status']=='PASS',first.stdout
        # Bind the fault matrix to first-run events before repeat validation.
        events=sum(len(json.loads(p.read_text())['state']['events']) for p in Path('/var/lib/universal-linux-installer').rglob('journal.json'))
        repeated=invoke(profile)
        assert repeated.returncode==0,repeated.stdout+repeated.stderr
        assert json.loads(repeated.stdout)['status']=='PASS',repeated.stdout
        assert not Path('/usr/sbin/policy-rc.d').exists()
        sockets=checked(['/usr/bin/ss','-H','-ltn'])
        assert external(sockets)==external(before_sockets),'new listener outside loopback'
        for line in sockets.splitlines():
            address=line.split()[3]
            if address.rsplit(':',1)[-1] in ('8080','5432'):
                assert address.startswith(('127.0.0.1:','[::1]:','::1:')),address
        if profile!='DB':
            checked(['/usr/sbin/nginx','-t'])
            assert 'Installer ready' in checked(['/usr/bin/curl','--fail','--silent','http://127.0.0.1:8080/'])
            assert checked(['/usr/bin/node','--version']).startswith('v22.')
            assert checked(['/usr/bin/npm','--version']).startswith('9.')
            assert checked(['/usr/bin/dotnet','--list-sdks']).startswith('10.')
            assert '20.3.39' in checked(['/opt/universal-linux-installer/angular/node_modules/.bin/ng','version'])
            assert '0.128.0' in checked(['/opt/universal-linux-installer/codex/node_modules/.bin/codex','--version'])
        if profile!='APP':
            checked(['/usr/bin/pg_isready','-h','127.0.0.1'])
            policy=checked(['/usr/sbin/runuser','-u','postgres','--','/usr/bin/psql','-X','-A','-t','-c',"SELECT current_setting('password_encryption'),current_setting('listen_addresses')"])
            assert policy.strip()=='scram-sha-256|localhost',policy
        from swap import active_swap
        total=sum(active_swap(checked).values())
        assert total>=4*2**30
        if swap_gib:assert '/e2e-existing-swap' in active_swap(checked)
        if swap_gib>=4:assert not Path('/var/lib/universal-linux-installer/swap/swapfile').exists()
        result={'journal_events':events,'layer':3,'profile':profile,'status':sudo_result['status'],'installation_status':'PASS','swap_initial_gib':swap_gib,'swap_before_apply_bytes':swap_before_apply,'fault_event':fault,
                'contention':contention,'contention_fixture':'injected-real-frontend-lock+actual-unattended-dry-run' if contention else None,'live_validated':False,'owner_acceptance_required':True,'mirror_fixture':'owner-supplied-fields-not-captured-file','development':profile!='DB','sudo':sudo_result,'os_release':identity,'ram_mib':initial['ram_mib'],'low_memory':low_memory}
        result['coldboot']=False
        if os.environ.get('RC5_E2E_REBOOT')=='1' and result['status']=='PASS' and not fault:
            pending={'result':result.copy(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'external_sockets':sorted(external(before_sockets))}
            reboot_marker.write_text(json.dumps(pending,sort_keys=True)+'\n');reboot_marker.chmod(0o600)
            result['status']='REBOOT_REQUIRED'
        Path('/var/lib/universal-linux-installer/e2e-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    finally:
        pass


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--collect-fixture-evidence':
        collect_fixture_evidence();raise SystemExit(0)
    if len(sys.argv)>1 and sys.argv[1]=='--fault-child':fault_child(int(sys.argv[2]),bool(int(sys.argv[3])),sys.argv[4:])
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True,choices=('APP','DB','APP+DB'))
    parser.add_argument('--swap-gib',type=int,default=0,choices=(0,2,4));parser.add_argument('--fault-event',type=int,default=0)
    parser.add_argument('--minimum-vm',action='store_true');parser.add_argument('--low-memory',action='store_true');parser.add_argument('--contention',action='store_true');args=parser.parse_args()
    run(args.profile,args.swap_gib,args.fault_event,args.contention,args.minimum_vm,args.low_memory)
