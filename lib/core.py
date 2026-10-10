"""Pure policy and bounded, read-only local inventory."""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess

BASE = Path(__file__).resolve().parents[1]
PROFILES = json.loads((BASE / 'profiles/profiles.json').read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def query(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=15, check=True,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    return result.stdout


def inventory():
    result = {'kernel': platform.system(), 'arch': platform.machine(), 'cpu': os.cpu_count(),
              'disk_gib': shutil.disk_usage('/').free / 2**30, 'errors': []}
    try:
        result['os'] = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        result['os'] = {k: v.strip('"') for k, v in result['os'].items() if k in ('ID', 'VERSION_ID')}
        result['ram_mib'] = int(next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')).split()[1]) / 1024
    except (OSError, ValueError, StopIteration):
        result['errors'].append('system-inventory')
    try:
        raw = query(['/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Version}\t${Status}\n'])
        result['packages'] = {p: v for p, v, s in (line.split('\t', 2) for line in raw.splitlines()) if s == 'install ok installed'}
    except (OSError, ValueError, subprocess.SubprocessError):
        result['errors'].append('package-inventory')
    try:
        raw = query(['/usr/bin/ss', '-H', '-ltn'])
        result['tcp_ports'] = sorted({int(line.split()[3].rsplit(':', 1)[1]) for line in raw.splitlines()})
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        result['errors'].append('listener-inventory')
    return result


def plan(profile, observed):
    policy = PROFILES[profile]
    failures = []
    if observed.get('kernel') != 'Linux':
        failures.append('linux-required')
    if observed.get('os') != {'ID': 'ubuntu', 'VERSION_ID': '26.04'}:
        failures.append('unsupported-os')
    if observed.get('arch') not in ('x86_64', 'aarch64'):
        failures.append('unsupported-architecture')
    for key, minimum in (('cpu', 1), ('ram_mib', 843), ('disk_gib', policy['disk_gib'])):
        if type(observed.get(key)) not in (int, float) or not math.isfinite(observed[key]) or observed[key] < minimum:
            failures.append(key)
    failures.extend(observed.get('errors', []))
    body = {'schema': 1, 'profile': profile, 'observations': observed,
            'packages': policy['packages'], 'failures': failures,
            'status': 'FAIL' if failures else 'WARN', 'mode': 'dry-run',
            'installation_authorized': False,
            'warnings': ['Exact package/source lock and target approval required; live compatibility untested.']}
    body['plan_id'] = digest(body)
    return body
