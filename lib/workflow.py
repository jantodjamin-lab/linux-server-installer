"""Reviewable local installation workflow; no commands run while planning."""
import copy
import re
from core import PROFILES, digest, plan

APT_NAMES = re.compile(r'[a-z0-9][a-z0-9+.-]*\Z')
APT_VERSION = re.compile(r'[0-9][A-Za-z0-9.+:~_-]*\Z')
SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')


def validate_lock(lock, profile, development):
    if not isinstance(lock, dict) or set(lock) != {'schema', 'apt', 'npm', 'updates'} or lock['schema'] != 2:
        raise ValueError('lock-schema')
    for field in ('apt', 'npm', 'updates'):
        if not isinstance(lock[field], dict):
            raise ValueError('lock-map')
    required = set(PROFILES[profile]['packages']) | {'ca-certificates'}
    apt = lock['apt']
    if not required <= set(apt):
        raise ValueError('profile-package-set')
    for name, version in {**apt, **lock['updates']}.items():
        if not APT_NAMES.fullmatch(name) or not isinstance(version, str) or not APT_VERSION.fullmatch(version):
            raise ValueError('apt-pin')
    if set(apt) & set(lock['updates']):
        raise ValueError('duplicate-update')
    if profile != 'DB':
        if not apt['dotnet-sdk-10.0'].split(':')[-1].startswith('10.'):
            raise ValueError('dotnet-major')
        from node import compatible_node_npm
        if not compatible_node_npm(apt):
            raise ValueError('node-angular-compatibility')
    if profile != 'APP' and not apt['postgresql-18'].split(':')[-1].startswith('18.'):
        raise ValueError('postgresql-major')
    npm_required = set() if profile == 'DB' else {'@angular/cli'}
    if development:
        if profile == 'DB':
            raise ValueError('codex-app-only')
        npm_required.add('@openai/codex')
    if set(lock['npm']) != npm_required:
        raise ValueError('npm-package-set')
    for name, pin in lock['npm'].items():
        if not isinstance(pin, dict) or set(pin) != {'version', 'lock_sha256'}:
            raise ValueError('npm-pin')
        if not isinstance(pin['version'], str) or not SEMVER.fullmatch(pin['version']):
            raise ValueError('npm-version')
        if name == '@angular/cli' and not pin['version'].startswith('20.'):
            raise ValueError('angular-major')
        if not isinstance(pin['lock_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', pin['lock_sha256']):
            raise ValueError('npm-lock-checksum')
    return copy.deepcopy(lock)


def build_workflow(profile, observed, lock, development=False, system_updates=False):
    lock = validate_lock(lock, profile, development)
    audit = plan(profile, observed)
    ports = observed.get('tcp_ports', [])
    owned = observed.get('managed', False)
    if not owned and any(port in ports for port in ([8080] if profile == 'APP' else [5432] if profile == 'DB' else [8080, 5432])):
        raise ValueError('existing-listener-conflict')
    if audit['failures']:
        raise ValueError('preflight-failed')
    if lock['updates'] and not system_updates:
        raise ValueError('system-update-approval-required')
    for name, version in {**lock['apt'], **lock['updates']}.items():
        current = observed.get('packages', {}).get(name)
        if current and current != version and name not in lock['updates']:
            raise ValueError('existing-version-conflict')
    steps = [{'id':'sources','kind':'sources'}, {'id':'apt-refresh','kind':'apt-refresh'},
             {'id':'package-preflight','kind':'apt-preflight','pins':{**lock['apt'],**lock['updates']}},
             {'id':'swap','kind':'swap','reserve_bytes':PROFILES[profile]['disk_gib']*2**30}]
    if lock['updates']:
        steps.append({'id':'system-updates','kind':'apt','pins':lock['updates']})
    steps.append({'id': 'packages', 'kind': 'apt', 'pins': lock['apt']})
    if profile != 'DB':
        steps.append({'id': 'app-config', 'kind': 'app-config'})
        for name, pin in lock['npm'].items():
            steps.append({'id': 'angular' if name == '@angular/cli' else 'codex', 'kind': 'npm', 'name': name, **pin})
    if profile != 'APP':
        steps.append({'id': 'db-config', 'kind': 'db-config'})
    steps.append({'id': 'validate', 'kind': 'validate', 'profile': profile, 'development': development})
    body = {'schema': 4, 'profile': profile, 'development': development, 'system_updates': system_updates,
            'lock': lock, 'steps': steps, 'target': observed.get('target', 'unverified'),
            'status': 'WARN', 'live_validated': False,
            'effects': ['explicit Ubuntu universe Node 22 LTS/npm 9 source', 'signed Ubuntu apt refresh', 'deficit-only persistent swap to 4 GiB', 'exact-version package installs',
                       'explicitly pinned updates only', 'new loopback services',
                       'npm ci with integrity lock and scripts disabled'],
            'arch': observed['arch'], 'capacity':audit['capacity'], 'warnings':audit['warnings'], 'observations_sha256': digest(observed)}
    body['plan_id'] = digest(body)
    return body
