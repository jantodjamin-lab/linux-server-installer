"""WP-003 preparation only: build SSH/stdin proposal, validate offline evidence.

Transport requires a separately reviewed GO-1 record; never invoked offline. Independent verification is a human
prerequisite, never inferred from keyscan or from a successful connection.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import selectors
import time
from uuid import uuid4

from infrastructure.installer import preflight
from infrastructure.installer.plan import build_plan

HOSTKEY_FILE = preflight.ROOT / 'infrastructure/ssh/test-o_known_hosts'
PUBLIC_KEY = '/home/appo-admin/.ssh/id_ed25519_ramin_v2.pub'
AGENT = '/run/user/1000/openssh_agent'
LIMIT = 1024 * 1024

STORE_ROOT = preflight.ROOT / 'logs' / 'wp003'


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def prepare(target, known_hosts, verification, *, profile, max_age_seconds):
    """Pure proposal. All target metadata must come from current operator review."""
    if profile not in preflight.PROFILES:
        raise ValueError('Invalid profile')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600:
        raise ValueError('Explicit bounded freshness policy required')
    for key in ('provider_instance', 'generation', 'hostname', 'machine_id', 'boot_id'):
        if not isinstance(target.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', target[key]):
            raise ValueError('Missing bounded target identity')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', target.get('host', '')):
        raise ValueError('Invalid host')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', target.get('user', '')) or target['user'] == 'root':
        raise ValueError('Non-root account required')
    if type(target.get('port')) is not int or not 1 <= target['port'] <= 65535:
        raise ValueError('Invalid port')
    # Exactly one explicit host pin. No wildcards, aliases, CA or TOFU.
    token = target['host'] if target['port'] == 22 else f"[{target['host']}]:{target['port']}"
    fields = known_hosts.split()
    if len(fields) != 3 or fields[:2] != [token, 'ssh-ed25519']:
        raise ValueError('Exactly one matching ED25519 host pin required')
    try:
        key = base64.b64decode(fields[2], validate=True)
        algorithm = b'ssh-ed25519'
        prefix = struct.pack('>I', len(algorithm)) + algorithm + struct.pack('>I', 32)
        if len(key) != len(prefix) + 32 or not key.startswith(prefix):
            raise ValueError('Invalid ED25519 wire key')
    except Exception as exc:
        raise ValueError('Invalid hostkey encoding') from exc
    fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip('=')
    if (verification.get('fingerprint') != fingerprint or
            verification.get('target') != target or
            verification.get('independent') is not True or
            not all(isinstance(verification.get(k), str) and verification[k].strip()
                    for k in ('source', 'reviewer', 'verified_at'))):
        raise ValueError('Independent fingerprint verification for exact target required')
    timestamp(verification['verified_at'])
    nonce = str(uuid4())
    # Self-contained code sent to python stdin: no upload, target file or import.
    source = Path(preflight.__file__).read_text()
    source = source[:source.index('\ndef evaluate(')]
    source = source.replace('ROOT = Path(__file__).resolve().parents[2]', "ROOT = Path('/')")
    stdin = (source + '\nimport socket\n' +
             "observations, errors = collect(Path('/'))\n" +
             "identity = {'hostname': socket.gethostname(), 'machine_id': Path('/etc/machine-id').read_text().strip(), "
             "'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'user': __import__('pwd').getpwuid(os.getuid()).pw_name}\n" +
             f"print(json.dumps({{'nonce': {nonce!r}, 'identity': identity, 'observations': observations, 'errors': errors, 'timestamp_utc': datetime.now(timezone.utc).isoformat()}}, allow_nan=False))\n")
    options = ['BatchMode=yes', 'StrictHostKeyChecking=yes', 'UpdateHostKeys=no',
               'GlobalKnownHostsFile=/dev/null', f'UserKnownHostsFile={HOSTKEY_FILE}',
               'HostKeyAlgorithms=ssh-ed25519', 'VerifyHostKeyDNS=no',
               'ConnectTimeout=10', 'ConnectionAttempts=1', 'ServerAliveInterval=5',
               'ServerAliveCountMax=2', 'ForwardAgent=no', 'ClearAllForwardings=yes',
               'ProxyCommand=none', 'ProxyJump=none', 'ControlMaster=no',
               'ControlPath=none', 'PermitLocalCommand=no', 'PreferredAuthentications=publickey',
               'PasswordAuthentication=no', 'KbdInteractiveAuthentication=no',
               f'IdentityFile={PUBLIC_KEY}', 'IdentitiesOnly=yes', f'IdentityAgent={AGENT}', 'RequestTTY=no']
    argv = ['ssh', '-F', '/dev/null', '-T']
    for option in options:
        argv += ['-o', option]
    argv += ['-p', str(target['port']), '-l', target['user'], '--', target['host'],
             'env LC_ALL=C PYTHONDONTWRITEBYTECODE=1 python3 -B -']
    return {'kind': 'remote-preflight-proposal', 'target': dict(target),
            'verification': json.loads(json.dumps(verification)), 'nonce': nonce, 'profile': profile,
            'max_age_seconds': max_age_seconds, 'argv': argv, 'stdin': stdin,
            'known_hosts': known_hosts, 'outer_timeout_seconds': 90,
            'execution_authorized': False, 'installation_authorized': False}


def assess(proposal, stdout, *, started_at, received_at, now, returncode, stderr=''):
    """Offline ingestion. Preserve raw evidence even on malformed/failed input."""
    evidence = {'kind': 'remote-preflight-evidence', 'proposal': proposal,
                'stdout': stdout, 'stderr': stderr, 'returncode': returncode,
                'started_at': started_at, 'received_at': received_at,
                'status': 'FAIL', 'installation_authorized': False}
    try:
        start, received, current = map(timestamp, (started_at, received_at, now))
        if not start <= received <= current or (current-start).total_seconds() > proposal['max_age_seconds']:
            raise ValueError('Stale or inconsistent APP-O evidence times')
        if returncode != 0:
            raise ValueError('Transport/remote failure; no automatic retry')
        payload = json.loads(stdout, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if set(payload) != {'nonce', 'identity', 'observations', 'errors', 'timestamp_utc'}:
            raise ValueError('Measurements-only envelope required')
        if payload['nonce'] != proposal['nonce']:
            raise ValueError('Request binding mismatch')
        expected = {k: proposal['target'][k] for k in ('hostname', 'machine_id', 'boot_id', 'user')}
        if payload['identity'] != expected or (payload['observations']['identity']['euid'] == 0 or payload['observations']['identity']['uid'] == 0):
            raise ValueError('Target identity mismatch or root context')
        remote_time = timestamp(payload['timestamp_utc'])
        if not start <= remote_time <= received:
            raise ValueError('Remote clock outside APP-O collection interval')
        report = preflight.evaluate(proposal['profile'], payload['observations'], payload['errors'])
        payload['report'] = report
        # Reuse current semantic validation: sorted JSON can reorder error dicts.
        build_plan(report)
        evidence.update(status=report['status'], payload=payload)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        evidence['error'] = str(exc)
    return evidence


def save(evidence, directory):
    """APP-O-only new owned directory; raw failures also retained."""
    directory = Path(directory).absolute()
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError('Symlink path forbidden')
    directory = directory.resolve()
    if not directory.is_relative_to(STORE_ROOT) or directory == STORE_ROOT:
        raise ValueError('Evidence must be below logs/wp003')
    serialized = json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + '\n'
    STORE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)
    fd = os.open(directory / 'evidence.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())


def bounded_runner(argv, *, input, timeout, output_limit, shell):
    """Drain both pipes within a shared deadline and per-stream byte limit."""
    if shell is not False:
        raise ValueError('Shell forbidden')
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, shell=False,
                          env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}) as process:
        try:
            with selectors.DefaultSelector() as selector:
                for stream, name in ((process.stdout, 'stdout'), (process.stderr, 'stderr'),
                                     (process.stdin, 'stdin')):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_WRITE if name == 'stdin'
                                      else selectors.EVENT_READ, name)
                pending = memoryview(input.encode())
                deadline = time.monotonic() + timeout
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Transport timeout; no retry')
                    for key, _ in selector.select(min(remaining, 0.1)):
                        if key.data == 'stdin':
                            if pending:
                                count = os.write(key.fd, pending[:4096])
                                pending = pending[count:]
                            if not pending:
                                selector.unregister(key.fileobj)
                                key.fileobj.close()
                        else:
                            chunk = os.read(key.fd, min(4096, output_limit + 1 - len(output[key.data])))
                            if not chunk:
                                selector.unregister(key.fileobj)
                            else:
                                output[key.data].extend(chunk)
                                if len(output[key.data]) > output_limit:
                                    raise ValueError('Transport output limit; no retry')
                process.wait(timeout=max(0.001, deadline-time.monotonic()))
            error = None
        except (TimeoutError, subprocess.TimeoutExpired, ValueError, OSError) as exc:
            process.kill()
            process.wait()
            error = str(exc)
    return dict(returncode=process.returncode if error is None else -1,
                stdout=bytes(output['stdout'][:output_limit]).decode(errors='replace'),
                stderr=bytes(output['stderr'][:output_limit]).decode(errors='replace'), error=error)


def test_o_proposal(target, verification, *, profile, max_age_seconds):
    """Only the documented absolute TEST-O pin; never a caller-selected file."""
    if (target.get('host') != '149.210.166.239' or target.get('port') != 22 or
            target.get('user') != 'o2-admin' or
            target.get('provider_instance') != 'widjamin-vps6' or
            target.get('hostname') != 'cloud.example.com' or
            target.get('machine_id') != '21f6df03264056c90382000028c88d41' or
            verification.get('fingerprint') != 'SHA256:IwugsqszZLcsMjve5+ZLja/HaSe7ORMbc9ciWb354tg'):
        raise ValueError('Documented TEST-O identity required')
    if any(path.is_symlink() for path in (HOSTKEY_FILE, *HOSTKEY_FILE.parents)):
        raise ValueError('Hostkey symlink forbidden')
    return prepare(target, HOSTKEY_FILE.read_text(), verification,
                   profile=profile, max_age_seconds=max_age_seconds)


def run_preflight(proposal, *, go_record, directory, runner=bounded_runner):
    """Future GO-1-only adapter. This function is tested with fake runner only."""
    expected = test_o_proposal(proposal['target'], proposal['verification'],
                               profile=proposal['profile'],
                               max_age_seconds=proposal['max_age_seconds'])
    # Nonce-dependent payload must be regenerated, never accept arbitrary stdin/argv.
    expected['stdin'] = expected['stdin'].replace(repr(expected['nonce']), repr(proposal['nonce']))
    expected['nonce'] = proposal['nonce']
    if proposal != expected:
        raise ValueError('Modified proposal; stop')
    if (not isinstance(go_record, dict) or go_record.get('scope') != 'GO-1-read-only' or
            go_record.get('target') != proposal['target'] or
            go_record.get('payload_sha256') != hashlib.sha256(proposal['stdin'].encode()).hexdigest() or
            not go_record.get('actor') or not go_record.get('reference') or
            not timestamp(go_record['issued_at']) <= datetime.now(timezone.utc) <= timestamp(go_record['expires_at'])):
        raise ValueError('Separate current human GO-1 record required')
    started = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    result = runner(tuple(expected['argv']), input=expected['stdin'], timeout=90,
                    output_limit=LIMIT, shell=False)
    received = datetime.now(timezone.utc).isoformat()
    if (time.monotonic()-before > 90 or result.get('error') or
            any(len(result[name].encode()) > LIMIT for name in ('stdout', 'stderr'))):
        result['returncode'] = -1
    evidence = assess(proposal, result['stdout'][:LIMIT], stderr=result['stderr'][:LIMIT],
                      started_at=started, received_at=received, now=received,
                      returncode=result['returncode'])
    evidence['go_record'] = go_record
    evidence['transport_error'] = result.get('error')
    save(evidence, directory)
    return evidence
