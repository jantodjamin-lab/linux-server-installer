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
    # Read ONLY the explicit keyring. Disable default keyring/trustdb/daemon
    # initialization and lock writes; trust is established by fingerprints below,
    # not by the listing command's trust-model option.
    try:
        output = call(['/usr/bin/gpg','--no-options','--batch','--no-autostart',
                   '--homedir','/nonexistent','--no-default-keyring','--keyring',str(key),
                   '--trust-model','always','--no-auto-check-trustdb','--lock-never',
                   '--with-colons','--list-keys'])
    except FileNotFoundError: raise ValueError('archive-key-gpg-required') from None
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


def universe_present(root, arch=None, allow_mirrors=()):
    from sources import BASE_SUITES, universe_coverage
    return BASE_SUITES <= universe_coverage(root,arch,allow_mirrors)


def universe_source(arch, suites=None, root=None, allow_mirrors=()):
    from sources import BASE_SUITES
    suites=BASE_SUITES if suites is None else set(suites)
    if not suites<=BASE_SUITES: raise ValueError('apt-suite')
    if arch == 'x86_64':
        uri='https://archive.ubuntu.com/ubuntu'; security='https://security.ubuntu.com/ubuntu'; apt_arch='amd64'
    elif arch == 'aarch64':
        uri=security='https://ports.ubuntu.com/ubuntu-ports'; apt_arch='arm64'
    else: raise ValueError('node-architecture')
    stanzas=[]
    if root is not None:
        from sources import read_sources
        entries=read_sources(root,allow_mirrors)['entries']
        for suite in sorted(suites):
            candidates=[e for e in entries if 'deb' in e['types'] and suite in e['suites'] and (not e['architectures'] or apt_arch in e['architectures'])]
            if not candidates: raise ValueError('universe-base-source-required')
            entry=candidates[0]
            # APT requires identical Signed-By for a shared URI/suite, even when
            # components differ. Preserve its binding; gpgv independently pins
            # the archive signer for every configured Release file.
            stanzas.append('Types: deb\nURIs: '+entry['uris'][0]+'\nSuites: '+suite+'\nComponents: universe\nArchitectures: '+apt_arch+'\nSigned-By: '+entry['signed_by']+'\n')
        return '\n'.join(stanzas)
    for address,group in ((uri,{'resolute','resolute-updates'}),(security,{'resolute-security'})):
        selected=sorted(suites&group)
        if selected:
            stanzas.append('Types: deb\nURIs: '+address+'\nSuites: '+' '.join(selected)+'\nComponents: universe\nArchitectures: '+apt_arch+'\nSigned-By: '+KEYRING+' '+ARCHIVE_KEY+'\n')
    return '\n'.join(stanzas)


def upstream_version(version):
    if not isinstance(version,str): return None
    match=re.match(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?=$|[+~_-])',version.split(':')[-1])
    return tuple(map(int,match.groups())) if match else None


def compatible_node_npm(pins):
    node=upstream_version(pins.get('nodejs')); npm=upstream_version(pins.get('npm'))
    return bool(node and npm and node[0]==22 and node>=(22,12,0) and npm[0]==9)


def package_metadata(output,name,version):
    for paragraph in re.split(r'\n\s*\n',output.strip()):
        fields={}
        for line in paragraph.splitlines():
            if line.startswith((' ','\t')): continue
            if ':' in line:
                key,value=line.split(':',1)
                if key in fields: raise ValueError('package-metadata-duplicate')
                fields[key]=value.strip()
        if fields.get('Package')!=name or fields.get('Version')!=version: continue
        filename=fields.get('Filename','')
        if not re.fullmatch(r'[a-f0-9]{64}',fields.get('SHA256','')) or not filename.startswith('pool/') or '..' in filename.split('/'):
            raise ValueError('package-authenticated-metadata')
        dependencies=fields.get('Depends','')
        if len(dependencies)>8192 or not re.fullmatch(r'[A-Za-z0-9 .,+:~<>=|()_\-/]*',dependencies):
            raise ValueError('package-dependency-format')
        return {'version':version,'architecture':fields.get('Architecture','unknown'),
                'depends':[item.strip() for item in dependencies.split(',') if item.strip()],
                'sha256':fields['SHA256'],'availability':'cached-metadata; execution must verify signed closure'}
    raise ValueError('pinned-package-unavailable')


def package_available(call,pins):
    for name,version in sorted(pins.items()):
        output=call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','show',name+'='+version])
        package_metadata(output,name,version)
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


def verify_releases(root, call, allow_mirrors=(), enforce_policy=True):
    from sources import release_paths, BASE_SUITES
    root=Path(root); key=root/KEYRING.lstrip('/')
    expected=release_paths(root, allow_mirrors, enforce_policy)
    suites=set(); missing=False
    for name,suite in sorted(expected.items()):
        path=root/'var/lib/apt/lists'/name
        for p in [path,*path.parents]:
            if p.is_symlink(): raise ValueError('release-metadata-symlink')
        if not path.exists(): missing=True; continue
        s=path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid not in (0,os.geteuid()) or s.st_mode & 0o022:
            raise ValueError('release-metadata-owner')
        verify_signature(path,key,call); suites.add(suite)
    if missing or not BASE_SUITES<=suites: raise ValueError('signed-release-metadata-required')
    return True
