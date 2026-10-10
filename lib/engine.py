"""Verified offline package plan and injectable execution state machine.

No live adapter is released. Test runners model effects on disposable state.
"""
import hashlib
import json
import re
from pathlib import Path
from core import PROFILES, digest

NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*\Z')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+:~_-]*\Z')


def verify_bundle(manifest, directory, profile, development=False):
    if set(manifest) != {'schema', 'os', 'arch', 'packages', 'updates', 'development'}:
        raise ValueError('manifest-schema')
    if manifest['schema'] != 1 or manifest['os'] != 'ubuntu-26.04' or manifest['arch'] not in ('amd64', 'arm64'):
        raise ValueError('unsupported-bundle')
    if type(manifest['development']) is not bool or manifest['development'] != development:
        raise ValueError('development-binding')
    if not isinstance(manifest['packages'], list) or not isinstance(manifest['updates'], list):
        raise ValueError('package-list')
    required = set(PROFILES[profile]['packages'])
    if profile != 'DB':
        required.add('angular-cli')
    if development:
        if profile == 'DB':
            raise ValueError('codex-requires-app')
        required.add('codex-cli')
    seen = set()
    root = Path(directory).resolve(strict=True)
    for package in manifest['packages']:
        if set(package) != {'name', 'version', 'file', 'sha256', 'source', 'kind'}:
            raise ValueError('package-schema')
        name, version = package['name'], package['version']
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in seen:
            raise ValueError('package-name')
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise ValueError('package-version')
        seen.add(name)
        # Approved Ubuntu archive mirror only; no arbitrary executable URLs.
        if package['source'] != 'https://archive.ubuntu.com/ubuntu/':
            raise ValueError('unreviewed-source')
        filename = package['file']
        if not isinstance(filename, str) or '/' in filename or '\\' in filename or filename in ('.', '..'):
            raise ValueError('artifact-path')
        path = root / filename
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('artifact-type')
        if package['kind'] not in ('deb', 'npm-offline'):
            raise ValueError('artifact-kind')
        if not re.fullmatch('[a-f0-9]{64}', package['sha256']) or hashlib.sha256(path.read_bytes()).hexdigest() != package['sha256']:
            raise ValueError('artifact-checksum')
        if name == 'dotnet-sdk-10.0' and not version.startswith('10.'):
            raise ValueError('dotnet-version')
        if name == 'postgresql-18' and not version.startswith('18.'):
            raise ValueError('postgresql-version')
        if name == 'nodejs' and not version.startswith('22.'):
            raise ValueError('node-version')
        if name == 'angular-cli' and not version.startswith('20.'):
            raise ValueError('angular-version')
    if not required <= seen or not set(manifest['updates']) <= seen:
        raise ValueError('incomplete-closure')
    if not development and 'codex-cli' in seen:
        raise ValueError('codex-development-only')
    return digest({'manifest': manifest, 'profile': profile})


def actions(manifest):
    """Declarative commands only. Caller must provide reviewed dependency closure."""
    result = []
    for package in manifest['packages']:
        result.append({'id': package['name'], 'version': package['version'],
                       'artifact': package['file'], 'kind': package['kind'],
                       'validator': 'exact-version',
                       'security': ['no-download', 'no-existing-db-adoption', 'no-service-start',
                                    'no-firewall-or-ssh-change', 'no-npm-scripts']})
    return result


class Engine:
    """Runner API: version(name), install(action), validate(action), reboot_required().

    Persist pending before effects. An interrupted pending action always requires
    explicit review before retry. Checkpoints never override current validation.
    """
    def __init__(self, runner, checkpoint, binding):
        self.runner, self.path, self.binding = runner, Path(checkpoint), binding
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError('checkpoint-symlink')
        self.state = {'binding': binding, 'pending': None, 'completed': [], 'events': []}
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            if set(self.state) != {'binding', 'pending', 'completed', 'events'} or self.state['binding'] != binding:
                raise ValueError('checkpoint-binding')

    def save(self):
        import os
        import tempfile
        fd, name = tempfile.mkstemp(dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(self.state, stream, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def run(self, steps, review=False):
        if self.state['pending'] and review is not True:
            raise ValueError('uncertain-effects-review-required')
        if review is True:
            self.state['events'].append({'event': 'recovery-reviewed'})
            self.state['pending'] = None
            self.save()
        for step in steps:
            if self.runner.version(step['id']) == step['version']:
                if not self.runner.validate(step):
                    raise ValueError('existing-package-validation')
                continue
            if self.runner.version(step['id']) is not None:
                raise ValueError('existing-version-conflict')
            if self.runner.reboot_required():
                raise ValueError('reboot-required-manual-resume')
            self.state['pending'] = step['id']
            self.state['events'].append({'event': 'started', 'step': step['id']})
            self.save()
            try:
                self.runner.install(step)
                if not self.runner.validate(step) or self.runner.version(step['id']) != step['version']:
                    raise ValueError('postcondition')
            except Exception:
                self.state['events'].append({'event': 'failed', 'step': step['id']})
                self.save()
                raise RuntimeError('package-action-failed') from None
            self.state['completed'].append(step['id'])
            self.state['pending'] = None
            self.state['events'].append({'event': 'validated', 'step': step['id']})
            self.save()
        if self.runner.reboot_required():
            return {'status': 'WARN', 'reason': 'reboot-required', 'binding': self.binding}
        return {'status': 'PASS', 'binding': self.binding}


class LiveRunner:
    def __init__(self):
        raise RuntimeError('Live installation disabled: package closure, source authentication and target acceptance unverified')
