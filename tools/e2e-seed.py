"""Build isolated NoCloud seed and local serial-driven guest acceptance service."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

base=Path(os.environ['RC5_E2E_BASE']);work=Path(os.environ['RC5_E2E_WORK']);profile=os.environ['RC5_E2E_PROFILE']
scenarios=[{'swap':0,'memory':4096,'fault':0,'contention':False}]
if os.environ.get('RC5_E2E_MATRIX')=='1' or os.environ.get('RC5_E2E_SECURITY')=='1':
    scenarios += [{'swap':s,'memory':4096,'fault':0,'contention':False} for s in (2,4)]
    scenarios += [{'swap':0,'memory':843,'fault':0,'contention':False}, {'swap':0,'memory':4096,'fault':0,'contention':True}]
if os.environ.get('RC5_E2E_ONLY_FAULTS')=='1':
    scenarios=[{'swap':0,'memory':4096,'fault':n,'contention':False} for n in range(1,int(os.environ['RC5_E2E_FAULT_EVENTS'])+1)]
if os.environ.get('RC5_E2E_SCENARIO'):
    selected=os.environ['RC5_E2E_SCENARIO']
    variants={'swap2':{'swap':2,'memory':4096,'fault':0,'contention':False},
              'swap4':{'swap':4,'memory':4096,'fault':0,'contention':False},
              'minimum':{'swap':0,'memory':843,'fault':0,'contention':False},
              'low-memory':{'swap':0,'memory':896,'fault':0,'contention':False},
              'contention':{'swap':0,'memory':4096,'fault':0,'contention':True}}
    if selected not in variants:raise ValueError('Invalid isolated security scenario')
    scenarios=[variants[selected]]
if os.environ.get('RC5_E2E_FAULT_EVENT'):
    event=int(os.environ['RC5_E2E_FAULT_EVENT'])
    if not 1<=event<=256:raise ValueError('Invalid isolated fault event')
    scenarios=[{'swap':0,'memory':4096,'fault':event,'contention':False}]
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
    for directory in ('lib','profiles','bundle','tools'):
        for path in sorted((base/directory).rglob('*')):
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts:archive.add(path,arcname=str(path.relative_to(base)),recursive=False)
    archive.add(base/'install.sh',arcname='install.sh')
for i,scenario in enumerate(scenarios):
    case=work/('case-'+str(i+(100 if os.environ.get('RC5_E2E_ONLY_FAULTS')=='1' else 0)).zfill(3));case.mkdir();(case/'artifacts').mkdir()
    (case/'memory').write_text(str(scenario['memory'])+'\n')
    extra=(' --contention' if scenario['contention'] else '')+(' --minimum-vm' if scenario['memory']<1024 else '')
    if scenario['memory']==896:extra+=' --low-memory'
    command='python3 -B /opt/rc5-test/tools/e2e-guest.py --profile '+profile+' --swap-gib '+str(scenario['swap'])+' --fault-event '+str(scenario['fault'])+extra
    script='''#!/bin/sh
set +e
mkdir -p /e2e-artifacts
mount -t 9p -o trans=virtio,version=9p2000.L rc5logs /e2e-artifacts
COMMAND > /e2e-artifacts/guest.log 2>&1
rc=$?
python3 -B /opt/rc5-test/tools/e2e-guest.py --collect-fixture-evidence
if [ "$rc" -eq 0 ]; then
  cp /var/lib/universal-linux-installer/e2e-result.json /e2e-artifacts/result.json
else
  printf '{"status":"FAIL","exit_code":%s}\\n' "$rc" > /e2e-artifacts/result.json
fi
tar -czf /e2e-artifacts/private-journals.tar.gz /var/lib/universal-linux-installer 2>/dev/null
sync
systemctl poweroff
'''.replace('COMMAND',command)
    service='[Unit]\nAfter=cloud-final.service\n[Service]\nType=oneshot\nExecStart=/bin/sh /opt/rc5-e2e.sh\n[Install]\nWantedBy=multi-user.target\n'
    config={'package_update':True,'packages':['python3','gpg','gpgv','util-linux','curl','iproute2','unattended-upgrades'],'users':[{'name':'rc5-operator','sudo':'ALL=(ALL) NOPASSWD:ALL','lock_passwd':True}],
            'write_files':[{'path':'/etc/universal-installer-disposable-e2e','content':'isolated-local-qemu\n'},
             {'path':'/opt/rc5-installer.tar.gz','encoding':'b64','content':base64.b64encode(buffer.getvalue()).decode()},
             {'path':'/opt/rc5-e2e.sh','permissions':'0700','content':script},
             {'path':'/etc/systemd/system/rc5-e2e.service','content':service}],
            'runcmd':[['systemctl','disable','--now','apt-daily.timer','apt-daily-upgrade.timer'],['systemctl','stop','apt-daily.service','apt-daily-upgrade.service','unattended-upgrades.service'],['sh','-c',"mkdir -p /etc/apt/sources.list.d; rm -f /etc/apt/sources.list.d/ubuntu.sources; printf '%s\\n' 'Types: deb' 'URIs: https://mirror.transip.net/ubuntu/ubuntu/' 'Suites: resolute resolute-updates resolute-security' 'Components: main universe restricted multiverse' 'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' > /etc/apt/sources.list.d/provider-test.sources"],['apt-get','-o','DPkg::Lock::Timeout=600','update'],['mkdir','-p','/opt/rc5-test'],['tar','-xzf','/opt/rc5-installer.tar.gz','-C','/opt/rc5-test'],
                       ['systemctl','daemon-reload'],['systemctl','enable','rc5-e2e.service'],['systemctl','start','--no-block','rc5-e2e.service']]}
    (case/'user-data').write_text('#cloud-config\n'+json.dumps(config,indent=2)+'\n')
    (case/'meta-data').write_text('instance-id: rc5-disposable-'+str(i)+'\nlocal-hostname: rc5-disposable\n')
    subprocess.run(['cloud-localds',str(case/'seed.img'),str(case/'user-data'),str(case/'meta-data')],check=True)
print('Preserved local VM work:',work)
