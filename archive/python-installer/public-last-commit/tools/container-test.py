"""Layer 2: real signed sources, resolver, closure and Ubuntu npm9; no services/swap."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'lib'))
from core import inventory, plan, PROFILES
from errors import CommandError, PreflightError, failure_metadata, redact
from local import command, check_npm_lock, APT_SECURITY
from node import verify_key, verify_releases
from resolve import resolve, npm_pins, simulation_changes
from swap import active_swap
from workflow import validate_lock

TRANSIP_URI='https://mirror.transip.net/ubuntu/ubuntu/'


def save_report(reports, status='RUNNING'):
    output=Path(os.environ.get('RC5_TEST_OUTPUT','/tmp/rc5-layer2.json'))
    output.write_text(json.dumps({'layer':2,'status':status,'live_validated':False,
                                 'profiles':reports},indent=2)+'\n')


def container_audit(profile, data):
    admission=dict(data,service_manager=True,
                   services={s:'container-test-only' for s in PROFILES[profile]['services']})
    return plan(profile,admission)


def bounded_observations(profile, data):
    """Expose failed probe stages without installed-package dumps or raw stderr."""
    audit=container_audit(profile,data)
    safe_code=lambda value: isinstance(value,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,95}',value)
    diagnostics=[{key:value for key,value in row.items()
                  if key in ('stage','code','tool') and safe_code(value)}
                 for row in data.get('diagnostics',[])[:32]]
    return {'errors':[value for value in data.get('errors',[])[:32] if safe_code(value)],
            'diagnostics':diagnostics,'source_policy_valid':data.get('source_policy_valid') is True,
            'key_valid':data.get('key_valid') is True,
            'source_metadata':redact(str(data.get('source_metadata','unknown')))[:128],
            'candidate_count':sum(value is not None for value in data.get('package_candidates',{}).values()),
            'checks':[{'id':row['id'],'status':row['status'],
                       'detail':redact(str(row['detail']))[:512]} for row in audit['checks']]}


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
        # Emulated arm64 tools can exceed the production audit's 15s timeout.
        # Only this isolated harness uses the existing 1800s command boundary;
        # failed probes remain hard failures and are persisted before resolving.
        data=inventory(query_fn=command,allow_mirrors=mirrors)
        # Package-only test admission: the container has overlayfs, no systemd,
        # and no 4GiB swap. These explicit synthetic observations are NOT e2e.
        data.update(cpu=1,ram_mib=4096,disk_gib=100,swap_bytes=4*2**30,
                    swap_disk_bytes=100*2**30,swap_mount_rw=True,filesystem='overlay',
                    target=hashlib.sha256(b'disposable-container-package-test').hexdigest())
        dev=development and profile!='DB'
        report={'source':source_label,'allow_mirrors':list(mirrors),
                'development':dev,'profile':profile,'status':'RUNNING',
                'preflight':bounded_observations(profile,data)}
        reports.append(report); save_report(reports)
        print(json.dumps(report),flush=True)
        print('Resolving '+source_label+' '+profile,flush=True)
        try:
            if data.get('os')!={'ID':'ubuntu','VERSION_ID':'26.04'} or not data.get('sources_valid') or data.get('errors'):
                raise PreflightError(container_audit(profile,data))
            workflow=resolve(profile,data,command,refresh_metadata=True,system_updates=True,
                             require_systemd=False,allow_mirrors=mirrors,development=dev)
        except (ValueError,CommandError) as error:
            report.update(status='FAIL',failure=failure_metadata('layer2-resolve',error))
            save_report(reports,'FAIL');print(json.dumps(report),file=sys.stderr,flush=True)
            raise
        assert validate_lock(workflow['lock'],profile,dev)==workflow['lock']
        assert verify_releases('/',command,mirrors)
        pins={**workflow['lock']['apt'],**workflow['lock']['updates']}
        command(['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-s','install',*[name+'='+version for name,version in sorted(pins.items())]])
        if profile=='APP':app_pins=pins
        print(source_label,profile,workflow['resolution'],flush=True)
        report.update(status='PASS',node_npm={n:pins.get(n) for n in ('nodejs','npm')},
                      resolution=workflow['resolution'])
        save_report(reports)
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
    save_report(reports,'PASS')


if __name__=='__main__':
    try:main()
    except CommandError as error:
        print(json.dumps(failure_metadata('layer2',error)),file=sys.stderr)
        print(error.stderr_tail,file=sys.stderr)
        raise SystemExit(1) from None
    except ValueError as error:
        print(json.dumps(failure_metadata('layer2',error)),file=sys.stderr)
        raise SystemExit(1) from None
