"""Layer 2: real signed sources, resolver, closure and Ubuntu npm9; no services/swap."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'lib'))
from core import inventory, PROFILES
from local import command, check_npm_lock, APT_SECURITY
from node import verify_key, verify_releases
from resolve import resolve, npm_pins, simulation_changes
from swap import active_swap
from workflow import validate_lock


def main():
    if not Path('/.dockerenv').exists():raise SystemExit('container-only test')
    assert json.loads((BASE/'profiles/profiles.json').read_text()) == PROFILES
    print('Layer 2: real package tools; capacity/systemd admission is covered by units/VM only',flush=True)
    assert verify_key('/',command)
    raw_swap=command(['/usr/sbin/swapon','--show','--bytes','--noheadings','--raw','--output','NAME,SIZE'])
    print('real util-linux swap rows:',repr(raw_swap),flush=True)
    print('real active_swap:',active_swap(lambda _:raw_swap),flush=True)
    reports=[]
    for profile in PROFILES:
        data=inventory()
        assert data['os']=={'ID':'ubuntu','VERSION_ID':'26.04'}
        assert data['sources_valid']
        # Package-only test admission: the container has overlayfs, no systemd,
        # and no 4GiB swap. These explicit synthetic observations are NOT e2e.
        data.update(cpu=1,ram_mib=4096,disk_gib=100,swap_bytes=4*2**30,
                    swap_disk_bytes=100*2**30,swap_mount_rw=True,filesystem='overlay',
                    target=hashlib.sha256(b'disposable-container-package-test').hexdigest())
        workflow=resolve(profile,data,command,refresh_metadata=True,system_updates=True,require_systemd=False)
        assert validate_lock(workflow['lock'],profile,False)==workflow['lock']
        assert verify_releases('/',command)
        pins={**workflow['lock']['apt'],**workflow['lock']['updates']}
        command(['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-s','install',*[name+'='+version for name,version in sorted(pins.items())]])
        if profile=='APP':app_pins=pins
        print(profile,workflow['resolution'],flush=True)
        reports.append({'profile':profile,'status':'PASS','node_npm':{n:pins.get(n) for n in ('nodejs','npm')},'resolution':workflow['resolution']})
    # The only real package installation in this layer is in the disposable
    # container. Use exact runtime pins produced by the Ubuntu resolver.
    raw=command(['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-s','install',*[n+'='+app_pins[n] for n in ('nodejs','npm')]])
    runtime_pins={n:app_pins[n] for n in ('nodejs','npm')}
    runtime_pins.update(simulation_changes(raw))
    assert all(app_pins.get(n)==v for n,v in runtime_pins.items())
    command(['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-y','install',*[n+'='+v for n,v in sorted(runtime_pins.items())]])
    assert command(['/usr/bin/npm','--version']).strip().startswith('9.')
    for name,pin in npm_pins('APP',True).items():
        folder='angular' if name=='@angular/cli' else 'codex'
        check_npm_lock(BASE/'bundle'/folder,name,pin)
        with tempfile.TemporaryDirectory(prefix='npm9-closure-') as directory:
            directory=Path(directory)
            for filename in ('package.json','package-lock.json'):
                (directory/filename).write_bytes((BASE/'bundle'/folder/filename).read_bytes())
            command(['/usr/bin/npm','ci','--ignore-scripts','--omit=dev','--no-audit','--no-fund','--registry=https://registry.npmjs.org'],cwd=str(directory))
            check_npm_lock(directory,name,pin)
            assert json.loads((directory/'node_modules'/name/'package.json').read_text())['version']==pin['version']
            print('Ubuntu npm9 ci '+name+': PASS',flush=True)
    output=Path(os.environ.get('RC5_TEST_OUTPUT','/tmp/rc5-layer2.json'))
    output.write_text(json.dumps({'layer':2,'status':'PASS','live_validated':False,'profiles':reports},indent=2)+'\n')


if __name__=='__main__':main()
