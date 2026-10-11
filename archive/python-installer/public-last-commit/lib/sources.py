"""Read-only, format-aware Ubuntu source policy; no key import or source edits."""
from pathlib import Path
import os
import re
import stat
from urllib.parse import urlsplit

KEYRING = '/usr/share/keyrings/ubuntu-archive-keyring.gpg'
ARCHIVE_KEY = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'
BASE_SUITES = {'resolute','resolute-updates','resolute-security'}
SUITES = BASE_SUITES | {'resolute-backports'}
COMPONENTS = {'main','universe','restricted','multiverse'}
FIELDS = {'types','uris','suites','components','signed-by','architectures','enabled',
          'trusted','allow-insecure','allow-weak','allow-downgrade-to-insecure',
          'check-valid-until','check-date'}


def approve_uri(uri, allow_mirrors=(), enforce_policy=True):
    normalized = mirror_uri(uri)
    parts = urlsplit(normalized)
    host = parts.hostname
    canonical = host in ('archive.ubuntu.com','security.ubuntu.com','ports.ubuntu.com') or host.endswith('.archive.ubuntu.com')
    if canonical:
        expected = '/ubuntu-ports' if host == 'ports.ubuntu.com' else '/ubuntu'
        if parts.path.rstrip('/') != expected: raise ValueError('apt-source-path')
    elif enforce_policy and normalized not in {mirror_uri(v) for v in allow_mirrors}:
        raise MirrorError(normalized)
    return normalized.rstrip('/') if canonical else normalized


class MirrorError(ValueError):
    def __init__(self, uri):
        self.uri = uri
        self.host = urlsplit(uri).hostname
        self.remedy = 'rerun with --allow-mirror '+uri
        super().__init__('unapproved-apt-source')


def mirror_uri(uri):
    try:
        parts = urlsplit(uri)
        if parts.port is not None: raise ValueError('port')
    except ValueError: raise ValueError('mirror-uri-invalid') from None
    if len(uri)>2048: raise ValueError('mirror-uri-invalid')
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('mirror-uri-invalid')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', parts.netloc) or not parts.path.startswith('/') or '..' in parts.path.split('/') or not re.fullmatch(r'/[A-Za-z0-9_./-]*', parts.path):
        raise ValueError('mirror-uri-invalid')
    if len(parts.hostname)>253 or any(len(label)>63 for label in parts.hostname.split('.')):raise ValueError('mirror-uri-invalid')
    return parts.scheme+'://'+parts.netloc+parts.path


def safe_file(path):
    for p in [path,*path.parents]:
        if p.is_symlink(): raise ValueError('apt-source-symlink')
    s = path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid not in (0,os.geteuid()) or s.st_mode & 0o022:
        raise ValueError('apt-source-owner')


def deb822(text):
    for paragraph in re.split(r'\n[ \t]*\n',text.strip()):
        fields = {}; previous = None
        for line in paragraph.splitlines():
            if line.startswith('#') or not line.strip(): continue
            if line.startswith((' ','\t')):
                if previous is None: raise ValueError('apt-source-format')
                fields[previous] += ' '+line.strip()
                continue
            if ':' not in line: raise ValueError('apt-source-format')
            key,value = line.split(':',1); key=key.lower()
            if not re.fullmatch('[a-z][a-z0-9-]*',key) or key in fields: raise ValueError('apt-source-duplicate')
            fields[key]=value.strip(); previous=key
        if fields: yield fields


def legacy(text):
    mapping = {'arch':'architectures','signed-by':'signed-by'}
    for line in text.splitlines():
        line=line.split('#',1)[0].strip()
        if not line: continue
        match=re.fullmatch(r'(deb|deb-src)\s+(?:\[([^]]+)\]\s+)?(\S+)\s+(\S+)\s+(.+)',line)
        if not match: raise ValueError('apt-source-format')
        kind,options,uri,suite,components=match.groups()
        fields={'types':kind,'uris':uri,'suites':suite,'components':components}
        for option in (options or '').split():
            if '=' not in option: raise ValueError('apt-source-format')
            key,value=option.split('=',1); key=mapping.get(key,key)
            if key in fields: raise ValueError('apt-source-duplicate')
            fields[key]=value.replace(',',' ')
        yield fields


def read_sources(root, allow_mirrors=(), enforce_policy=True):
    root=Path(root)
    paths=[root/'etc/apt/sources.list']+sorted((root/'etc/apt/sources.list.d').glob('*'))
    entries=[]; disabled=0
    for path in paths:
        if path.name != 'sources.list' and path.suffix not in ('.list','.sources'): continue
        if not path.exists() and not path.is_symlink(): continue
        safe_file(path)
        parsed=deb822(path.read_text()) if path.suffix=='.sources' else legacy(path.read_text())
        for fields in parsed:
            if fields.get('enabled','yes').lower()=='no': disabled+=1; continue
            if fields.get('enabled','yes').lower()!='yes': raise ValueError('apt-source-enabled')
            if not set(fields)<=FIELDS: raise ValueError('apt-source-unreviewed-option')
            for key in ('trusted','allow-insecure','allow-weak','allow-downgrade-to-insecure'):
                if key in fields and fields[key].lower()!='no': raise ValueError('insecure-apt-source')
            for key in ('check-valid-until','check-date'):
                if fields.get(key,'yes').lower()!='yes': raise ValueError('insecure-apt-source')
            if fields.get('signed-by','').split() not in ([KEYRING],[KEYRING,ARCHIVE_KEY]):
                raise ValueError('apt-source-keyring')
            uris=fields.get('uris','').split()
            if not uris: raise ValueError('apt-source-uri-required')
            uris=[approve_uri(uri, allow_mirrors, enforce_policy) for uri in uris]
            suites=set(fields.get('suites','').split())
            if not suites or not suites<=SUITES: raise ValueError('apt-suite')
            components=set(fields.get('components','').split())
            if not components or not components<=COMPONENTS: raise ValueError('apt-components')
            types=set(fields.get('types','').split())
            if not types or not types<={'deb','deb-src'}: raise ValueError('apt-source-type')
            architectures=set(fields.get('architectures','').split())
            if not architectures<={'amd64','arm64','i386','armhf','ppc64el','riscv64','s390x'}:
                raise ValueError('apt-source-architecture')
            entries.append({'source_file':path.name,'uris':uris,'suites':sorted(suites),'components':sorted(components),
                            'types':sorted(types),'architectures':sorted(architectures),'signed_by':' '.join(fields['signed-by'].split())})
    binary=[e for e in entries if 'deb' in e['types']]
    if not binary: raise ValueError('no-approved-apt-sources')
    key=root/KEYRING.lstrip('/')
    if not key.exists() and not key.is_symlink(): raise ValueError('ubuntu-keyring-required')
    safe_file(key)
    return {'entries':entries,'disabled_stanzas':disabled}


def validate_sources(root, allow_mirrors=()):
    read_sources(root, allow_mirrors)
    return True


def universe_coverage(root, arch=None, allow_mirrors=()):
    expected={'x86_64':'amd64','aarch64':'arm64'}.get(arch)
    covered=set()
    for entry in read_sources(root, allow_mirrors)['entries']:
        if 'deb' in entry['types'] and 'universe' in entry['components'] and (not expected or not entry['architectures'] or expected in entry['architectures']):
            covered.update(entry['suites'])
    return covered


def source_summary(root, arch=None, allow_mirrors=()):
    data=read_sources(root, allow_mirrors)
    suites={s for e in data['entries'] if 'deb' in e['types'] for s in e['suites']}
    return {'active_stanzas':len(data['entries']),'disabled_stanzas':data['disabled_stanzas'],
            'suites':sorted(suites),'missing_base_suites':sorted(BASE_SUITES-suites),
            'universe_missing_suites':sorted(BASE_SUITES-universe_coverage(root,arch,allow_mirrors))}


def release_paths(root, allow_mirrors=(), enforce_policy=True):
    from urllib.parse import urlsplit
    expected = {}
    for entry in read_sources(root, allow_mirrors, enforce_policy)['entries']:
        for uri in entry['uris']:
            parts = urlsplit(uri); prefix = parts.hostname+parts.path.rstrip('/').replace('/', '_')
            for suite in entry['suites']:
                expected[prefix+'_dists_'+suite+'_InRelease'] = suite
    return expected
