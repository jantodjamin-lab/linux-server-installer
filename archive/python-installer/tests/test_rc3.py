"""Offline RC3 acceptance. No real APT, formatter or swapon command is invoked.

Pure capacity tests use exact GiB. Filesystem recovery tests use proportional
MiB-sized files to exercise real writes/fsync/permissions without allocating GiB.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture
from test_workflow import sources, lock_for
from test_local import Transport, npm_bundle
from core import plan, PROFILES
from local import LocalRunner, validate_sources
from node import verify_key, ARCHIVE_KEY, package_available, verify_signature, verify_releases
from swap import SwapManager, swap_plan, GIB, TARGET
from workflow import build_workflow
from journal import run_workflow

MIB = 2**20


class SwapTransport:
    def __init__(self, existing=0):
        self.active = {'/existing':existing} if existing else {}
        self.calls = []; self.formatted = set(); self.fail = None
    def __call__(self, argv, cwd=None):
        self.calls.append(argv)
        name = Path(argv[0]).name
        if self.fail == name and not any(a.startswith('--show') for a in argv): raise RuntimeError('simulated-interruption')
        if name == 'swapon' and any(a.startswith('--show') for a in argv):
            return ''.join(k+' '+str(v)+'\n' for k,v in self.active.items())
        if name == 'findmnt': return json.dumps({'filesystems':[{'fstype':'ext4','options':'rw,relatime'}]})
        if name == 'blkid':
            if argv[-1] not in self.formatted: raise RuntimeError('unformatted')
            return 'swap\n'
        if name == 'mkswap': self.formatted.add(argv[-1])
        if name == 'swapon': self.active[argv[-1]] = Path(argv[-1]).stat().st_size-os.sysconf('SC_PAGE_SIZE')
        return ''


def manager(tmp, existing=0):
    root = Path(tmp); (root/'etc').mkdir()
    fstab = root/'etc/fstab'; fstab.write_text('# Preserve operator entries\n/existing none swap sw 0 0\n'); fstab.chmod(0o644)
    transport = SwapTransport(existing)
    return SwapManager(root,transport,0,target=4*MIB), transport


class RC3SwapTests(unittest.TestCase):
    def test_exact_gib_deficits(self):
        for existing, deficit in ((0,4*GIB),(2*GIB,2*GIB),(4*GIB,0),(6*GIB,0)):
            p = swap_plan(existing,50*GIB,'ext4',30*GIB)
            self.assertEqual(p['deficit_bytes'],deficit)
            if deficit: self.assertEqual(p['file_bytes'],deficit+os.sysconf('SC_PAGE_SIZE'))
            else: self.assertEqual(p['file_bytes'],0)
    def test_zero_two_four_and_repeat(self):
        for existing in (0,2*MIB,4*MIB,6*MIB):
            with tempfile.TemporaryDirectory() as tmp:
                m,tr = manager(tmp,existing); before=m.fstab.read_bytes()
                result=m.apply(); self.assertGreaterEqual(result['active_bytes'],4*MIB)
                self.assertEqual(result['existing_bytes'],existing)
                calls=sum(Path(x[0]).name in ('mkswap','swapon') and not any(a.startswith('--show') for a in x) for x in tr.calls)
                m.apply(); self.assertEqual(calls,sum(Path(x[0]).name in ('mkswap','swapon') and not any(a.startswith('--show') for a in x) for x in tr.calls))
                self.assertTrue(m.validate())
                if existing >= 4*MIB:
                    self.assertFalse(m.path.exists()); self.assertEqual(before,m.fstab.read_bytes())
                else:
                    self.assertEqual(m.path.stat().st_mode & 0o777,0o600)
                    self.assertTrue(m.fstab.read_bytes().startswith(before))
                    self.assertEqual(m.fstab.read_text().count(m.name()),1)
    def test_disk_and_filesystem(self):
        with self.assertRaises(ValueError): swap_plan(0,4*GIB,'ext4',0)
        with self.assertRaises(ValueError): swap_plan(2*GIB,10*GIB,'btrfs',0)
        self.assertEqual(swap_plan(4*GIB,0,'btrfs',0)['file_bytes'],0)
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); before=m.fstab.read_bytes()
            class Full: f_bavail=1; f_frsize=4096
            with patch('swap.os.statvfs',return_value=Full()):
                with self.assertRaises(ValueError): m.apply()
            self.assertFalse(m.path.exists()); self.assertEqual(before,m.fstab.read_bytes())
    def test_interrupt_format_and_activation(self):
        for fail in ('mkswap','swapon'):
            with tempfile.TemporaryDirectory() as tmp:
                m,tr=manager(tmp); tr.fail=fail
                with self.assertRaises(RuntimeError): m.apply()
                inode=m.path.stat().st_ino
                self.assertTrue(m.state_path.is_file()); self.assertFalse(m.validate())
                tr.fail=None; m.apply()
                self.assertTrue(m.validate()); self.assertEqual(inode,m.path.stat().st_ino)
                self.assertEqual(m.fstab.read_text().count(m.name()),1)
    def test_interrupt_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); original=os.write; count=0
            def interrupted(fd,data):
                nonlocal count
                count+=1
                if count==2: raise OSError('interrupted')
                return original(fd,data)
            with patch('swap.os.write',side_effect=interrupted):
                with self.assertRaises(OSError): m.apply()
            inode=m.path.stat().st_ino; self.assertEqual(json.loads(m.state_path.read_text())['state']['stage'],'creating')
            m.apply(); self.assertTrue(m.validate()); self.assertEqual(inode,m.path.stat().st_ino)
    def test_permissions_and_unknown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); m.path.parent.mkdir(parents=True); m.path.write_bytes(b'original')
            with self.assertRaises(ValueError): m.apply()
            self.assertEqual(m.path.read_bytes(),b'original')
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); m.apply(); m.path.chmod(0o644)
            with self.assertRaises(ValueError): m.apply()
            self.assertEqual(m.path.stat().st_mode & 0o777,0o644)
    def test_fstab_duplicates_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); m.apply(); m.fstab.write_text(m.fstab.read_text()+' '.join([m.name(),'none','swap','sw','0','0'])+'\n')
            self.assertFalse(m.validate())
            with self.assertRaises(ValueError): m.apply()
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp); m.path.parent.mkdir(parents=True); m.path.symlink_to(m.fstab)
            with self.assertRaises(ValueError): m.apply()
    def test_failed_activation_preserves_existing_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,tr=manager(tmp,2*MIB); tr.fail='swapon'
            with self.assertRaises(RuntimeError): m.apply()
            self.assertEqual(tr.active,{'/existing':2*MIB})
            self.assertIn(m.name(),m.fstab.read_text())
            self.assertFalse(any(Path(x[0]).name=='swapoff' for x in tr.calls))


class RC3SourceTests(unittest.TestCase):
    def test_fingerprint_and_bad_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sources(root)
            output='pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::'+ARCHIVE_KEY+':\n'
            self.assertTrue(verify_key(root,lambda argv:output))
            for bad in ('',output.replace(ARCHIVE_KEY,'A'*40),output+'pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::'+'B'*40+':\n'):
                with self.assertRaises(ValueError): verify_key(root,lambda argv:bad)
    def test_actual_invalid_gpg_signature(self):
        import shutil
        if not shutil.which('gpgv'): self.skipTest('gpgv unavailable')
        from local import command
        with tempfile.TemporaryDirectory() as tmp:
            signature=Path(tmp)/'InRelease'; signature.write_text('invalid signature')
            key=Path(tmp)/'keyring.gpg'; key.write_bytes(b'invalid keyring')
            with self.assertRaises(RuntimeError): verify_signature(signature,key,command)
    def test_release_signature_and_fingerprint_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root)
            good='[GNUPG:] VALIDSIG '+ARCHIVE_KEY+' 2026-01-01 0 0 4 0 1 10 01 '+ARCHIVE_KEY+'\n'
            self.assertTrue(verify_releases(root,lambda argv:good))
            for output in ('[GNUPG:] BADSIG untrusted',good.replace(ARCHIVE_KEY,'B'*40),good+'[GNUPG:] EXPKEYSIG expired'):
                with self.assertRaises(ValueError): verify_releases(root,lambda argv:output)
    def test_missing_packages_and_hashes(self):
        for output in ('', 'Package: npm\nVersion: 9.2.0\nFilename: pool/fixture.deb\n'):
            with self.assertRaises(ValueError): package_available(lambda argv:output,{'npm':'9.2.0'})
    def test_source_creation_and_no_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target';root.mkdir();sources(root)
            p=root/'etc/apt/sources.list.d/ubuntu.sources';p.write_text(p.read_text().replace('main universe','main'))
            lock=lock_for('APP'); bundle=Path(tmp)/'bundle';npm_bundle(bundle,lock)
            w=build_workflow('APP',fixture(),lock);tr=Transport(root,w)
            runner=LocalRunner(w,'INSTALL:'+w['plan_id'],True,True,root,tr,bundle)
            runner.apply(w['steps'][0]);self.assertTrue(runner.validate(w['steps'][0]))
            generated=root/'etc/apt/sources.list.d/universal-node-universe.sources'
            self.assertIn('Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg',generated.read_text()); self.assertTrue(validate_sources(root))
            original=generated.read_bytes();runner.apply(w['steps'][0]);self.assertEqual(original,generated.read_bytes())
    def test_invalid_signature_stops_before_packages_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target';root.mkdir();sources(root)
            w=build_workflow('DB',fixture(),lock_for('DB')); tr=Transport(root,w)
            def invalid(argv,cwd=None):
                if Path(argv[0]).name=='apt-get' and 'update' in argv: raise RuntimeError('invalid-signature')
                return tr(argv,cwd)
            runner=LocalRunner(w,'INSTALL:'+w['plan_id'],True,True,root,invalid)
            with self.assertRaises(RuntimeError):run_workflow(w,runner,Path(tmp)/'private')
            self.assertFalse(any('install' in a for a,_ in tr.calls))
            self.assertFalse(runner.swap.path.exists())
    def test_duplicate_and_insecure_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);p=root/'etc/apt/sources.list.d/ubuntu.sources';s=p.read_text()
            for addition in ('Trusted: yes\n','Allow-Insecure: yes\n','Signed-By: /tmp/key\n','Check-Valid-Until: no\n'):
                p.write_text(s+addition)
                with self.assertRaises(ValueError):validate_sources(root)


class RC3CapacityTests(unittest.TestCase):
    def test_all_profiles_and_ram_independent_swap(self):
        for profile in PROFILES:
            observed=fixture(); observed.update(cpu=1,ram_mib=843,swap_bytes=0)
            result=plan(profile,observed);self.assertFalse(result['failures']);self.assertIn('ram_mib-below-recommendation',result['warnings'])
            self.assertEqual(result['capacity']['swap']['deficit_bytes'],4*GIB)
            observed.update(ram_mib=842,swap_bytes=100*GIB)
            self.assertIn('ram_mib',plan(profile,observed)['failures'])
        observed=fixture();observed.update(ram_mib=843)
        self.assertTrue(any('insufficient for reliable' in w for w in plan('APP+DB',observed)['warnings']))
    def test_missing_services_sources_packages(self):
        for key,value,code in (('services',{},'service-inventory'),('sources_valid',False,'package-sources'),('service_manager',False,'systemd-required')):
            observed=fixture();observed[key]=value;self.assertIn(code,plan('APP',observed)['failures'])
        observed=fixture();observed['package_candidates']={}
        self.assertTrue(any('packages-unavailable' in w for w in plan('APP',observed)['warnings']))
    def test_cli_audit_and_dry_run_all_profiles(self):
        import contextlib
        import io
        from cli import main
        for profile in PROFILES:
            for mode in ('--audit','--dry-run'):
                out=io.StringIO()
                with patch('sys.argv',['installer','--profile',profile,mode,'--json']), patch('cli.inventory',return_value=fixture()), patch('cli.LocalRunner',side_effect=AssertionError('execution during audit')), patch('subprocess.run',side_effect=AssertionError('system command')), contextlib.redirect_stdout(out):
                    self.assertEqual(main(),0)
                report=json.loads(out.getvalue());self.assertFalse(report['installation_authorized'])
                self.assertEqual(report['mode'],'dry-run')
    def test_audit_dry_run_no_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sources(root)
            before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            for profile in PROFILES:
                observed=fixture();observed['swap_bytes']=0; copied=copy.deepcopy(observed)
                with patch('subprocess.run',side_effect=AssertionError('audit-planning-command')):
                    plan(profile,observed);build_workflow(profile,observed,lock_for(profile))
                self.assertEqual(observed,copied)
            self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
