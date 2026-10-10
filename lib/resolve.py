"""Authorized, on-target exact APT closure; reviewed public npm locks are shipped."""
import json
from pathlib import Path
import re
from core import BASE, PROFILES, digest
from local import APT_SECURITY, LocalRunner, check_npm_lock
from node import verify_key, verify_releases
from sources import validate_sources
from workflow import build_workflow, validate_lock

INST = re.compile(r'Inst ([a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?)(?: \[([^]]+)\])? \(([^ ]+)')


def simulation_changes(output):
    changes = {}
    for line in output.splitlines():
        if line.startswith('Remv '): raise ValueError('package-removal-refused')
        if line.startswith('Inst '):
            match = INST.match(line)
            if not match: raise ValueError('apt-simulation-format')
            name, previous, version = match.groups()
            if ':' in name: raise ValueError('foreign-architecture-package-refused')
            if name in changes and changes[name] != version: raise ValueError('apt-simulation-format')
            changes[name] = version
    return changes


def npm_pins(profile, development=False, bundle=None):
    if profile == 'DB':
        if development: raise ValueError('codex-app-only')
        return {}
    pins = json.loads((BASE/'profiles/npm-pins.json').read_text())
    names = ['@angular/cli'] + (['@openai/codex'] if development else [])
    selected = {name:pins[name] for name in names}
    for name, pin in selected.items():
        check_npm_lock(Path(bundle or BASE/'bundle')/('angular' if name=='@angular/cli' else 'codex'), name, pin)
    return selected


def resolve(profile, observed, call, *, root='/', development=False, system_updates=False,
            allow_mirrors=(), allow_proxy_env=False, bundle=None, refresh_metadata=False,
            max_new_packages=1000, max_updates=100, authorization=None, require_systemd=True):
    if not refresh_metadata: raise ValueError('refresh-metadata-authorization-required')
    root=Path(root)
    validate_sources(root,allow_mirrors); verify_key(root,call)
    pins_npm=npm_pins(profile,development,bundle)
    # This mutation is reached only after explicit apply or refresh authorization.
    call(['/usr/bin/apt-get', *APT_SECURITY, 'update'])
    verify_releases(root,call,allow_mirrors)
    required=sorted(set(PROFILES[profile]['packages'])|{'ca-certificates'})
    # First unpinned solve. Explicit candidate roots below prevent keeping obsolete
    # cloud-image versions whose metadata has been removed from the archive.
    argv=['/usr/bin/apt-get',*APT_SECURITY,'--no-remove','--no-install-recommends','-s','install']
    simulation_changes(call([*argv,*required]))
    candidates={}
    for name in required:
        output=call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','policy',name])
        match=re.search(r'^\s*Candidate:\s*(\S+)',output,re.M)
        if not match or match[1]=='(none)': raise ValueError('pinned-package-unavailable')
        candidates[name]=match[1]
    changes=simulation_changes(call([*argv,*[name+'='+version for name,version in sorted(candidates.items())]]))
    pins={**candidates,**changes}
    installed={}
    raw=call(['/usr/bin/dpkg-query','-W','-f=${Package}\t${Version}\t${Status}\n'])
    for line in raw.splitlines():
        name,version,status=line.split('\t',2)
        if status=='install ok installed': installed[name]=version
    updates={name:version for name,version in pins.items() if name in installed and installed[name]!=version}
    apt={name:version for name,version in pins.items() if name not in updates}
    new=[name for name in pins if name not in installed]
    if updates and not system_updates: raise ValueError('system-update-approval-required')
    if len(new)>max_new_packages: raise ValueError('new-package-limit-exceeded')
    if len(updates)>max_updates: raise ValueError('update-limit-exceeded')
    # No downgrade even if APT's simulation would accept the exact old pin.
    for name,version in updates.items():
        try: call(['/usr/bin/dpkg','--compare-versions',version,'ge',installed[name]])
        except RuntimeError: raise ValueError('package-downgrade-refused') from None
    lock=validate_lock({'schema':2,'apt':apt,'updates':updates,'npm':pins_npm},profile,development)
    observed=dict(observed,packages=installed,package_candidates=candidates)
    # The container layer lacks systemd; only that check is bypassed by its harness.
    if not require_systemd:
        observed['service_manager']=True
        observed['services']={s:'container-test-only' for s in PROFILES[profile]['services']}
    # Self-test through the exact executor method without its effectful constructor.
    checker=object.__new__(LocalRunner)
    checker.root=root; checker.transport=lambda argv,cwd=None:call(argv)
    checker.workflow={'allow_mirrors':list(allow_mirrors),'allow_proxy_env':allow_proxy_env}
    checker.package_preflight(pins)
    workflow=build_workflow(profile,observed,lock,development,system_updates,
                            allow_mirrors=allow_mirrors,allow_proxy_env=allow_proxy_env,authorization=authorization)
    workflow['resolution']={'new_packages':len(new),'updates':len(updates),
                            'download_bytes':None,'disk_bytes':None,'estimate':'APT simulation; sizes not supplied by simulation'}
    # Use apt-cache's authenticated package size metadata for real estimates.
    download=0; disk=0
    for name in changes:
        output=call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','show',name+'='+pins[name]])
        size=re.search(r'^Size:\s*(\d+)\s*$',output,re.M)
        installed_size=re.search(r'^Installed-Size:\s*(\d+)\s*$',output,re.M)
        if size and installed_size: download+=int(size[1]); disk+=int(installed_size[1])*1024
        else: download=None; disk=None; break
    workflow['resolution'].update(download_bytes=download,disk_bytes=disk,estimate='upper-bound installed size for changed packages; excludes npm and swap')
    workflow['plan_id']=digest({k:v for k,v in workflow.items() if k!='plan_id'})
    return workflow
