"""Reproducible generic release; explicit allowlist, never parent project export."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'release'
VERSION = '1.0.0-rc.4'


def public_files():
    names = ['install.sh', 'README.md', 'SECURITY.md', 'profiles/profiles.json',
             'docs/GUIDE.md', 'docs/SOURCES.md', 'docs/ACCEPTANCE.md', 'docs/RC3.md', 'docs/RC4.md', 'tests/fixtures/ubuntu-archive-2018.b64', 'release/build.py']
    names += [str(p.relative_to(BASE)) for folder, pattern in [('lib','*.py'), ('tests','test_*.py')]
              for p in sorted((BASE/folder).glob(pattern))]
    result = sorted(BASE/name for name in names)
    for path in result:
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('public-artifact-type')
        content = path.read_text()
        # Exclude environment-specific names and private host addresses.
        forbidden = ('ra'+'min', 'APP'+'-O', 'TEST'+'-O', '/home/'+'appo-admin', '149.210.'+'166.239')
        if any(word in content for word in forbidden):
            raise ValueError('internal-data-in-public-file')
        for pattern in (r'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----', r'AKIA[A-Z0-9]{16}',
                        r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{30,}', r'sk-[A-Za-z0-9_-]{30,}'):
            if re.search(pattern, content): raise ValueError('secret-in-public-file')
    return result


def build():
    files = public_files()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for path in files:
            payload = path.read_bytes()
            info = tarfile.TarInfo('universal-linux-installer-' + VERSION + '/' + str(path.relative_to(BASE)))
            info.size = len(payload); info.mode = 0o644; info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    OUT.mkdir(exist_ok=True)
    artifact = OUT / ('universal-linux-installer-' + VERSION + '.tar.gz')
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, compresslevel=9, mtime=0) as stream:
        stream.write(buffer.getvalue())
    artifact.write_bytes(compressed.getvalue())
    manifest = {'version': VERSION, 'status': 'NIET LIVE GEVALIDEERD', 'live_installation_validated': False,
                'artifact': artifact.name, 'sources': {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (OUT/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    archive_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    url = 'https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v'+VERSION+'/'+artifact.name
    audit = ("(set -eu; audit_dir=$(mktemp -d); cd \"$audit_dir\"; curl -q --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 '"+url+"' --output '"+artifact.name+"'; printf '%s  %s\\n' '"+archive_sha+"' '"+artifact.name+"' | sha256sum -c -; tar -xzf '"+artifact.name+"'; sh 'universal-linux-installer-"+VERSION+"/install.sh' --profile APP+DB --audit)\n")
    (OUT/'AUDIT.txt').write_text(audit)
    checks = [artifact, OUT/'manifest.json', OUT/'build.py', OUT/'AUDIT.txt']
    (OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in checks))
    return artifact.read_bytes()


if __name__ == '__main__':
    build()
