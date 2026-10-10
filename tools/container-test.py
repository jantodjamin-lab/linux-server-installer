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

TRANSIP_URI='https://mirror.transip.net/ubuntu/ubuntu/'


def use_supplied_transip_sources():
    """Disposable-container mutation, reconstructed from supplied source fields.

    No claim is made that this is the provider's captured cloud-init file.
    Existing source files remain preserved with an APT-ignored suffix.
    """
    if not Path('/.dockerenv').exists():raise ValueError('container-only-source-fixture')
    directory=Path('/etc/apt/sources.list.d')
    paths=[Path('/etc/apt/sources.list')]+sorted(directory.glob('*'))
    for path in paths:
        if path.name!='sources.list' and path.suffix not in ('.list','.sources'):continue
        if path.exists():path.rename(path.with_name(path.name+'.rc5-original'))
    target=directory/'rc5-transip-supplied.sources'
    target.write_text('Types: deb\nURIs: '+TRANSIP_URI+'\n'
                      'Suites: resolute resolute-updates resolute-security\n'
                      'Components: main universe restricted multiverse\n'
                      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
    target.chmod(0o644)


def resolve_profiles(reports, source_label, mirrors=(), development=False):
    app_pins=None
    for profile in PROFILES:
        data=inventory(allow_mirrors=mirrors)
        assert data['os']=={'ID':'ubuntu','VERSION_ID':'26.04'}
        assert data['sources_valid']
        # Package-only test admission: the container has overlayfs, no systemd,
        # and no 4GiB swap. These explicit synthetic observations are NOT e2e.
        data.update(cpu=1,ram_mib=4096,disk_gib=100,swap_bytes=4*2**30,
                    swap_disk_bytes=100*2**30,swap_mount_rw=True,filesystem='overlay',
                    target=hashlib.sha256(b'disposable-container-package-test').hexdigest())
        dev=development and profile!='DB'
        print('Resolving '+source_label+' '+profile,flush=True)
        workflow=resolve(profile,data,command,refresh_metadata=True,system_updates=True,
                         require_systemd=False,allow_mirrors=mirrors,development=dev)
        assert validate_lock(workflow['lock'],profile,dev)==workflow['lock']
        assert verify_releases('/',command,mirrors)
        pins={**workflow['lock']['apt'],**workflow['lock']['updates']}
        command(['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-s','install',*[name+'='+version for name,version in sorted(pins.items())]])
        if profile=='APP':app_pins=pins
        print(source_label,profile,workflow['resolution'],flush=True)
        reports.append({'source':source_label,'allow_mirrors':list(mirrors),
                        'development':dev,'profile':profile,'status':'PASS',
                        'node_npm':{n:pins.get(n) for n in ('nodejs','npm')},
                        'resolution':workflow['resolution']})
    return app_pins


def main():
    if not Path('/.dockerenv').exists():raise SystemExit('container-only test')
    assert json.loads((BASE/'profiles/profiles.json').read_text()) == PROFILES
    print('Layer 2: real package tools; capacity/systemd admission is covered by units/VM only',flush=True)
    assert verify_key('/',command)
    raw_swap=command(['/usr/sbin/swapon','--show=NAME,SIZE','--bytes','--noheadings','--raw'])
    print('real util-linux swap rows:',repr(raw_swap),flush=True)
    print('real active_swap:',active_swap(lambda _:raw_swap),flush=True)
    reports=[]
    resolve_profiles(reports,'canonical-image-sources')
    use_supplied_transip_sources()
    app_pins=resolve_profiles(reports,'operator-supplied-transip-fields',
                              [TRANSIP_URI],development=True)
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


if __name__=='__main__':
    from errors import CommandError, failure_metadata
    try:main()
    except CommandError as error:
        print(json.dumps(failure_metadata('layer2',error)),file=sys.stderr)
        print(error.stderr_tail,file=sys.stderr)
        raise SystemExit(1) from None
