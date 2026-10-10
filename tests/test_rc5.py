"""RC5 offline safety regressions; no live resolver or privileged target effects."""
import argparse
import contextlib
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from core import BASE, digest, plan
from errors import CommandError, WorkflowError, redact
from journal import Journal, run_workflow
from local import command, check_npm_lock, APT_SECURITY
from resolve import resolve, simulation_changes, npm_pins
from sources import read_sources, MirrorError
from workflow import build_workflow, validate_plan_age, validate_lock
from test_core import fixture
from test_workflow import sources, lock_for, Runner
from test_local import Transport
from test_rc4 import audit_tree, Probe, observed, snapshot
from apply import confirm, private_write, run_apply
from cli import main, render_summary


class RC5RecoveryTests(unittest.TestCase):
    def test_retry_classes_and_effectful_gate(self):
        for step_id in ('apt-refresh','package-preflight','packages'):
            with tempfile.TemporaryDirectory() as tmp:
                w=build_workflow('DB',fixture(),lock_for('DB'));runner=Runner();runner.fail=step_id
                directory=Path(tmp)/'state'
                with self.assertRaises(WorkflowError):run_workflow(w,runner,directory)
                runner.fail=None
                if step_id=='packages':
                    with self.assertRaisesRegex(ValueError,'uncertain-effects'):run_workflow(w,runner,directory)
                    self.assertEqual(run_workflow(w,runner,directory,True)['status'],'PASS')
                else:
                    self.assertEqual(run_workflow(w,runner,directory)['status'],'PASS')
                    self.assertIn('AUTO_CLEARED',(directory/'journal.json').read_text())

    def test_interruption_safe_steps_clear_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=build_workflow('DB',fixture(),lock_for('DB'));directory=Path(tmp)/'state'
            with Journal(directory,w['plan_id']) as j:
                j.state['pending']='package-preflight';j.event('STARTED','package-preflight')
            self.assertEqual(run_workflow(w,Runner(),directory)['status'],'PASS')

    def test_private_redacted_diagnostics_and_bounded_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=build_workflow('DB',fixture(),lock_for('DB'));runner=Runner()
            original=runner.apply
            def fail(step):
                if step['id']=='packages':raise CommandError(['/usr/bin/apt-get','install','https://operator:password@mirror.invalid'],100,'https://operator:password@mirror.invalid\nAuthorization: Bearer private_token\ntoken=PRIVATE_SECRET\n'+'x'*9000)
                original(step)
            runner.apply=fail;directory=Path(tmp)/'state'
            with self.assertRaises(WorkflowError) as caught:run_workflow(w,runner,directory)
            path=Path(caught.exception.diagnostic_path)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertLessEqual(len(path.read_bytes()),4096)
            for content in (path.read_text(),(directory/'journal.json').read_text(),json.dumps(caught.exception.metadata)):
                self.assertNotIn('password@',content);self.assertNotIn('private_token',content);self.assertNotIn('PRIVATE_SECRET',content)
            self.assertNotIn('stderr',(directory/'journal.json').read_text())
            self.assertIn('FAIL packages: command-failed (exit 100)',render_summary({'status':'FAIL','diagnostics':[caught.exception.metadata]}))

    def test_redaction_before_truncation(self):
        raw='a'*8000+' https://user:secret@mirror.invalid/path Authorization: Bearer abc\ntoken=xyz\nghp_'+'a'*36
        value=redact(raw)
        self.assertIn('[REDACTED]',value)
        for private in ('user:secret','Bearer abc','token=xyz','ghp_'):self.assertNotIn(private,value)

    def test_cli_tail_stderr_only(self):
        error=WorkflowError({'step':'packages','code':'command-failed','command':['apt-get','install'],'exit_code':100})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'diagnostic.log';path.write_text(redact('https://user:password@mirror.invalid\n'));path.chmod(0o600)
            error.diagnostic_path=str(path)
            out=io.StringIO();err=io.StringIO()
            with patch('sys.argv',['installer','--profile','DB','--apply','--json','--show-diagnostics']),patch('cli.inventory',return_value=fixture()),patch('cli.os.geteuid',side_effect=[0,os.geteuid()]),patch('apply.run_apply',side_effect=error),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                self.assertEqual(main(),1)
            self.assertEqual(json.loads(out.getvalue())['diagnostics'][0]['exit_code'],100)
            self.assertNotIn('mirror.invalid',out.getvalue());self.assertIn('[REDACTED]',err.getvalue());self.assertNotIn('password',err.getvalue())


class RC5SourceTests(unittest.TestCase):
    def mirror_fixture(self, root):
        audit_tree(root)
        p=root/'etc/apt/sources.list.d/ubuntu.sources'
        p.write_text(p.read_text().replace('http://archive.ubuntu.com/ubuntu/','http://provider.example/ubuntu/archive/'))
        for old in (root/'var/lib/apt/lists').glob('*InRelease'):
            old.rename(old.with_name(old.name.replace('archive.ubuntu.com_ubuntu','provider.example_ubuntu_archive')))
        templates=root/'etc/cloud/templates';templates.mkdir(parents=True)
        (templates/'sources.list.ubuntu.deb822.tmpl').write_text('# Synthetic cloud-init fixture, not a captured provider configuration\n')
        return 'http://provider.example/ubuntu/archive/'

    def test_exact_mirror_opt_in_and_no_cascade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);uri=self.mirror_fixture(root)
            with self.assertRaises(MirrorError) as denied:read_sources(root)
            self.assertEqual(denied.exception.args,('unapproved-apt-source',))
            probe=Probe();data=observed(root,probe)
            self.assertFalse(data['sources_valid']);self.assertTrue(data['key_valid'])
            self.assertEqual(data['source_metadata'],'verified-cached')
            self.assertTrue(data['package_candidates']['nodejs'])
            self.assertTrue(any(Path(argv[0]).name=='gpgv' for argv in probe.calls))
            self.assertTrue(any(d.get('host')=='provider.example' for d in data['diagnostics']))
            from core import inventory
            accepted=inventory(root,Probe(),allow_mirrors=[uri])
            self.assertTrue(accepted['sources_valid'])
            for other in ('http://provider.example/ubuntu','https://provider.example/ubuntu/archive','http://other.example/ubuntu/archive'):
                with self.assertRaises(MirrorError):read_sources(root,[other])

    def test_mirror_credentials_and_unsafe_policy_refused(self):
        from sources import mirror_uri
        for uri in ('https://u:p@example.org/ubuntu','https://*.example.org/ubuntu','https://example.org/ubuntu?token=abc','ftp://example.org/ubuntu','https://example.org/a/../ubuntu','https://example.org:443/ubuntu'):
            with self.assertRaises(ValueError):mirror_uri(uri)

    def test_stale_index_age_warn_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root)
            now=datetime.now(timezone.utc)
            for index, path in enumerate((root/'var/lib/apt/lists').glob('*InRelease')):
                old=now-timedelta(days=17 if index==0 else 14)
                path.write_text('Date: '+old.strftime('%a, %d %b %Y %H:%M:%S +0000')+'\n')
                os.utime(path,(old.timestamp(),old.timestamp()))
            data=observed(root,Probe());report=plan('DB',data)
            check=next(c for c in report['checks'] if c['id']=='apt-index-age')
            self.assertEqual(check['status'],'WARN');self.assertFalse(report['failures'])
            self.assertGreaterEqual(data['apt_index_age']['age_days'],17)

    def test_no_gpg_clear_remedy_and_no_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);before=snapshot(root);probe=Probe()
            def call(argv):
                if Path(argv[0]).name=='gpg':raise FileNotFoundError('private missing path')
                return probe(argv)
            data=observed(root,call)
            self.assertIn('archive-key-gpg-required',json.dumps(data))
            self.assertIn('apt-get install gpg',json.dumps(data))
            self.assertEqual(before,snapshot(root))


class RC5ResolverTests(unittest.TestCase):
    def test_shipped_real_npm_locks(self):
        pins=npm_pins('APP',True)
        for name,pin in pins.items():self.assertTrue(check_npm_lock(BASE/'bundle'/('angular' if name=='@angular/cli' else 'codex'),name,pin))
        self.assertGreater(len(json.loads((BASE/'bundle/angular/package-lock.json').read_text())['packages']),200)

    def transport(self,root,profile,installed=None,extra='',missing=None):
        w=build_workflow(profile,fixture(),lock_for(profile));base=Transport(root,w)
        versions=lock_for(profile)['apt'];calls=[]
        installed=installed or {}
        def call(argv):
            calls.append(argv);binary=Path(argv[0]).name
            if binary=='apt-cache' and 'policy' in argv:
                return 'Candidate: '+('(none)' if argv[-1]==missing else versions[argv[-1]])+'\n'
            if binary=='dpkg-query' and argv[-1].endswith('\n'):
                return ''.join(n+'\t'+v+'\tinstall ok installed\n' for n,v in installed.items())
            if binary=='dpkg-query':
                if argv[-1] not in installed:raise RuntimeError('missing')
                return installed[argv[-1]]
            if binary=='dpkg':return ''
            if binary=='apt-get' and '-s' in argv:
                return ''.join('Inst '+n+' ('+v+' Ubuntu [amd64])\n' for n,v in versions.items() if installed.get(n)!=v)+extra
            return base(argv)
        return call,calls

    def test_real_executor_selftest_for_all_profiles(self):
        for profile in ('APP','DB','APP+DB'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sources(root);call,calls=self.transport(root,profile)
                w=resolve(profile,fixture(),call,root=root,refresh_metadata=True)
                self.assertEqual(w['schema'],5);self.assertEqual(validate_lock(w['lock'],profile,False),w['lock'])
                self.assertTrue(any('-s' in a and all('=' not in b for b in a[a.index('install')+1:]) for a in calls if 'install' in a))
                self.assertFalse(any('install' in a and '-s' not in a for a in calls))
                validate_plan_age(w)

    def test_refresh_requires_authorization(self):
        calls=[]
        with self.assertRaisesRegex(ValueError,'refresh-metadata-authorization'):resolve('DB',fixture(),lambda argv:calls.append(argv))
        self.assertFalse(calls)

    def test_removal_missing_candidate_limits_updates(self):
        for options,extra,missing,installed,code in [({},'Remv git\n',None,{},'package-removal-refused'),({},'', 'git',{},'pinned-package-unavailable'),({'max_new_packages':1},'',None,{},'new-package-limit-exceeded'),({},'',None,{'git':'0.1'},'system-update-approval-required'),({'system_updates':True,'max_updates':0},'',None,{'git':'0.1'},'update-limit-exceeded')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sources(root);call,_=self.transport(root,'DB',installed,extra,missing)
                with self.assertRaisesRegex(ValueError,code):resolve('DB',fixture(),call,root=root,refresh_metadata=True,**options)

    def test_installed_required_updates_take_common_lock_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);call,_=self.transport(root,'DB',{'git':'0.1'})
            w=resolve('DB',fixture(),call,root=root,refresh_metadata=True,system_updates=True)
            self.assertIn('git',w['lock']['updates']);self.assertNotIn('git',w['lock']['apt'])
            validate_lock(w['lock'],'DB',False)

    def test_expired_and_schema4_plans_refused(self):
        w=build_workflow('DB',fixture(),lock_for('DB'),created_at=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat())
        with self.assertRaisesRegex(ValueError,'plan-expired'):validate_plan_age(w)
        with self.assertRaisesRegex(ValueError,'regenerate'):validate_plan_age(dict(w,schema=4))

    def test_proxy_opt_in_and_timeout_metadata(self):
        completed=subprocess.CompletedProcess([],0,stdout='',stderr='')
        with patch.dict(os.environ,{'HTTPS_PROXY':'https://user:password@proxy.invalid'}),patch('local.subprocess.run',return_value=completed) as run:
            command(['/usr/bin/apt-get','update']);self.assertNotIn('HTTPS_PROXY',run.call_args.kwargs['env'])
            command(['/usr/bin/apt-get','update'],allow_proxy_env=True);self.assertIn('HTTPS_PROXY',run.call_args.kwargs['env'])
        with patch('local.subprocess.run',side_effect=subprocess.TimeoutExpired('apt',1,stderr='https://u:p@proxy.invalid')):
            with self.assertRaises(CommandError) as e:command(['/usr/bin/apt-get','update'])
            self.assertEqual(e.exception.exit_code,124);self.assertNotIn('u:p',e.exception.stderr_tail)
        self.assertIn('DPkg::Lock::Timeout=600',APT_SECURITY)


class RC5ApprovalTests(unittest.TestCase):
    def test_confirmation_refusal_has_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);before=snapshot(root)
            args=argparse.Namespace(profile='DB',resolve=False,approval=None,snapshot_confirmed=True,allow_unvalidated=True,state_dir=str(root/'var/lib/universal-linux-installer'))
            intent={'request_id':'a'*64,'mode':'apply','profile':'DB','limits':{'max_new_packages':1000,'max_updates':100},'system_updates':False,'allow_mirrors':[],'allow_proxy_env':False,'wait_cloud_init':True,'npm':{}}
            with patch('apply.os.geteuid',return_value=0),patch('apply.request',return_value=intent),patch('apply.confirm',side_effect=ValueError('installation-not-confirmed')),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'not-confirmed'):run_apply(args,dict(fixture(),target='fixture'))
            self.assertEqual(before,snapshot(root));self.assertFalse(Path(args.state_dir).exists())

    def test_typed_and_noninteractive_gate(self):
        args=argparse.Namespace(approval=None,snapshot_confirmed=True,allow_unvalidated=True)
        intent={'request_id':'a'*64}
        class TTY(io.StringIO):
            def write(self,value):return len(value)
        with patch('apply.sys.stdin.isatty',return_value=True):
            confirm(args,intent,TTY('INSTALL '+'a'*12+'\n'))
            with self.assertRaises(ValueError):confirm(args,intent,TTY('yes\n'))
        args.approval='INSTALL:'+'a'*64
        confirm(args,intent)
        args.snapshot_confirmed=False
        with self.assertRaises(ValueError):confirm(args,intent)

    def test_saved_outputs_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            private_write(directory,'plan.json','{}\n')
            self.assertEqual((directory/'plan.json').stat().st_mode & 0o777,0o600)
            (directory/'bad').symlink_to(directory/'plan.json')
            with self.assertRaises(ValueError):private_write(directory,'bad','unsafe')


class RC5ApplyIntegrationTests(unittest.TestCase):
    def args(self, root, profile):
        return argparse.Namespace(profile=profile,resolve=False,apply=True,development=False,
             system_updates=False,allow_mirror=[],allow_proxy_env=False,no_wait_cloud_init=True,
             max_new_packages=1000,max_updates=100,npm_bundle=None,state_dir=str(root/'state'),
             out=None,refresh_metadata=False,recovery_reviewed=False,approval=None,
             snapshot_confirmed=True,allow_unvalidated=True)

    def test_complete_apply_all_profiles_resume_and_no_confirmation_writes(self):
        from apply import request
        for profile in ('APP','DB','APP+DB'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sources(root);args=self.args(root,profile)
                data=dict(fixture(),target='offline-target')
                lock=lock_for(profile);lock['npm']=npm_pins(profile)
                w=build_workflow(profile,data,lock);tr=Transport(root,w)
                versions=lock['apt']
                def call(argv,cwd=None):
                    binary=Path(argv[0]).name
                    if binary=='apt-cache' and 'policy' in argv:return 'Candidate: '+versions[argv[-1]]+'\n'
                    if binary=='dpkg-query' and argv[-1].endswith('\n'):
                        return ''.join(n+'\t'+v+'\tinstall ok installed\n' for n,v in tr.versions.items())
                    if binary=='apt-get' and '-s' in argv and all('=' not in v for v in argv[argv.index('install')+1:]):
                        return ''.join('Inst '+n+' ('+v+' Ubuntu [amd64])\n' for n,v in versions.items() if tr.versions.get(n)!=v)
                    return tr(argv,cwd)
                before=snapshot(root)
                def approval(a,intent):
                    self.assertEqual(before,snapshot(root))
                    self.assertFalse(any('update' in argv for argv,_ in tr.calls))
                with patch('apply.confirm',side_effect=approval),contextlib.redirect_stderr(io.StringIO()):
                    result=run_apply(args,data,root=root,transport=call)
                self.assertEqual(result['status'],'PASS')
                installed=sum('install' in a and '-s' not in a for a,_ in tr.calls)
                with patch('apply.confirm'),contextlib.redirect_stderr(io.StringIO()):
                    second=run_apply(args,data,root=root,transport=call)
                self.assertEqual(second['status'],'PASS')
                self.assertEqual(installed,sum('install' in a and '-s' not in a for a,_ in tr.calls))
                self.assertFalse((root/'usr/sbin/policy-rc.d').exists())
                directory=Path(result['directory'])
                self.assertEqual(directory.stat().st_mode & 0o777,0o700)
                for name in ('lock.json','plan.json','SUMMARY.txt'):
                    self.assertEqual((directory/name).stat().st_mode & 0o777,0o600)
                saved=json.loads((directory/'plan.json').read_text())
                self.assertEqual(saved['authorization'],request(args,data,root=root))

    def test_network_failure_resolve_autoclears_and_no_package_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);args=self.args(root,'DB');data=dict(fixture(),target='offline-target')
            def fail(argv,cwd=None):
                if Path(argv[0]).name=='gpg':return Probe()(argv)
                raise CommandError(argv,124,'https://user:password@proxy.invalid')
            with patch('apply.confirm'),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(WorkflowError):run_apply(args,data,root=root,transport=fail)
            journals=list((root/'state').glob('*/preparation/journal.json'))
            self.assertEqual(len(journals),1)
            state=json.loads(journals[0].read_text())['state']
            self.assertIsNone(state['pending']);self.assertEqual(state['events'][-1]['event'],'AUTO_CLEARED')
            self.assertFalse((root/'usr/sbin/policy-rc.d').exists())


class CapturedProviderTests(unittest.TestCase):
    def test_exact_owner_supplied_transip_sources(self):
        directory=BASE/'tests/fixtures/transip-26.04'
        captured=list((directory/'etc/apt/sources.list.d').glob('*.sources'))
        if not captured:self.skipTest('actual owner-supplied TransIP source files absent; no exact reproduction claimed')
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            root=Path(tmp);sources(root)
            for existing in (root/'etc/apt/sources.list.d').glob('*'):existing.unlink()
            for path in captured:shutil.copyfile(path,root/'etc/apt/sources.list.d'/path.name)
            legacy=directory/'etc/apt/sources.list'
            if legacy.exists():shutil.copyfile(legacy,root/'etc/apt/sources.list')
            with self.assertRaises(MirrorError) as failure:read_sources(root)
            self.assertEqual(failure.exception.args,('unapproved-apt-source',))
            # Discover the exact captured URI for this explicit test approval,
            # never as an automatic target trust expansion.
            from sources import deb822, legacy as parse_legacy
            uris=set()
            for path in captured:
                for fields in deb822(path.read_text()):uris.update(fields.get('uris','').split())
            if legacy.exists():
                for fields in parse_legacy(legacy.read_text()):uris.update(fields.get('uris','').split())
            accepted=read_sources(root,sorted(uris))
            self.assertTrue(accepted['entries'])
            self.assertTrue(all(e['signed_by'].startswith('/usr/share/keyrings/ubuntu-archive-keyring.gpg') for e in accepted['entries']))
