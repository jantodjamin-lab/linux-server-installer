"""ONLY inside the disposable, explicitly seeded local VM; no remote interface."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'lib'))
from apply import request
from core import inventory
from cli import main
from journal import Journal


def checked(argv):return subprocess.run(argv,check=True,text=True,capture_output=True).stdout


def args_for(profile):
    return argparse.Namespace(profile=profile,apply=True,resolve=False,development=False,
            system_updates=True,allow_mirror=[],allow_proxy_env=False,no_wait_cloud_init=False,
            max_new_packages=1000,max_updates=100,npm_bundle=None,state_dir='/var/lib/universal-linux-installer/checkpoints')


def invoke(profile, kill_event=0, review=False, contention=False):
    data=inventory();data['target']=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
    intent=request(args_for(profile),data)
    argv=['sh',str(BASE/'install.sh'),'--profile',profile,'--apply','--system-updates',
          '--snapshot-confirmed','--allow-unvalidated','--approval','INSTALL:'+intent['request_id'],'--show-diagnostics','--json']
    if review:argv.append('--recovery-reviewed')
    if kill_event or contention:
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--fault-child',str(kill_event),str(int(contention)),*argv[2:]]
    return subprocess.run(argv,check=False,capture_output=True,text=True)


def fault_child(event, contention, argv):
    # Test-only deterministic fault hook; NEVER shipped as a target CLI flag or
    # activated through a production environment variable.
    original=Journal.event;counter=0;locker=None;started=None
    def fault(journal,*args,**kwargs):
        nonlocal counter,locker,started
        original(journal,*args,**kwargs);counter+=1
        if event and counter==event:os.kill(os.getpid(),signal.SIGKILL)
        if contention and args==('STARTED','packages'):
            blocker="import fcntl,time;f=open('/var/lib/dpkg/lock-frontend','a');fcntl.lockf(f,fcntl.LOCK_EX);time.sleep(25)"
            locker=subprocess.Popen(['/usr/bin/unattended-upgrade','-c',blocker],executable='/usr/bin/python3')
            time.sleep(1);started=time.monotonic()
        if contention and args==('VALIDATED','packages'):
            assert time.monotonic()-started>=23,'APT did not wait on dpkg contention'
            locker.wait(timeout=60)
    Journal.event=fault
    sys.argv=['installer',*argv];raise SystemExit(main())


def run(profile, swap_gib=0, fault=0, contention=False):
    if os.geteuid()!=0 or not Path('/etc/universal-installer-disposable-e2e').is_file() or not Path('/run/systemd/system').is_dir():
        raise SystemExit('Refusing: disposable VM marker/root/systemd required')
    if swap_gib:
        path='/e2e-existing-swap'
        checked(['/usr/bin/dd','if=/dev/zero','of='+path,'bs=1M','count='+str(swap_gib*1024),'status=none'])
        os.chmod(path,0o600);checked(['/usr/sbin/mkswap',path]);checked(['/usr/sbin/swapon',path])
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
        repeated=invoke(profile)
        assert repeated.returncode==0,repeated.stdout+repeated.stderr
        assert json.loads(repeated.stdout)['status']=='PASS',repeated.stdout
        assert not Path('/usr/sbin/policy-rc.d').exists()
        sockets=checked(['/usr/bin/ss','-H','-ltn'])
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
        if profile!='APP':
            checked(['/usr/bin/pg_isready','-h','127.0.0.1'])
            policy=checked(['/usr/sbin/runuser','-u','postgres','--','/usr/bin/psql','-X','-A','-t','-c',"SELECT current_setting('password_encryption'),current_setting('listen_addresses')"])
            assert policy.strip()=='scram-sha-256|localhost',policy
        from swap import active_swap
        total=sum(active_swap(checked).values())
        assert total>=4*2**30
        if swap_gib:assert '/e2e-existing-swap' in active_swap(checked)
        if swap_gib>=4:assert not Path('/var/lib/universal-linux-installer/swap/swapfile').exists()
        events=sum(len(json.loads(p.read_text())['state']['events']) for p in Path('/var/lib/universal-linux-installer').rglob('journal.json'))
        result={'journal_events':events,'layer':3,'profile':profile,'status':'PASS','swap_initial_gib':swap_gib,'fault_event':fault,
                'contention':contention,'live_validated':False,'owner_acceptance_required':True}
        Path('/var/lib/universal-linux-installer/e2e-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    finally:
        pass


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fault-child':fault_child(int(sys.argv[2]),bool(int(sys.argv[3])),sys.argv[4:])
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True,choices=('APP','DB','APP+DB'))
    parser.add_argument('--swap-gib',type=int,default=0,choices=(0,2,4));parser.add_argument('--fault-event',type=int,default=0)
    parser.add_argument('--contention',action='store_true');args=parser.parse_args()
    run(args.profile,args.swap_gib,args.fault_event,args.contention)
