"""Local Ubuntu adapter. Constructing it needs explicit target-bound consent.

Tests inject a command transport and filesystem root; development never invokes
live package commands. No SSH, sudo, credential loading or remote provisioning.
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
                '-o', 'Dpkg::Options::=--force-confold']


def command(argv, cwd=None):
    completed = subprocess.run(argv, cwd=cwd, check=False, capture_output=True, text=True,
                               timeout=1800, stdin=subprocess.DEVNULL,
                               env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
                                    'HOME': '/root', 'DEBIAN_FRONTEND': 'noninteractive',
                                    'NEEDRESTART_MODE': 'l', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
                                    'NG_CLI_ANALYTICS': 'false'})
    if completed.returncode:
        # No arbitrary stdout/stderr/exception text in persistent reports.
        raise RuntimeError('local-command-failed')
    return completed.stdout


def validate_sources(root):
    root = Path(root)
    candidates = [root/'etc/apt/sources.list'] + sorted((root/'etc/apt/sources.list.d').glob('*'))
    count = 0
    for path in candidates:
        if not path.exists(): continue
        if path.is_symlink(): raise ValueError('apt-source-symlink')
        text = path.read_text()
        if path.suffix not in ('.list', '.sources') and path.name != 'sources.list':
            continue
        for dangerous in ('trusted=yes', 'allow-insecure=yes', 'Trusted: yes', 'Check-Valid-Until: no'):
            if dangerous in text: raise ValueError('insecure-apt-source')
        if path.suffix == '.sources':
            for paragraph in re.split(r'\n\s*\n', text.strip()):
                fields = {}
                for line in paragraph.splitlines():
                    if line.startswith('#') or not line.strip(): continue
                    if ':' not in line or line.startswith((' ', '\t')): raise ValueError('apt-source-format')
                    key, value = line.split(':', 1); fields[key.lower()] = value.strip()
                if not fields: continue
                if fields.get('trusted', 'no').lower() != 'no' or fields.get('allow-insecure', 'no').lower() != 'no' or fields.get('check-valid-until', 'yes').lower() != 'yes':
                    raise ValueError('insecure-apt-source')
                if fields.get('enabled', 'yes') != 'yes': raise ValueError('disabled-source-review')
                if fields.get('signed-by') != '/usr/share/keyrings/ubuntu-archive-keyring.gpg':
                    raise ValueError('apt-source-keyring')
                for uri in fields.get('uris', '').split():
                    approve_uri(uri); count += 1
                if not fields.get('suites') or any(s not in ('resolute', 'resolute-updates', 'resolute-security') for s in fields['suites'].split()):
                    raise ValueError('apt-suite')
                if fields.get('types') != 'deb': raise ValueError('apt-source-type')
        else:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'): continue
                # Restrictive legacy syntax; options require operator conversion to deb822.
                fields = line.split()
                if len(fields) < 4 or fields[0] != 'deb' or '[' in line:
                    raise ValueError('apt-source-format')
                approve_uri(fields[1]); count += 1
                if fields[2] not in ('resolute', 'resolute-updates', 'resolute-security'):
                    raise ValueError('apt-suite')
    if not count: raise ValueError('no-approved-apt-sources')
    key = root/'usr/share/keyrings/ubuntu-archive-keyring.gpg'
    if key.is_symlink() or not key.is_file(): raise ValueError('ubuntu-keyring-required')
    return True


def approve_uri(uri):
    parts = urlsplit(uri)
    if parts.scheme not in ('http', 'https') or parts.hostname not in ('archive.ubuntu.com', 'security.ubuntu.com', 'ports.ubuntu.com') or parts.username or parts.password or parts.query or parts.fragment or parts.port:
        raise ValueError('unapproved-apt-source')
    if parts.path.rstrip('/') not in ('/ubuntu', '/ubuntu-ports'):
        raise ValueError('apt-source-path')
    # HTTP Ubuntu mirrors are authenticated by signed apt metadata, not transport.


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
            if os.geteuid() != 0: raise ValueError('root-required')
            identity = hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
            if workflow['target'] != identity: raise ValueError('target-binding')
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
        return self.transport(argv, cwd=cwd)

    def reboot_required(self):
        return (self.root/'var/run/reboot-required').exists()

    def write_new(self, relative, content, mode=0o644):
        path = self.root/relative
        for parent in [path, *path.parents]:
            if parent.is_symlink(): raise ValueError('config-symlink')
        if path.exists():
            if path.read_text() != content: raise ValueError('existing-config-conflict')
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())

    def apply(self, step):
        kind = step['kind']
        if kind == 'sources':
            validate_sources(self.root)
            self.write_new('var/lib/universal-linux-installer/ownership.json', json.dumps({'plan_id': self.workflow['plan_id']}), 0o600)
            self.owned = True
            self.write_new('usr/sbin/policy-rc.d', SERVICE_BLOCK, 0o755)
        elif kind == 'apt-refresh':
            self.call(['/usr/bin/apt-get', *APT_SECURITY, 'update'])
        elif kind == 'apt':
            validate_sources(self.root)
            if (self.root/'usr/sbin/policy-rc.d').read_text() != SERVICE_BLOCK:
                raise ValueError('service-start-guard')
            pins = [name+'='+version for name, version in sorted(step['pins'].items())]
            simulation = self.call(['/usr/bin/apt-get', *APT_SECURITY, '--no-remove', '--no-install-recommends', '-s', 'install', *pins])
            changes = {}
            for line in simulation.splitlines():
                if line.startswith('Remv '): raise ValueError('package-removal-refused')
                if line.startswith('Inst '):
                    match = re.match(r'Inst ([a-z0-9+.-]+)(?: \[[^]]+\])? \(([^ ]+)', line)
                    if not match: raise ValueError('apt-simulation-format')
                    name, version = match.groups()
                    if step['pins'].get(name) != version: raise ValueError('unpinned-dependency')
                    changes[name] = version
            for name, version in step['pins'].items():
                if self.package_version(name) != version and changes.get(name) != version:
                    raise ValueError('apt-simulation-incomplete')
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

    def package_version(self, name):
        try:
            return self.call(['/usr/bin/dpkg-query', '-W', '-f=${Version}', name]).strip()
        except RuntimeError:
            return None

    def validate(self, step):
        kind = step['kind']
        if kind == 'sources': return validate_sources(self.root)
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
                if not self.call(['/usr/bin/node', '--version']).startswith(('v22.', 'v24.')): return False
            return True
        return False
