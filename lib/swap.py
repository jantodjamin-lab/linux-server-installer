"""Deficit-only swap with exclusive ownership, durable checkpoints and no rollback.

Only ext4 and XFS are accepted. No existing swap is removed, resized or disabled.
Caller holds the host execution lock and gates uncertain recovery explicitly.
"""
import json
import math
import os
from pathlib import Path
import stat
import tempfile

GIB = 2**30
RELATIVE = 'var/lib/universal-linux-installer/swap/swapfile'
TARGET = 4 * GIB


def active_swap(call):
    """Supported util-linux raw output; successful empty output means zero swap."""
    raw = call(['/usr/sbin/swapon', '--show', '--bytes', '--noheadings', '--raw', '--output', 'NAME,SIZE'])
    if not isinstance(raw, str): raise ValueError('swap-inventory-format')
    result = {}
    for line in raw.splitlines():
        if not line.strip(): continue
        # util-linux raw NAME is not guaranteed to hex-escape spaces (e.g.
        # a kernel swap path marked '(deleted)' inside a container). SIZE is
        # the final numeric column; split from the right and preserve the name.
        fields = line.rsplit(None, 1)
        if len(fields) != 2: raise ValueError('swap-inventory-format')
        name, size = fields
        # libsmartcols raw output escapes unsafe path bytes as hex escapes.
        import re
        name = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m[1],16)), name)
        if not name.startswith('/') or any(c in name for c in ('\x00','\n','\r')) or name in result or not size.isascii() or not size.isdecimal() or int(size) <= 0:
            raise ValueError('swap-inventory-format')
        result[name] = int(size)
    return result


def swap_plan(existing, free, filesystem, reserve, target=TARGET):
    if any(type(v) is not int or v < 0 for v in (existing, free, reserve, target)):
        raise ValueError('swap-capacity')
    # One page is reserved for the swap header; active capacity still reaches target.
    page = os.sysconf('SC_PAGE_SIZE')
    deficit = max(0, target-existing)
    size = math.ceil(deficit/page)*page + page if deficit else 0
    if size and filesystem not in ('ext4', 'xfs'): raise ValueError('swap-filesystem')
    if size and free < size+reserve: raise ValueError('swap-disk-reserve')
    return {'existing_bytes': existing, 'required_bytes': target, 'deficit_bytes': deficit, 'file_bytes': size}


def regular(path, mode=None):
    for parent in [path, *path.parents]:
        if parent.is_symlink(): raise ValueError('swap-symlink')
    s = path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid() or s.st_mode & 0o022:
        raise ValueError('swap-file-owner')
    if mode is not None and stat.S_IMODE(s.st_mode) != mode: raise ValueError('swap-file-mode')
    return s


def atomic(path, content, mode):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if os.path.exists(name): os.unlink(name)


class SwapManager:
    def __init__(self, root, call, reserve, target=TARGET):
        self.root = Path(root).absolute(); self.call = call; self.reserve = reserve; self.target = target
        if type(target) is not int or target <= 0: raise ValueError('swap-target')
        self.path = self.root/RELATIVE
        self.state_path = self.path.parent/'checkpoint.json'
        self.fstab = self.root/'etc/fstab'

    def name(self): return str(self.path)

    def report(self):
        active = active_swap(self.call)
        existing = self.read()['existing_bytes'] if self.state_path.exists() else sum(active.values())
        return {'existing_bytes': existing, 'required_bytes': self.target, 'deficit_bytes':max(0,self.target-existing),
                'active_bytes': sum(active.values()), 'managed_active_bytes': active.get(self.name(), 0)}

    def filesystem(self):
        parent = self.path.parent
        while not parent.exists(): parent = parent.parent
        for p in [parent, *parent.parents]:
            if p.is_symlink(): raise ValueError('swap-parent-symlink')
        data = json.loads(self.call(['/usr/bin/findmnt', '--json', '--target', str(parent), '--output', 'FSTYPE,OPTIONS']))
        rows = data['filesystems']
        if len(rows) != 1 or 'rw' not in rows[0]['options'].split(','): raise ValueError('swap-mount')
        return parent, rows[0]['fstype']

    def save(self, state):
        from core import digest
        atomic(self.state_path, json.dumps({'state':state,'sha256':digest(state)}, sort_keys=True)+'\n', 0o600)

    def read(self):
        regular(self.state_path, 0o600)
        from core import digest
        envelope = json.loads(self.state_path.read_text())
        if set(envelope) != {'state','sha256'} or digest(envelope['state']) != envelope['sha256']: raise ValueError('swap-checkpoint-integrity')
        state = envelope['state']
        if set(state) != {'schema','inode','device','size','stage','existing_bytes'} or state['schema'] != 1 or state['stage'] not in ('allocated','formatted','persistent','active','creating'):
            raise ValueError('swap-checkpoint')
        if type(state['existing_bytes']) is not int or not 0 <= state['existing_bytes'] < self.target or type(state['size']) is not int or state['size'] != swap_plan(state['existing_bytes'],self.target*2,'ext4',0,self.target)['file_bytes']:
            raise ValueError('swap-checkpoint-capacity')
        s = regular(self.path, 0o600)
        if (s.st_ino, s.st_dev) != (state['inode'], state['device']) or type(state['size']) is not int or state['size'] <= 0 or s.st_size > state['size']:
            raise ValueError('swap-ownership')
        return state

    def persist(self):
        s = regular(self.fstab)
        before = self.fstab.read_text()
        matches = []
        for line in before.splitlines():
            fields = line.split('#',1)[0].split()
            if fields and fields[0] == self.name(): matches.append(fields)
        expected = [self.name(), 'none', 'swap', 'sw', '0', '0']
        if matches:
            if matches != [expected]: raise ValueError('swap-fstab-conflict')
            return
        if self.fstab.read_text() != before or self.fstab.stat().st_ino != s.st_ino:
            raise ValueError('swap-fstab-drift')
        atomic(self.fstab, before + ('' if not before or before.endswith('\n') else '\n') + ' '.join(expected)+'\n', stat.S_IMODE(s.st_mode))

    def apply(self):
        active = active_swap(self.call)
        existing = sum(active.values())
        if self.state_path.exists() or self.state_path.is_symlink():
            state = self.read()
            if state['stage'] == 'active':
                if not self.validate(): raise ValueError('swap-active-drift')
                return self.report()
        else:
            if self.path.exists() or self.path.is_symlink(): raise ValueError('existing-swap-file-refused')
            if existing >= self.target: return self.report()
            # Refuse stale fstab references before allocating anything.
            regular(self.fstab)
            if any(line.split('#',1)[0].split()[:1] == [self.name()] for line in self.fstab.read_text().splitlines()):
                raise ValueError('swap-fstab-unowned')
            parent, fs = self.filesystem()
            capacity = swap_plan(existing, os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize, fs, self.reserve, self.target)
            from journal import private_directory
            private_directory(self.path.parent)
            fd = os.open(self.path, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600)
            try:
                s = os.fstat(fd)
                state = {'schema':1,'inode':s.st_ino,'device':s.st_dev,'size':capacity['file_bytes'],'stage':'creating','existing_bytes':existing}
                self.save(state)
            finally: os.close(fd)
        parent, fs = self.filesystem()
        if fs not in ('ext4','xfs'): raise ValueError('swap-filesystem')
        s = regular(self.path, 0o600)
        if state['stage'] == 'creating':
            available = os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize
            if available < state['size']-s.st_size+self.reserve: raise ValueError('swap-disk-reserve')
            fd = os.open(self.path, os.O_WRONLY|os.O_NOFOLLOW)
            try:
                if (os.fstat(fd).st_ino, os.fstat(fd).st_dev) != (state['inode'],state['device']): raise ValueError('swap-file-race')
                os.lseek(fd, s.st_size, os.SEEK_SET)
                remaining = state['size']-s.st_size
                zeros = bytes(1024*1024)
                while remaining:
                    count = os.write(fd, zeros[:min(remaining,len(zeros))]); remaining -= count
                os.fsync(fd)
            finally: os.close(fd)
            state['stage'] = 'allocated'; self.save(state)
        s = regular(self.path, 0o600)
        if s.st_size != state['size'] or s.st_blocks*512 < s.st_size: raise ValueError('swap-holes-or-size')
        if state['stage'] == 'allocated':
            if self.name() in active: raise ValueError('unexpected-active-swap')
            # An interrupted formatter is detected; never reformat an active file.
            try: formatted = self.call(['/usr/sbin/blkid','-p','-s','TYPE','-o','value',self.name()]).strip() == 'swap'
            except RuntimeError: formatted = False
            if not formatted: self.call(['/usr/sbin/mkswap',self.name()])
            if self.call(['/usr/sbin/blkid','-p','-s','TYPE','-o','value',self.name()]).strip() != 'swap': raise ValueError('swap-format')
            state['stage'] = 'formatted'; self.save(state)
        self.persist()
        state['stage'] = 'persistent'; self.save(state)
        active = active_swap(self.call)
        if self.name() not in active: self.call(['/usr/sbin/swapon',self.name()])
        if not self.validate(): raise ValueError('swap-activation')
        state['stage'] = 'active'; self.save(state)
        report = self.report(); report['existing_bytes'] = state['existing_bytes']
        return report

    def validate(self):
        active = active_swap(self.call)
        if sum(active.values()) < self.target: return False
        if not self.state_path.exists(): return not self.path.exists()
        state = self.read(); s = regular(self.path,0o600)
        if s.st_size != state['size'] or s.st_blocks*512 < s.st_size or active.get(self.name(),0) < state['size']-os.sysconf('SC_PAGE_SIZE'): return False
        regular(self.fstab)
        rows = [line.split('#',1)[0].split() for line in self.fstab.read_text().splitlines()]
        matches = [r for r in rows if r[:1] == [self.name()]]
        return matches == [[self.name(),'none','swap','sw','0','0']]
