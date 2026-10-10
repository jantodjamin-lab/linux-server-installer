"""Exercise the actual local adapter against a disposable tree and command double."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from test_core import fixture
from test_workflow import lock_for, sources
from workflow import build_workflow
from local import LocalRunner, check_npm_lock, PGHBA, SERVICE_BLOCK
from journal import run_workflow


def npm_bundle(root, lock):
    root.mkdir()
    for name, pin in lock['npm'].items():
        destination = root/('angular' if name == '@angular/cli' else 'codex'); destination.mkdir()
        dependencies = {name:pin['version']}
        package = {'name':'installer-toolchain','version':'1.0.0','private':True,'dependencies':dependencies}
        npm_lock = {'name':'installer-toolchain','version':'1.0.0','lockfileVersion':3,
                    'packages':{'':{'dependencies':dependencies}, 'node_modules/'+name:{'version':pin['version'],
                    'resolved':'https://registry.npmjs.org/'+name+'/-/fixture.tgz',
                    'integrity':'sha512-'+base64.b64encode(bytes(64)).decode()}}}
        (destination/'package.json').write_text(json.dumps(package))
        raw=json.dumps(npm_lock).encode(); (destination/'package-lock.json').write_bytes(raw)
        pin['lock_sha256']=hashlib.sha256(raw).hexdigest()


class Transport:
    def __init__(self, root, workflow): self.root=root; self.workflow=workflow; self.versions={}; self.calls=[]; self.fail=False
    def __call__(self, argv, cwd=None):
        self.calls.append((argv,cwd))
        if self.fail: raise RuntimeError('PRIVATE_TOKEN')
        executable=Path(argv[0]).name
        if executable == 'gpg':
            return 'pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::F6ECB3762474EDA9D21B7022871920D1991BC93C:\n'
        if executable == 'gpgv':
            return '[GNUPG:] VALIDSIG F6ECB3762474EDA9D21B7022871920D1991BC93C 2026-01-01 0 0 4 0 1 10 01 F6ECB3762474EDA9D21B7022871920D1991BC93C\n'
        if executable == 'swapon':
            return '/existing-swap '+str(4*2**30)+'\n'
        if executable == 'apt-cache':
            return '\n'.join('Package: '+name+'\nVersion: '+version+'\nFilename: pool/main/fixture.deb\nSHA256: '+'a'*64+'\n' for name,version in (pin.split('=',1) for pin in argv[argv.index('show')+1:]))
        if executable == 'apt-get' and 'install' in argv and '-s' in argv:
            pins = [a.split('=',1) for a in argv if '=' in a and not a.startswith(('APT::','Acquire::','Dpkg::','DPkg::'))]
            return ''.join('Inst '+name+' ('+version+' Ubuntu [amd64])\n' for name,version in pins if self.versions.get(name) != version)
        if executable == 'apt-get' and 'install' in argv and '-s' not in argv:
            for pin in argv:
                if '=' in pin and not pin.startswith(('APT::','Acquire::','Dpkg::','DPkg::')):
                    name,version=pin.split('=',1); self.versions[name]=version
            if 'nginx' in self.versions:
                path=self.root/'etc/nginx/sites-available/default'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('package default')
                link=self.root/'etc/nginx/sites-enabled/default'; link.parent.mkdir(parents=True,exist_ok=True)
                if not link.exists(): link.symlink_to(path)
            if 'postgresql-18' in self.versions:
                path=self.root/'etc/postgresql/18/main/pg_hba.conf'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(PGHBA)
        if executable=='dpkg-query':
            if argv[-1] not in self.versions: raise RuntimeError('missing')
            return self.versions[argv[-1]]
        if executable=='curl': return '<!doctype html><title>Installer ready</title>Installer ready\n'
        if executable=='runuser': return 'localhost|scram-sha-256|180000\n'
        if executable=='dotnet': return '10.0.100 [/usr/share/dotnet/sdk]\n'
        if executable=='node': return 'v22.12.0\n'
        if executable=='ng': return 'Angular CLI: '+self.workflow['lock']['npm']['@angular/cli']['version']+'\n'
        if executable=='codex': return 'codex-cli '+self.workflow['lock']['npm']['@openai/codex']['version']+'\n'
        if executable=='npm':
            if '--version' in argv: return '9.2.0\n'
            data=json.loads((Path(cwd)/'package.json').read_text())
            for name,version in data['dependencies'].items():
                path=Path(cwd)/'node_modules'/name/'package.json'; path.parent.mkdir(parents=True); path.write_text(json.dumps({'version':version}))
        return ''


class LocalIntegrationTests(unittest.TestCase):
    def test_complete_profiles_real_adapter_and_repeat(self):
        for profile in ('APP','DB','APP+DB'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'target'; root.mkdir(); sources(root)
                lock=lock_for(profile); bundle=Path(tmp)/'bundle'; npm_bundle(bundle,lock)
                workflow=build_workflow(profile,fixture(),lock); transport=Transport(root,workflow)
                runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport,bundle)
                state=Path(tmp)/'private'
                self.assertEqual(run_workflow(workflow,runner,state)['status'],'PASS')
                self.assertFalse((root/'usr/sbin/policy-rc.d').exists())
                install_count=sum('install' in argv and '-s' not in argv for argv,_ in transport.calls)
                reopened=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport,bundle)
                self.assertEqual(run_workflow(workflow,reopened,state)['status'],'PASS')
                self.assertEqual(install_count,sum('install' in argv and '-s' not in argv for argv,_ in transport.calls))
                for argv,_ in transport.calls:
                    self.assertNotIn('ssh',argv); self.assertNotIn('sudo',argv)
                    if Path(argv[0]).name=='npm' and 'ci' in argv: self.assertIn('--ignore-scripts',argv)
    def test_optional_codex_and_explicit_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target'; root.mkdir(); sources(root)
            lock=lock_for('APP'); lock['npm']['@openai/codex']={'version':'0.128.0','lock_sha256':'b'*64}; lock['updates']['openssl']='3.0-1'
            bundle=Path(tmp)/'bundle'; npm_bundle(bundle,lock)
            workflow=build_workflow('APP',fixture(),lock,True,True); transport=Transport(root,workflow)
            runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport,bundle)
            self.assertEqual(run_workflow(workflow,runner,Path(tmp)/'private')['status'],'PASS')
            self.assertEqual(transport.versions['openssl'],'3.0-1')
            self.assertTrue((root/'opt/universal-linux-installer/codex/node_modules/@openai/codex/package.json').exists())
    def test_existing_data_no_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'var/lib/postgresql').mkdir(parents=True)
            workflow=build_workflow('DB',fixture(),lock_for('DB')); calls=[]
            with self.assertRaises(ValueError): LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,lambda *a,**k:calls.append(a))
            self.assertFalse(calls)
    def test_failure_keeps_service_guard_and_private_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target'; root.mkdir(); sources(root)
            workflow=build_workflow('DB',fixture(),lock_for('DB')); transport=Transport(root,workflow)
            original = transport.__call__
            def fail_refresh(argv,cwd=None):
                if Path(argv[0]).name == 'apt-get': raise RuntimeError('PRIVATE_TOKEN')
                return original(argv,cwd)
            transport = fail_refresh
            runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport)
            with self.assertRaises(RuntimeError): run_workflow(workflow,runner,Path(tmp)/'private')
            self.assertEqual((root/'usr/sbin/policy-rc.d').read_text(),SERVICE_BLOCK)
            self.assertNotIn('PRIVATE_TOKEN',(Path(tmp)/'private/journal.json').read_text())
    def test_npm_invalid_registry_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=lock_for('APP'); bundle=Path(tmp)/'bundle'; npm_bundle(bundle,lock)
            path=bundle/'angular/package-lock.json'; data=json.loads(path.read_text())
            data['packages']['node_modules/@angular/cli']['resolved']='https://evil.invalid/fixture'
            raw=json.dumps(data).encode(); path.write_bytes(raw); lock['npm']['@angular/cli']['lock_sha256']=hashlib.sha256(raw).hexdigest()
            with self.assertRaises(ValueError): check_npm_lock(bundle/'angular','@angular/cli',lock['npm']['@angular/cli'])
    def test_pg_hba_trust_and_remote_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target'; root.mkdir(); sources(root)
            workflow=build_workflow('DB',fixture(),lock_for('DB')); transport=Transport(root,workflow)
            runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport)
            run_workflow(workflow,runner,Path(tmp)/'private')
            hba=root/'etc/postgresql/18/main/pg_hba.conf'
            for line in ('host all all 0.0.0.0/0 scram-sha-256\n','host all all 127.0.0.1/32 trust\n'):
                hba.write_text(line); self.assertFalse(runner.validate({'kind':'db-config'}))

    def test_unpinned_dependency_and_removal_refused(self):
        for simulation in ('Inst unwanted (9.0 Ubuntu [amd64])\n', 'Remv git [1.0]\n'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'target'; root.mkdir(); sources(root)
                workflow=build_workflow('DB',fixture(),lock_for('DB')); transport=Transport(root,workflow)
                def override(argv,cwd=None):
                    if '-s' in argv: return simulation
                    return transport(argv,cwd)
                runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,override)
                with self.assertRaises(RuntimeError): run_workflow(workflow,runner,Path(tmp)/'private')
                self.assertFalse(any('install' in argv and '-s' not in argv for argv,_ in transport.calls))

    def test_host_lock_spans_different_checkpoint_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target'; root.mkdir(); sources(root)
            workflow=build_workflow('DB',fixture(),lock_for('DB')); transport=Transport(root,workflow)
            runner=LocalRunner(workflow,'INSTALL:'+workflow['plan_id'],True,True,root,transport)
            with runner.execution_lock():
                with self.assertRaises(BlockingIOError): run_workflow(workflow,runner,Path(tmp)/'different-state')
            self.assertFalse(transport.calls)
