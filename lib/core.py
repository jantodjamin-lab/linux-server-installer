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
    try:
        from swap import active_swap
        result['swap_bytes'] = sum(active_swap(lambda argv: query(argv)).values())
        mounts = json.loads(query(['/usr/bin/findmnt', '--json', '--target', '/var/lib', '--output', 'FSTYPE,OPTIONS']))
        result['filesystem'] = mounts['filesystems'][0]['fstype']
        result['swap_disk_bytes'] = shutil.disk_usage('/var/lib').free
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        result['errors'].append('swap-inventory')
    try:
        from local import validate_sources
        from node import verify_key, universe_present
        validate_sources(Path('/')); verify_key(Path('/'), lambda argv: query(argv))
        result['sources_valid'] = True
        result['node_universe'] = universe_present(Path('/'))
    except (OSError, ValueError, subprocess.SubprocessError):
        result['sources_valid'] = False
        result['errors'].append('source-inventory')
    result['service_manager'] = Path('/run/systemd/system').is_dir() and Path('/usr/bin/systemctl').is_file()
    result['services'] = {}
    for service in ('nginx', 'postgresql'):
        try:
            result['services'][service] = query(['/usr/bin/systemctl', 'show', service,
                                                 '--property=LoadState,ActiveState']).strip()
        except (OSError, subprocess.SubprocessError):
            result['errors'].append('service-inventory')
    result['package_candidates'] = {}
    for package in sorted({p for v in PROFILES.values() for p in v['packages']}):
        try:
            raw = query(['/usr/bin/apt-cache', '-o', 'Dir::Cache::pkgcache=', '-o', 'Dir::Cache::srcpkgcache=', 'policy', package])
            candidate = next((line.split(':',1)[1].strip() for line in raw.splitlines() if line.strip().startswith('Candidate:')), '(none)')
            result['package_candidates'][package] = None if candidate == '(none)' else candidate
        except (OSError, subprocess.SubprocessError):
            result['errors'].append('package-source-inventory')
    return result


def plan(profile, observed):
    policy = PROFILES[profile]
    failures = []
    warnings = []
    if observed.get('kernel') != 'Linux':
        failures.append('linux-required')
    if observed.get('os') != {'ID': 'ubuntu', 'VERSION_ID': '26.04'}:
        failures.append('unsupported-os')
    if observed.get('arch') not in ('x86_64', 'aarch64'):
        failures.append('unsupported-architecture')
    for key, minimum in (('cpu', policy['minimum']['cpu']), ('ram_mib', policy['minimum']['ram_mib']), ('disk_gib', policy['disk_gib'])):
        if type(observed.get(key)) not in (int, float) or not math.isfinite(observed[key]) or observed[key] < minimum:
            failures.append(key)
    for key, recommended in policy['recommended'].items():
        if type(observed.get(key)) in (int,float) and observed[key] < recommended:
            warnings.append(key+'-below-recommendation')
    if profile == 'APP+DB' and type(observed.get('ram_mib')) in (int,float) and observed['ram_mib'] < policy['recommended']['ram_mib']:
        warnings.append('APP+DB technically possible at test minimum; physical RAM insufficient for reliable builds and runtime; swap does not remedy RAM capacity.')
    if observed.get('sources_valid') is not True: failures.append('package-sources')
    if observed.get('service_manager') is not True: failures.append('systemd-required')
    if not all(s in observed.get('services',{}) for s in policy['services']): failures.append('service-inventory')
    missing = [p for p in policy['packages'] if not observed.get('package_candidates',{}).get(p)]
    if missing: warnings.append('packages-unavailable-in-current-cache: '+','.join(missing))
    try:
        from swap import swap_plan, TARGET
        swap = swap_plan(observed.get('swap_bytes'), observed.get('swap_disk_bytes'),
                         observed.get('filesystem'), policy['disk_gib']*2**30)
        if swap['deficit_bytes']: warnings.append('swap-deficit-requires-explicit-execution')
    except ValueError:
        failures.append('swap-preflight'); swap = {'required_bytes': 4*2**30}
    failures.extend(observed.get('errors', []))
    body = {'schema': 1, 'profile': profile, 'observations': observed,
            'packages': policy['packages'], 'failures': failures,
            'capacity': {'minimum':policy['minimum'],'recommended':policy['recommended'],'disk_reserve_gib':policy['disk_gib'],'swap':swap},
            'required_services':policy['services'],
            'status': 'FAIL' if failures else 'WARN', 'mode': 'dry-run',
            'installation_authorized': False,
            'warnings': warnings + ['Exact package/source lock and target approval required; live compatibility untested.']}
    body['plan_id'] = digest(body)
    return body
