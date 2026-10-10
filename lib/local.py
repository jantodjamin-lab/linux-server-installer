"""Local Ubuntu adapter. Constructing it needs explicit target-bound consent.

Tests inject a command transport and filesystem root; development never invokes
live package commands. No SSH, credential loading or remote provisioning; sudo is CLI-only and interactive.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from core import digest

NGINX = '''server {
    listen 127.0.0.1:8080 default_server;
    server_name _;
    root /var/www/universal-installer;
    server_tokens off;
    location / { try_files $uri $uri/ =404; }
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
}
'''
PGCONF = "listen_addresses = 'localhost'\npassword_encryption = 'scram-sha-256'\nssl = on\n"
PGHBA = '''local all postgres peer
local all all peer
host all all 127.0.0.1/32 scram-sha-256
host all all ::1/128 scram-sha-256
'''
SERVICE_BLOCK = '#!/bin/sh\n# universal-linux-installer: block package service starts until validation\nexit 101\n'
APT_SECURITY = ['-o', 'APT::Get::AllowUnauthenticated=false', '-o', 'Acquire::AllowInsecureRepositories=false',
                '-o', 'Acquire::AllowDowngradeToInsecureRepositories=false', '-o', 'APT::Get::allow-Downgrades=false',
                '-o', 'APT::Update::Error-Mode=any', '-o', 'Acquire::Check-Valid-Until=true', '-o', 'Acquire::Check-Date=true',
                '-o', 'Acquire::AllowWeakRepositories=false', '-o', 'DPkg::Lock::Timeout=600',
                '-o', 'Dpkg::Options::=--force-confold']


def command(argv, cwd=None, allow_proxy_env=False):
    from errors import CommandError
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
           'HOME': '/root', 'DEBIAN_FRONTEND': 'noninteractive',
           'NEEDRESTART_MODE': 'l', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
           'NG_CLI_ANALYTICS': 'false', 'NPM_CONFIG_USERCONFIG':'/dev/null',
           'NPM_CONFIG_GLOBALCONFIG':'/nonexistent/universal-npmrc'}
    if allow_proxy_env:
        for key in ('HTTP_PROXY','HTTPS_PROXY','NO_PROXY','http_proxy','https_proxy','no_proxy'):
            if key in os.environ: env[key] = os.environ[key]
    try:
        completed = subprocess.run(argv, cwd=cwd, check=False, capture_output=True, text=True,
                                   timeout=1800, stdin=subprocess.DEVNULL, env=env)
    except subprocess.TimeoutExpired as error:
        tail = error.stderr or ''
        if isinstance(tail, bytes): tail = tail.decode(errors='replace')
        raise CommandError(argv, 124, tail) from None
    if completed.returncode: raise CommandError(argv, completed.returncode, completed.stderr)
    return completed.stdout


from sources import validate_sources as validate_sources, approve_uri as approve_uri


def check_npm_lock(directory, name, pin):
    directory = Path(directory)
    for path in (directory, directory/'package.json', directory/'package-lock.json'):
        if path.is_symlink(): raise ValueError('npm-symlink')
    raw = (directory/'package-lock.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin['lock_sha256']:
        raise ValueError('npm-lock-integrity')
    lock = json.loads(raw)
    package = json.loads((directory/'package.json').read_text())
    if package.get('scripts') or package.get('dependencies') != {name: pin['version']}:
        raise ValueError('npm-root-package')
    if lock.get('lockfileVersion') != 3 or not isinstance(lock.get('packages'), dict):
        raise ValueError('npm-lock-version')
    if lock['packages'].get('', {}).get('dependencies') != package['dependencies']:
        raise ValueError('npm-root-binding')
    if lock['packages'].get('node_modules/'+name, {}).get('version') != pin['version']:
        raise ValueError('npm-version-binding')
    for path, entry in lock['packages'].items():
        if not path: continue
        if not path.startswith('node_modules/') or '..' in path.split('/') or entry.get('link'):
            raise ValueError('npm-package-path')
        url = urlsplit(entry.get('resolved', ''))
        if url.scheme != 'https' or url.hostname != 'registry.npmjs.org' or url.username or url.password or url.query or url.fragment or url.port:
            raise ValueError('npm-registry')
        if not re.fullmatch(r'sha512-[A-Za-z0-9+/]{86}==', entry.get('integrity', '')):
            raise ValueError('npm-sri')
    return True


class LocalRunner:
    def __init__(self, workflow, approval, snapshot_confirmed=False, allow_unvalidated=False,
                 root='/', transport=command, bundle=None):
        if approval != 'INSTALL:'+workflow['plan_id'] or snapshot_confirmed is not True or allow_unvalidated is not True:
            raise ValueError('explicit-plan-snapshot-and-candidate-approval-required')
        body = {k: v for k, v in workflow.items() if k != 'plan_id'}
        if digest(body) != workflow['plan_id']:
            raise ValueError('plan-integrity')
        self.root = Path(root).absolute(); self.transport = transport; self.workflow = workflow
        self.bundle = Path(bundle).absolute() if bundle else None
        self.marker = self.root/'var/lib/universal-linux-installer/ownership.json'
        if self.root == Path('/'):
            from workflow import validate_plan_age
            validate_plan_age(workflow)
            if os.geteuid() != 0: raise ValueError('root-required')
            identity = hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
            if workflow['target'] != identity: raise ValueError('target-binding')
        from swap import SwapManager
        from core import PROFILES
        self.swap = SwapManager(self.root, self.call, PROFILES[workflow['profile']]['disk_gib']*2**30)
        self.swap_report = None
        self.owned = False
        if self.marker.exists():
            if self.marker.is_symlink(): raise ValueError('ownership-symlink')
            previous = json.loads(self.marker.read_text())
            if previous != {'plan_id': workflow['plan_id']}:
                raise ValueError('ownership-binding')
            self.owned = True
        if not self.owned:
            for path in ('etc/nginx', 'etc/postgresql', 'var/lib/postgresql', 'opt/universal-linux-installer', 'usr/sbin/policy-rc.d'):
                item = self.root/path
                if item.exists(): raise ValueError('existing-service-or-data-conflict')
        if self.bundle:
            for name, pin in workflow['lock']['npm'].items():
                check_npm_lock(self.bundle/('angular' if name == '@angular/cli' else 'codex'), name, pin)
        elif workflow['lock']['npm']:
            raise ValueError('npm-bundle-required')

    def execution_lock(self):
        from journal import Journal
        return Journal(self.root/'var/lib/universal-linux-installer/execution', self.workflow['target'])

    def call(self, argv, cwd=None):
        if self.transport is command:
            return command(argv, cwd=cwd, allow_proxy_env=self.workflow.get('allow_proxy_env', False))
        return self.transport(argv, cwd=cwd)

    def check_sources(self):
        from sources import read_sources
        mirrors=self.workflow.get('allow_mirrors',())
        data=read_sources(self.root,mirrors)
        authorized=self.workflow.get('authorization')
        if authorized is not None:
            base=[e for e in data['entries'] if e['source_file']!='universal-node-universe.sources']
            if base!=authorized['source_policy']:raise ValueError('source-policy-changed')
        return True

    def reboot_required(self):
        return (self.root/'var/run/reboot-required').exists()

    def write_new(self, relative, content, mode=0o644):
        path = self.root/relative
        for parent in [path, *path.parents]:
            if parent.is_symlink(): raise ValueError('config-symlink')
        if path.exists():
            if path.read_text() != content: raise ValueError('existing-config-conflict')
            return
        for parent in reversed(path.parents):
            if not parent.exists(): parent.mkdir(mode=0o755)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())

    def apply(self, step):
        kind = step['kind']
        if kind == 'sources':
            self.check_sources()
            from node import verify_key, universe_present, universe_source, SOURCE
            verify_key(self.root, self.call)
            if self.workflow['profile'] != 'DB' and not universe_present(self.root,self.workflow['arch'],self.workflow.get('allow_mirrors',())):
                from sources import BASE_SUITES, universe_coverage
                missing=BASE_SUITES-universe_coverage(self.root,self.workflow['arch'],self.workflow.get('allow_mirrors',()))
                self.write_new(SOURCE, universe_source(self.workflow['arch'],missing,self.root,self.workflow.get('allow_mirrors',())))
                self.check_sources()
            self.write_new('var/lib/universal-linux-installer/ownership.json', json.dumps({'plan_id': self.workflow['plan_id']}), 0o600)
            self.owned = True
            self.write_new('usr/sbin/policy-rc.d', SERVICE_BLOCK, 0o755)
        elif kind == 'apt-preflight':
            self.package_preflight(step['pins'])
        elif kind == 'swap':
            self.swap_report = self.swap.apply()
        elif kind == 'apt-refresh':
            from node import verify_key
            self.check_sources(); verify_key(self.root, self.call)
            self.call(['/usr/bin/apt-get', *APT_SECURITY, 'update'])
            from node import verify_releases
            verify_releases(self.root,self.call,self.workflow.get('allow_mirrors',()))
        elif kind == 'apt':
            self.check_sources()
            from node import verify_key, package_available, verify_releases
            verify_key(self.root, self.call); verify_releases(self.root,self.call,self.workflow.get('allow_mirrors',())); package_available(self.call, step['pins'])
            if (self.root/'usr/sbin/policy-rc.d').read_text() != SERVICE_BLOCK:
                raise ValueError('service-start-guard')
            self.package_preflight(step['pins'])
            pins = [name+'='+version for name, version in sorted(step['pins'].items())]
            self.call(['/usr/bin/apt-get', *APT_SECURITY, '--no-remove', '--no-install-recommends', '-y', 'install', *pins])
        elif kind == 'app-config':
            # Only a fresh, package-created service is allowed by constructor.
            self.write_new('var/www/universal-installer/index.html', '<!doctype html><title>Installer ready</title>Installer ready\n')
            self.write_new('etc/nginx/conf.d/universal-installer.conf', NGINX)
            default = self.root/'etc/nginx/sites-enabled/default'
            if default.exists() or default.is_symlink():
                if not default.is_symlink() or default.resolve() != self.root/'etc/nginx/sites-available/default':
                    raise ValueError('nginx-default-conflict')
                default.unlink()
            self.call(['/usr/sbin/nginx', '-t'])
            self.call(['/usr/bin/systemctl', 'enable', '--now', 'nginx'])
            self.call(['/usr/bin/systemctl', 'reload', 'nginx'])
        elif kind == 'db-config':
            self.write_new('etc/postgresql/18/main/conf.d/90-universal-installer.conf', PGCONF)
            # Preserve Ubuntu's hba file. Verify its effective policy below.
            self.call(['/usr/bin/pg_conftool', '18', 'main', 'set', 'listen_addresses', 'localhost'])
            self.call(['/usr/bin/pg_conftool', '18', 'main', 'set', 'password_encryption', 'scram-sha-256'])
            self.call(['/usr/bin/systemctl', 'enable', '--now', 'postgresql'])
            self.call(['/usr/bin/pg_ctlcluster', '18', 'main', 'restart'])
        elif kind == 'npm':
            source = self.bundle/step['id']
            check_npm_lock(source, step['name'], step)
            destination = self.root/'opt/universal-linux-installer'/step['id']
            for parent in [destination, *destination.parents]:
                if parent.is_symlink(): raise ValueError('npm-destination-symlink')
            destination.mkdir(parents=True, exist_ok=True)
            for name in ('package.json', 'package-lock.json'):
                self.write_new(str(destination.relative_to(self.root)/name), (source/name).read_text())
            self.call(['/usr/bin/npm', 'ci', '--ignore-scripts', '--omit=dev', '--no-audit', '--no-fund', '--registry=https://registry.npmjs.org'], cwd=str(destination))
        elif kind == 'validate':
            if not self.validate(step): raise ValueError('final-validators')
            guard = self.root/'usr/sbin/policy-rc.d'
            if guard.exists():
                if guard.is_symlink() or guard.read_text() != SERVICE_BLOCK: raise ValueError('service-guard-drift')
                guard.unlink()
        else:
            raise ValueError('unknown-step')

    def package_preflight(self, pins):
        from node import verify_key, verify_releases, package_available
        self.check_sources(); verify_key(self.root,self.call)
        verify_releases(self.root,self.call,self.workflow.get('allow_mirrors',())); package_available(self.call,pins)
        for name,version in pins.items():
            current=self.package_version(name)
            if current and current!=version:
                try:self.call(['/usr/bin/dpkg','--compare-versions',version,'ge',current])
                except RuntimeError:raise ValueError('package-downgrade-refused') from None
        argv_pins = [name+'='+version for name, version in sorted(pins.items())]
        simulation = self.call(['/usr/bin/apt-get', *APT_SECURITY, '--no-remove', '--no-install-recommends', '-s', 'install', *argv_pins])
        from resolve import simulation_changes
        changes = simulation_changes(simulation)
        for name,version in changes.items():
            if pins.get(name) != version: raise ValueError('unpinned-dependency')
        for name, version in pins.items():
            if self.package_version(name) != version and changes.get(name) != version:
                raise ValueError('apt-simulation-incomplete')

    def package_version(self, name):
        try:
            return self.call(['/usr/bin/dpkg-query', '-W', '-f=${Version}', name]).strip()
        except RuntimeError:
            return None

    def validate(self, step):
        kind = step['kind']
        if kind == 'sources':
            from node import verify_key, universe_present
            return self.check_sources() and verify_key(self.root,self.call) and (self.workflow['profile']=='DB' or universe_present(self.root,self.workflow['arch'],self.workflow.get('allow_mirrors',())))
        if kind == 'swap': return self.swap.validate()
        if kind == 'apt-preflight':
            self.package_preflight(step['pins']); return True
        if kind == 'apt-refresh': return True  # completed command evidence, no cached freshness claim
        if kind == 'apt': return all(self.package_version(n) == v for n, v in step['pins'].items())
        if kind == 'npm':
            base = self.root/'opt/universal-linux-installer'/step['id']
            check_npm_lock(base, step['name'], step)
            installed = json.loads((base/'node_modules'/step['name']/'package.json').read_text())
            if installed.get('version') != step['version']: return False
            if step['name'] == '@angular/cli':
                return 'Angular CLI: '+step['version'] in self.call([str(base/'node_modules/.bin/ng'), 'version'])
            return self.call([str(base/'node_modules/.bin/codex'), '--version']).strip() == 'codex-cli '+step['version']
        if kind == 'app-config':
            if (self.root/'etc/nginx/conf.d/universal-installer.conf').read_text() != NGINX: return False
            self.call(['/usr/sbin/nginx', '-t'])
            self.call(['/usr/bin/systemctl', 'is-active', 'nginx'])
            return self.call(['/usr/bin/curl', '--fail', '--silent', '--max-time', '5', 'http://127.0.0.1:8080/']).strip().endswith('Installer ready')
        if kind == 'db-config':
            base = self.root/'etc/postgresql/18/main'
            if (base/'conf.d/90-universal-installer.conf').read_text() != PGCONF: return False
            # Refuse trust, remote networks and password methods weaker than SCRAM.
            for line in (base/'pg_hba.conf').read_text().splitlines():
                row = line.split('#', 1)[0].split()
                if not row: continue
                if row[0] == 'local':
                    if row[-1] != 'peer': return False
                elif row[0] in ('host', 'hostssl', 'hostnossl'):
                    if len(row) != 5 or row[3] not in ('127.0.0.1/32', '::1/128') or row[-1] != 'scram-sha-256': return False
                else: return False
            self.call(['/usr/bin/pg_isready', '-h', '127.0.0.1', '-p', '5432'])
            values = self.call(['/usr/sbin/runuser', '-u', 'postgres', '--', '/usr/bin/psql', '-X', '-A', '-t', '-c',
                                "SELECT current_setting('listen_addresses'), current_setting('password_encryption'), current_setting('server_version_num')"]).strip().split('|')
            return len(values) == 3 and values[0:2] == ['localhost', 'scram-sha-256'] and values[2].startswith('18')
        if kind == 'validate':
            for item in self.workflow['steps']:
                if item['kind'] not in ('validate', 'apt-refresh') and not self.validate(item): return False
            if step['profile'] != 'DB':
                if not self.call(['/usr/bin/dotnet', '--list-sdks']).startswith('10.'): return False
                from node import check_runtime
                if not check_runtime(self.call,{**self.workflow['lock']['apt'],**self.workflow['lock']['updates']}): return False
            return True
        return False
