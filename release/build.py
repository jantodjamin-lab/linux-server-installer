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
VERSION = '1.0.0-rc.2'


def public_files():
    names = ['install.sh', 'README.md', 'SECURITY.md', 'profiles/profiles.json',
             'docs/GUIDE.md', 'docs/SOURCES.md', 'docs/ACCEPTANCE.md', 'release/build.py']
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
    artifact.write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
    manifest = {'version': VERSION, 'status': 'NIET LIVE GEVALIDEERD', 'live_installation_validated': False,
                'artifact': artifact.name, 'sources': {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (OUT/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    checks = [artifact, OUT/'manifest.json', OUT/'build.py']
    (OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in checks))
    return artifact.read_bytes()


if __name__ == '__main__':
    build()
