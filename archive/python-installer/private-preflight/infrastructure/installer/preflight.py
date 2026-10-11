#!/usr/bin/env python3
"""Local read-only inventory; the only write is a new JSON evidence file."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    'APP': {'cpu': 2, 'ram_mib': 2048, 'disk_gib': 10, 'ports': [80, 443]},
    'DB': {'cpu': 2, 'ram_mib': 4096, 'disk_gib': 20, 'ports': [5432]},
    'APP-DB': {'cpu': 4, 'ram_mib': 6144, 'disk_gib': 30, 'ports': [80, 443, 5432]},
}
OTEST_MINIMUM = {'cpu': 1, 'ram_mib': 843}
# Fixed local queries only: no caller-supplied commands, shell, sudo or SSH.
QUERIES = {
    'services': ('systemctl', 'list-units', '--type=service', '--all',
                 '--no-pager', '--no-legend', '--plain'),
    'ssh_sockets': ('systemctl', 'list-units', '--type=socket', '--all',
                    '--no-pager', '--no-legend', '--plain'),
    'ports': ('ss', '-H', '-lntu'),
}


class QueryError(RuntimeError):
    def __init__(self, name, result):
        super().__init__(f'{name} query returned {result.returncode}')
        self.evidence = {'returncode': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr}


def query(name):
    result = subprocess.run(QUERIES[name], capture_output=True, text=True,
                            timeout=5, check=False, stdin=subprocess.DEVNULL, env={**os.environ, 'LC_ALL': 'C',
                                                        'SYSTEMD_PAGER': '', 'SYSTEMD_COLORS': '0'})
    if result.returncode:
        raise QueryError(name, result)
    return result.stdout


def parse_os(text):
    return dict(line.split('=', 1) for line in text.splitlines()
                if '=' in line and not line.startswith('#'))


def parse_memory(text):
    values = {}
    for line in text.splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'SwapTotal'):
            fields = value.split()
            if len(fields) != 2 or fields[1] != 'kB':
                raise ValueError('unexpected memory unit')
            values[key] = int(fields[0]) / 1024
    return {key: values[source] for key, source in
            (('ram_mib', 'MemTotal'), ('swap_mib', 'SwapTotal')) if source in values}


def parse_services(text, suffix='.service'):
    services = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == '●':
            fields = fields[1:]
        if not fields:
            continue
        if len(fields) < 4 or not fields[0].endswith(suffix):
            raise ValueError('unexpected service inventory format')
        services.append({'unit': fields[0], 'load': fields[1],
                         'active': fields[2], 'sub': fields[3]})
    return services


def parse_ports(text):
    ports = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[0] not in ('tcp', 'udp'):
            raise ValueError('unexpected listener inventory format')
        address, port = fields[4].rsplit(':', 1)
        ports.append({'protocol': fields[0], 'address': address, 'port': int(port)})
    return ports


def collect(disk_path):
    observations, errors = {}, {}
    def inventory(name, parser):
        raw = query(name)
        observations[name + '_raw'] = raw
        return parser(raw)

    probes = {
        'os': lambda: parse_os(Path('/etc/os-release').read_text()),
        'kernel': lambda: {'system': platform.system(), 'release': platform.release()},
        'cpu': os.cpu_count,
        'memory': lambda: parse_memory(Path('/proc/meminfo').read_text()),
        'disk': lambda: {'path': str(disk_path), 'free_gib': shutil.disk_usage(disk_path).free / 1024**3},
        'services': lambda: inventory('services', parse_services),
        'ssh_sockets': lambda: inventory('ssh_sockets', lambda raw: parse_services(raw, '.socket')),
        'ports': lambda: inventory('ports', parse_ports),
        'ssh_binary': lambda: shutil.which('sshd') or next(
            (str(p) for p in (Path('/usr/sbin/sshd'), Path('/sbin/sshd'))
             if p.is_file() and os.access(p, os.X_OK)), None),
        'sudo_binary': lambda: shutil.which('sudo'),
        'identity': lambda: {'uid': os.getuid(), 'euid': os.geteuid(),
                             'group_ids': os.getgroups()},
    }
    for name, probe in probes.items():
        try:
            observations[name] = probe()
        except Exception as exc:
            # Continue collecting so failure never discards other evidence.
            errors[name] = {'message': f'{type(exc).__name__}: {exc}'}
            if isinstance(exc, QueryError):
                errors[name].update(exc.evidence)
            elif isinstance(exc, subprocess.TimeoutExpired):
                errors[name].update({'timeout_seconds': exc.timeout,
                                    'stdout': (exc.stdout or b'').decode(errors='replace')
                                    if isinstance(exc.stdout, bytes) else exc.stdout,
                                    'stderr': (exc.stderr or b'').decode(errors='replace')
                                    if isinstance(exc.stderr, bytes) else exc.stderr})
    return observations, errors


def evaluate(profile, observations, errors):
    checks = []
    def add(name, status, message):
        checks.append({'name': name, 'status': status, 'message': message})
    for name, error in errors.items():
        add(name, 'WARN', f'Observation unavailable: {error}')
    for name in ('os', 'kernel', 'services', 'ssh_sockets', 'ports',
                 'ssh_binary', 'sudo_binary', 'identity'):
        if name not in observations and name not in errors:
            add(name, 'WARN', 'Observation missing; no successful inventory established')
    policy = PROFILES[profile]
    if 'os' in observations:
        distro = observations['os'].get('ID', '').strip('\"\'')
        add('os', 'PASS' if distro in ('ubuntu', 'debian') else 'WARN',
            f'Observed distribution: {distro or "unknown"}; Ubuntu/Debian are design targets')
    if 'kernel' in observations:
        kernel = observations['kernel']
        add('kernel', 'PASS' if kernel['system'] == 'Linux' and kernel['release'] else 'FAIL',
            f'{kernel["system"]} {kernel["release"]}')
    for name, value, minimum in (
        ('cpu', observations.get('cpu'), policy['cpu']),
        ('ram', observations.get('memory', {}).get('ram_mib'), policy['ram_mib']),
        ('disk', observations.get('disk', {}).get('free_gib'), policy['disk_gib']),
    ):
        if value is not None:
            if name == 'disk':
                add(name, 'PASS' if value >= minimum else 'FAIL', f'Observed {value:g}; minimum {minimum}')
            else:
                floor = OTEST_MINIMUM['cpu' if name == 'cpu' else 'ram_mib']
                status = 'FAIL' if value < floor else ('WARN' if value < minimum else 'PASS')
                add(name, status, f'Observed {value:g}; O/TEST minimum {floor}; production recommendation {minimum}')
        elif name not in errors:
            add(name, 'WARN', f'{name} unavailable')
    swap = observations.get('memory', {}).get('swap_mib')
    add('swap', 'PASS' if swap is not None and swap > 0 else 'WARN',
        f'Observed swap: {swap:g} MiB' if swap is not None else 'Swap observation unavailable')
    if 'services' in observations:
        services = observations['services']
        failed = [s['unit'] for s in services
                  if s['active'] == 'failed' or s['load'] in ('error', 'bad-setting')]
        not_found = [s['unit'] for s in services if s['load'] == 'not-found']
        add('services', 'WARN' if failed else 'PASS',
            f'Inventoried {len(services)} services; failed/invalid units: {failed}; '
            f'not-found units (informational): {not_found}')
        ssh_active = any(s['unit'] in ('ssh.service', 'sshd.service') and
                         s['load'] == 'loaded' and s['active'] == 'active' and
                         s['sub'] == 'running' for s in services)
        add('ssh_service', 'PASS' if ssh_active else 'WARN',
            'SSH service active' if ssh_active else 'No active SSH service observed; socket activation/custom units may apply')
    if 'ssh_sockets' in observations:
        active = any(s['unit'] in ('ssh.socket', 'sshd.socket') and
                     s['load'] == 'loaded' and s['active'] == 'active' and
                     s['sub'] == 'listening' for s in observations['ssh_sockets'])
        add('ssh_socket', 'PASS' if active else 'WARN',
            'Local SSH socket listening' if active else 'No standard listening SSH socket observed')
    if 'ssh_binary' in observations:
        add('ssh_binary', 'PASS' if observations['ssh_binary'] else 'WARN', 'Local sshd executable presence checked')
    add('ssh_security', 'WARN', 'SSH access, configuration and authentication are not verified; no SSH connection made')
    if 'ports' in observations:
        conflicts = sorted({p['port'] for p in observations['ports']} & set(policy['ports']))
        add('ports', 'WARN' if conflicts else 'PASS',
            f'Profile ports already in use: {conflicts}' if conflicts else 'Proposed profile ports are free')
        add('ssh_listener', 'PASS' if any(p['protocol'] == 'tcp' and p['port'] == 22
                                        for p in observations['ports']) else 'WARN',
            'Local TCP port 22 inspected; owner, reachability and custom SSH ports are not verified')
    if 'sudo_binary' in observations:
        add('sudo_binary', 'PASS' if observations['sudo_binary'] else 'WARN', 'sudo executable presence checked')
    if 'identity' in observations:
        identity = observations['identity']
        add('sudo_context', 'PASS',
            f'Local UID {identity["uid"]}, effective UID {identity["euid"]}, groups {identity["group_ids"]}; these do not establish sudo authorization')
    add('sudo_passwordless', 'WARN', 'Not verified: WP-001 prohibits executing sudo, including sudo -n')
    overall = 'FAIL' if any(c['status'] == 'FAIL' for c in checks) else (
        'WARN' if any(c['status'] == 'WARN' for c in checks) else 'PASS')
    return {'schema_version': 2, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'profile': profile, 'scope': 'local-read-only', 'policy': {'environment': 'O/TEST', 'minimum': {**OTEST_MINIMUM, 'disk_gib': policy['disk_gib']},
                                                     'production_recommendation': policy},
            'status': overall, 'checks': checks, 'observations': observations, 'errors': errors}


def save_evidence(report, output):
    # Existing evidence is never overwritten. Restrict writes to this repository.
    output = output.resolve()
    protected = {'.git', '.agents', '.codex', '.aws', 'references'}
    if not output.is_relative_to(ROOT) or protected.intersection(output.relative_to(ROOT).parts):
        raise ValueError('Evidence output must be inside the repository, outside protected directories')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--disk-path', type=Path, default=ROOT,
                        help='Local filesystem path whose free space is inspected')
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args(argv)
    observations, errors = collect(args.disk_path)
    report = evaluate(args.profile, observations, errors)
    output = args.output or ROOT / 'docs/installer/evidence' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + args.profile + '.json')
    try:
        save_evidence(report, output)
    except (OSError, ValueError) as exc:
        report['checks'].append({'name': 'evidence', 'status': 'FAIL', 'message': str(exc)})
        report['status'] = 'FAIL'
        # stdout remains machine readable if persistence itself fails.
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f'FAIL: could not save evidence: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f'{report["status"]}: evidence saved to {output}', file=sys.stderr)
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
