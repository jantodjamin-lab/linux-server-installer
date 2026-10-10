"""Explicit Ubuntu universe provider: Node 22 LTS and separately pinned npm.

No third-party key import, executable download, version discovery or fallback.
APT authenticates signed Release files and their package checksum chain.
"""
import os
from pathlib import Path
import re
import stat

KEYRING = '/usr/share/keyrings/ubuntu-archive-keyring.gpg'
ARCHIVE_KEY = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'
ALLOWED_KEYS = {ARCHIVE_KEY, '790BC7277767219C42C86F933B4FE6ACC0B21F32',
                '843938DF228D22F7B3742BC0D94AA3F0EFE21092'}
SOURCE = 'etc/apt/sources.list.d/universal-node-universe.sources'


def verify_key(root, call):
    key = Path(root)/KEYRING.lstrip('/')
    for parent in [key,*key.parents]:
        if parent.is_symlink(): raise ValueError('archive-key-symlink')
    s = key.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid not in (0, os.geteuid()) or s.st_mode & 0o022:
        raise ValueError('archive-key-owner')
    # --show-keys does not import keys. Nonexistent home prevents trustdb writes.
    output = call(['/usr/bin/gpg','--no-options','--batch','--homedir','/nonexistent',
                   '--with-colons','--show-keys',str(key)])
    fingerprints = set(); primary = False
    for line in output.splitlines():
        fields = line.split(':')
        if fields[0] == 'pub':
            if len(fields) < 7 or fields[1] in ('r','e','d'): raise ValueError('archive-key-invalid')
            primary = True
        elif fields[0] == 'sub': primary = False
        elif fields[0] == 'fpr' and primary:
            if len(fields) < 10: raise ValueError('archive-key-format')
            fingerprints.add(fields[9]); primary = False
    if ARCHIVE_KEY not in fingerprints or not fingerprints <= ALLOWED_KEYS:
        raise ValueError('archive-key-fingerprint')
    return True


def universe_present(root):
    paths = sorted((Path(root)/'etc/apt/sources.list.d').glob('*.sources'))
    covered = set()
    for path in paths:
        for paragraph in re.split(r'\n\s*\n',path.read_text().strip()):
            fields = dict(line.split(':',1) for line in paragraph.splitlines() if ':' in line and not line.startswith('#'))
            if 'universe' in fields.get('Components','').split(): covered.update(fields.get('Suites','').split())
    return {'resolute','resolute-updates','resolute-security'} <= covered


def universe_source(arch):
    if arch == 'x86_64':
        uri = 'https://archive.ubuntu.com/ubuntu'; security = 'https://security.ubuntu.com/ubuntu'; apt_arch = 'amd64'
    elif arch == 'aarch64':
        uri = security = 'https://ports.ubuntu.com/ubuntu-ports'; apt_arch = 'arm64'
    else: raise ValueError('node-architecture')
    def stanza(address,suites):
        return ('Types: deb\nURIs: '+address+'\nSuites: '+suites+'\nComponents: universe\nArchitectures: '+apt_arch+
                '\nSigned-By: '+KEYRING+' '+ARCHIVE_KEY+'\n')
    return stanza(uri,'resolute resolute-updates')+'\n'+stanza(security,'resolute-security')


def package_available(call, pins):
    # Exact-version authenticated metadata is required for the entire closure.
    # apt-cache policy candidates are insufficient: pins may not be candidates.
    for name,version in sorted(pins.items()):
        output = call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','show',name+'='+version])
        paragraphs = re.split(r'\n\s*\n', output.strip())
        found = False
        for paragraph in paragraphs:
            fields = {}
            for line in paragraph.splitlines():
                if line.startswith((' ','\t')): continue
                if ':' in line:
                    k,v = line.split(':',1)
                    if k in fields: raise ValueError('package-metadata-duplicate')
                    fields[k]=v.strip()
            if fields.get('Package') == name and fields.get('Version') == version:
                if not re.fullmatch(r'[a-f0-9]{64}',fields.get('SHA256','')) or not fields.get('Filename','').startswith('pool/'):
                    raise ValueError('package-authenticated-metadata')
                found = True
        if not found: raise ValueError('pinned-package-unavailable')
    return True


def check_runtime(call, pins):
    def upstream(version):
        match = re.match(r'(\d+\.\d+\.\d+)',version.split(':')[-1])
        if not match: raise ValueError('node-runtime-pin')
        return match[1]
    return (call(['/usr/bin/node','--version']).strip() == 'v'+upstream(pins['nodejs']) and
            call(['/usr/bin/npm','--version']).strip() == upstream(pins['npm']))


def verify_signature(path, keyring, call):
    output = call(['/usr/bin/gpgv','--homedir','/nonexistent','--status-fd=1','--keyring',str(keyring),str(path)])
    signatures = [line.split() for line in output.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
    if not signatures or not any(row[-1] == ARCHIVE_KEY for row in signatures):
        raise ValueError('archive-signature-fingerprint')
    if any(code in output for code in ('BADSIG','ERRSIG','REVKEYSIG','EXPKEYSIG','EXPSIG')):
        raise ValueError('archive-signature-invalid')
    return True


def verify_releases(root, call):
    root = Path(root); key = root/KEYRING.lstrip('/')
    directory = root/'var/lib/apt/lists'
    suites = set()
    for path in sorted(directory.glob('*_InRelease')):
        match = re.fullmatch(r'(?:archive\.ubuntu\.com_ubuntu|security\.ubuntu\.com_ubuntu|ports\.ubuntu\.com_ubuntu-ports)_dists_(resolute(?:-updates|-security)?)_InRelease',path.name)
        if not match: raise ValueError('unreviewed-release-metadata')
        for p in [path,*path.parents]:
            if p.is_symlink(): raise ValueError('release-metadata-symlink')
        s = path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid not in (0,os.geteuid()) or s.st_mode & 0o022:
            raise ValueError('release-metadata-owner')
        verify_signature(path,key,call); suites.add(match[1])
    if suites != {'resolute','resolute-updates','resolute-security'}:
        raise ValueError('signed-release-metadata-required')
    return True
