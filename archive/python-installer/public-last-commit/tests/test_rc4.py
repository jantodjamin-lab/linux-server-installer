"""RC4 uses faithful util-linux output, full fixture audits and real public keys.

All system/package/format/activation/sudo effects are mocked. Real GnuPG reads
only public fixture data; util-linux is invoked with --help, never for activation.
"""
import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture
from test_workflow import sources, lock_for
from test_local import Transport, npm_bundle
from test_rc3 import manager, MIB
from core import inventory, plan, query, PROFILES
from cli import main
from local import LocalRunner, APT_SECURITY
from node import verify_key, compatible_node_npm, package_metadata, verify_releases, universe_source
from sources import read_sources, source_summary, universe_coverage
from swap import active_swap
from workflow import build_workflow, validate_lock
from privilege import interactive_execute, privileged_arguments

BASE=Path(__file__).resolve().parents[1]


def snapshot(root):
    return {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


class Probe:
    """Models Ubuntu tools and refuses the old unsupported swapon/GPG commands."""
    def __init__(self, swap='', missing=(), source_failure=None):
        self.calls=[];self.swap=swap;self.missing=missing;self.source_failure=source_failure
    def __call__(self,argv):
        self.calls.append(argv);tool=Path(argv[0]).name
        if tool=='swapon':
            if argv[1:]!=['--show=NAME,SIZE','--bytes','--noheadings','--raw']: raise AssertionError('unsupported swapon invocation')
            return self.swap
        if tool=='findmnt':return json.dumps({'filesystems':[{'fstype':'ext4','options':'rw,relatime'}]})
        if tool=='gpg':
            for option in ('--no-default-keyring','--keyring','--trust-model','--no-auto-check-trustdb','--lock-never','--list-keys','--no-autostart'): assert option in argv
            assert '--show-keys' not in argv
            if self.source_failure:raise self.source_failure
            return 'pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::F6ECB3762474EDA9D21B7022871920D1991BC93C:\n'
        if tool=='gpgv':return '[GNUPG:] VALIDSIG F6ECB3762474EDA9D21B7022871920D1991BC93C 2026-01-01 0 0 4 0 1 10 01 F6ECB3762474EDA9D21B7022871920D1991BC93C\n'
        if tool=='dpkg-query':return 'python3\t3.14.0-1\tinstall ok installed\n'
        if tool=='ss':return ''
        if tool=='systemctl':return 'LoadState=not-found\nActiveState=inactive\n'
        if tool=='apt-cache':
            assert 'Dir::Cache::pkgcache=' in argv and 'Dir::Cache::srcpkgcache=' in argv
            name=argv[-1].split('=',1)[0]
            version={'nodejs':'22.22.1+dfsg+~cs22.19.15-1ubuntu1','npm':'9.2.0~ds3-1'}.get(name,'1.0-1')
            if 'policy' in argv:return '  Candidate: '+('(none)' if name in self.missing else version)+'\n'
            if 'show' in argv:
                dependencies='libnode127 (= '+version+')' if name=='nodejs' else 'nodejs, node-semver, node-gyp'
                return 'Package: '+name+'\nVersion: '+version+'\nArchitecture: '+('all' if name=='npm' else 'amd64')+'\nDepends: '+dependencies+'\nFilename: pool/universe/fixture.deb\nSHA256: '+'a'*64+'\n'
        raise AssertionError('unexpected probe: '+tool)


def audit_tree(root):
    sources(root)
    (root/'etc/os-release').write_text('ID=ubuntu\nVERSION_ID="26.04"\n')
    (root/'proc').mkdir();(root/'proc/meminfo').write_text('MemTotal: 863232 kB\n')
    (root/'run/systemd/system').mkdir(parents=True)
    (root/'usr/bin').mkdir();(root/'usr/bin/systemctl').write_bytes(b'fixture')
    (root/'etc/machine-id').write_text('offline-fixture-target\n')


def observed(root,probe):
    usage=shutil._ntuple_diskusage(120*10**9,26*10**9,94*10**9)
    with patch('core.platform.system',return_value='Linux'),patch('core.platform.machine',return_value='x86_64'),patch('core.os.cpu_count',return_value=1),patch('core.shutil.disk_usage',return_value=usage):
        return inventory(root,probe)


class RC4SwapRegressionTests(unittest.TestCase):
    def test_successful_empty_swap_is_zero(self):
        for raw in ('','\n',' \n\t\n'):
            probe=Probe(swap=raw);self.assertEqual(active_swap(probe),{})
            self.assertNotIn('--json',probe.calls[0])
    def test_raw_devices_and_escaped_paths(self):
        raw='/dev/sda2 2147483648\n/swap\\x20file 1073741824\n'
        self.assertEqual(active_swap(Probe(swap=raw)),{'/dev/sda2':2*2**30,'/swap file':2**30})
    def test_failures_are_not_empty_swap(self):
        for raw in ('NAME SIZE','/swap 4G','/swap -1','/swap 0','/swap 1\n/swap 1','/swap 1 extra','{}'):
            with self.assertRaises(ValueError):active_swap(Probe(swap=raw))
        def denied(argv):raise PermissionError('private error')
        with self.assertRaises(PermissionError):active_swap(denied)
    def test_real_util_linux_option_compatibility_only_help(self):
        if not shutil.which('swapon'):self.skipTest('swapon unavailable')
        good=subprocess.run(['/usr/sbin/swapon','--show=NAME,SIZE','--bytes','--noheadings','--raw','--help'],capture_output=True,timeout=10)
        self.assertEqual(good.returncode,0)
        bad=subprocess.run(['/usr/sbin/swapon','--json','--help'],capture_output=True,timeout=10)
        self.assertNotEqual(bad.returncode,0)
    def test_reported_clean_capacity_all_profiles_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);before=snapshot(root)
            for profile in PROFILES:
                probe=Probe();data=observed(root,probe);report=plan(profile,data)
                self.assertEqual(data['swap_bytes'],0);self.assertFalse(report['failures'])
                self.assertEqual(report['status'],'WARN');self.assertEqual(report['capacity']['swap']['deficit_bytes'],4*2**30)
                self.assertFalse(report['capacity']['swap']['audit_changes'])
                self.assertEqual(report,plan(profile,data));self.assertEqual(before,snapshot(root))
                self.assertFalse(any(Path(a[0]).name in ('apt-get','mkswap','sudo','swapoff') for a in probe.calls))
    def test_swap_probe_failure_keeps_specific_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);probe=Probe(swap='invalid')
            data=observed(root,probe);report=plan('APP',data)
            self.assertIn('swap-inventory',report['failures']);self.assertIn('swap-preflight',report['failures'])
            self.assertIn({'stage':'swap-inventory','code':'swap-inventory-format','tool':'swapon'},data['diagnostics'])


class RC4SourceRegressionTests(unittest.TestCase):
    def test_real_key_listing_readonly_without_home(self):
        if not shutil.which('gpg'):self.skipTest('gpg unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root)
            key=root/'usr/share/keyrings/ubuntu-archive-keyring.gpg'
            key.write_bytes(base64.b64decode((BASE/'tests/fixtures/ubuntu-archive-2018.b64').read_text()));key.chmod(0o644)
            before=snapshot(root)
            self.assertTrue(verify_key(root,query));self.assertEqual(before,snapshot(root))
            self.assertFalse((root/'.gnupg').exists())
    def test_rc3_gpg_shape_reproduces_failure_on_fixture(self):
        if not shutil.which('gpg'):self.skipTest('gpg unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);key=root/'key.gpg';key.write_bytes(base64.b64decode((BASE/'tests/fixtures/ubuntu-archive-2018.b64').read_text()))
            home=root/'does-not-exist'
            result=subprocess.run(['/usr/bin/gpg','--no-options','--batch','--homedir',str(home),'--with-colons','--show-keys',str(key)],capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertFalse(home.exists())
    def test_standard_formats_backports_and_disabled_stanzas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);path=root/'etc/apt/sources.list.d/ubuntu.sources'
            path.write_text('Types: deb deb-src\nURIs: https://nl.archive.ubuntu.com/ubuntu/\nSuites: resolute resolute-updates\n resolute-security resolute-backports\nComponents: main\n universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n\nEnabled: no\nTypes: deb\nURIs: https://unapproved.invalid/repo\n')
            data=read_sources(root);self.assertEqual(data['disabled_stanzas'],1)
            self.assertIn('resolute-backports',source_summary(root)['suites'])
            self.assertFalse(source_summary(root)['universe_missing_suites'])
            path.write_text('# Deb822 disabled; legacy signed source is explicit\n')
            legacy=root/'etc/apt/sources.list';legacy.write_text('deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu resolute main universe\n');legacy.chmod(0o644)
            self.assertEqual(len(read_sources(root)['entries']),1)
            legacy.write_text('deb https://archive.ubuntu.com/ubuntu resolute main\n')
            with self.assertRaises(ValueError):read_sources(root)
    def test_partial_universe_preserves_signed_by_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);path=root/'etc/apt/sources.list.d/ubuntu.sources'
            path.write_text('Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: resolute\nComponents: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n\nTypes: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: resolute-updates resolute-security\nComponents: main\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
            original=path.read_bytes();before=read_sources(root)['entries']
            missing=set(source_summary(root)['universe_missing_suites'])
            generated=universe_source('x86_64',missing,root)
            destination=root/'etc/apt/sources.list.d/universal-node-universe.sources';destination.write_text(generated);destination.chmod(0o644)
            self.assertEqual(path.read_bytes(),original)
            self.assertNotIn('Suites: resolute\n',generated)
            for entry in read_sources(root)['entries'][len(before):]:
                self.assertEqual(entry['signed_by'],'/usr/share/keyrings/ubuntu-archive-keyring.gpg')
            self.assertFalse(source_summary(root)['universe_missing_suites'])
    def test_real_apt_parser_signed_by_consistency_offline(self):
        if not shutil.which('apt-cache'):self.skipTest('apt-cache unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root)
            source=root/'etc/apt/sources.list.d/ubuntu.sources'
            source.write_text(source.read_text().replace('main universe','main'))
            generated=root/'etc/apt/sources.list.d/universal-node-universe.sources'
            generated.write_text(universe_source('x86_64',{'resolute','resolute-updates','resolute-security'},root));generated.chmod(0o644)
            (root/'status').write_text('');(root/'lists').mkdir()
            argv=['/usr/bin/apt-cache']
            options={'Dir::Etc::sourcelist':str(root/'etc/apt/sources.list'),
                     'Dir::Etc::sourceparts':str(root/'etc/apt/sources.list.d'),
                     'Dir::Etc::main':'/dev/null','Dir::Etc::parts':'-',
                     'Dir::State::status':str(root/'status'),'Dir::State::lists':str(root/'lists'),
                     'Dir::Cache::pkgcache':'','Dir::Cache::srcpkgcache':''}
            for key,value in options.items():argv.extend(['-o',key+'='+value])
            argv.append('policy');before=snapshot(root)
            env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'}
            good=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(good.returncode,0,good.stderr);self.assertEqual(before,snapshot(root))
            generated.write_text(generated.read_text().replace('Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg','Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg F6ECB3762474EDA9D21B7022871920D1991BC93C'))
            bad=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(bad.returncode,0);self.assertIn('Conflicting values set for option Signed-By',bad.stderr)
    def test_architecture_coverage_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root);path=root/'etc/apt/sources.list.d/ubuntu.sources'
            path.write_text(path.read_text()+'Architectures: arm64\n')
            self.assertEqual(universe_coverage(root,'x86_64'),set())
            with self.assertRaises(ValueError):universe_source('x86_64',{'resolute'},root)
    def test_source_diagnostics_not_arbitrary_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root)
            data=observed(root,Probe(source_failure=ValueError('archive-key-fingerprint')))
            self.assertIn('source-inventory',data['errors']);self.assertIn('package-sources',plan('APP',data)['failures'])
            self.assertTrue(any(x['code']=='archive-key-fingerprint' for x in data['diagnostics']))
            data=observed(root,Probe(source_failure=RuntimeError('PRIVATE_PASSWORD_SHOULD_NOT_APPEAR')))
            self.assertNotIn('PRIVATE_PASSWORD',json.dumps(data))
    def test_missing_cache_warns_without_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root)
            for path in (root/'var/lib/apt/lists').glob('*'):path.unlink()
            probe=Probe(missing=('nodejs','npm'));data=observed(root,probe);report=plan('APP',data)
            self.assertTrue(data['sources_valid']);self.assertEqual(data['source_metadata'],'not-cached')
            self.assertFalse(report['failures']);self.assertEqual(report['status'],'WARN')
            self.assertFalse(any(Path(a[0]).name=='apt-get' for a in probe.calls))
    def test_available_bad_signature_is_not_hidden_by_missing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sources(root)
            (root/'var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_resolute-security_InRelease').unlink()
            def bad(argv):return '[GNUPG:] BADSIG bad'
            with self.assertRaises(ValueError):verify_releases(root,bad)


class RC4NodeTests(unittest.TestCase):
    def test_supported_ubuntu_versions_no_fallback(self):
        for node,npm,accepted in (('22.22.1+dfsg+~cs22.19.15-1ubuntu1','9.2.0~ds3-1',True),('22.12.0-1','9.2.0',True),('22.11.0','9.2.0',False),('24.0.0','9.2.0',False),('22.22.1','10.0.0',False),('22.22.1bad','9.2.0',False)):
            self.assertEqual(compatible_node_npm({'nodejs':node,'npm':npm}),accepted)
    def test_cached_dependency_details_and_missing_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit_tree(root);data=observed(root,Probe())
            self.assertIn('node-semver',data['node_package_metadata']['npm']['depends'])
            self.assertIn('libnode127',data['node_package_metadata']['nodejs']['depends'][0])
            report=plan('APP',data);self.assertFalse(report['failures'])
    def test_missing_or_tampered_package_metadata_refused(self):
        for raw in ('','Package: npm\nVersion: 9.2.0\n','Package: npm\nVersion: 9.2.0\nFilename: pool/../npm.deb\nSHA256: '+'a'*64):
            with self.assertRaises(ValueError):package_metadata(raw,'npm','9.2.0')
        self.assertIn('Acquire::AllowWeakRepositories=false',APT_SECURITY)
        self.assertIn('APT::Update::Error-Mode=any',APT_SECURITY)


class RC4ExecutionPreflightTests(unittest.TestCase):
    def test_missing_packages_or_dependencies_stop_before_swap(self):
        for unavailable in ('metadata','dependency'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'target';root.mkdir();sources(root)
                w=build_workflow('DB',fixture(),lock_for('DB'));tr=Transport(root,w)
                before=(root/'etc/apt/sources.list.d/ubuntu.sources').read_bytes()
                def incomplete(argv,cwd=None):
                    if unavailable=='metadata' and Path(argv[0]).name=='apt-cache':return ''
                    if unavailable=='dependency' and '-s' in argv:return 'Inst unpinned-dependency (1.0 Ubuntu [amd64])\n'
                    return tr(argv,cwd)
                runner=LocalRunner(w,'INSTALL:'+w['plan_id'],True,True,root,incomplete)
                from journal import run_workflow
                with self.assertRaises(RuntimeError):run_workflow(w,runner,Path(tmp)/'private')
                self.assertFalse(runner.swap.path.exists());self.assertFalse(any('install' in a and '-s' not in a for a,_ in tr.calls))
                self.assertEqual(before,(root/'etc/apt/sources.list.d/ubuntu.sources').read_bytes())
    def test_workflow_checks_closure_before_swap_or_updates(self):
        w=build_workflow('DB',fixture(),lock_for('DB'));ids=[s['id'] for s in w['steps']]
        self.assertLess(ids.index('package-preflight'),ids.index('swap'))
        self.assertLess(ids.index('swap'),ids.index('packages'))


class RC4SudoTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(profile='APP',execute=True,sudo=True,plan='reviewed plan.json',approval='INSTALL:'+'a'*64,snapshot_confirmed=True,allow_unvalidated=True,state_dir='private state',npm_bundle='reviewed bundle',development=False,system_updates=False,recovery_reviewed=False,json=True)
    def test_interactive_inherits_terminal_no_password_or_env(self):
        args=self.args()
        with patch('privilege.os.geteuid',return_value=1000),patch('privilege.sys.stdin.isatty',return_value=True),patch('privilege.sudo_available',return_value=True),patch('privilege.subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run,patch.dict(os.environ,{'SUDO_ASKPASS':'untrusted-helper','PYTHONPATH':'untrusted','PASSWORD':'not-forwarded'}):
            self.assertEqual(interactive_execute(args),0)
        argv=run.call_args.args[0];kwargs=run.call_args.kwargs
        self.assertEqual(argv[:6],['/usr/bin/sudo','-k','-u','root','--','/usr/bin/python3'])
        self.assertNotIn('-S',argv);self.assertNotIn('-A',argv);self.assertNotIn('--sudo',argv)
        self.assertTrue(Path(argv[9]).is_absolute())
        for key in ('stdin','input','capture_output','stdout','stderr','shell'):self.assertNotIn(key,kwargs)
        self.assertNotIn('SUDO_ASKPASS',kwargs['env']);self.assertNotIn('PASSWORD',kwargs['env'])
        self.assertNotIn('PYTHONPATH',kwargs['env']);self.assertIn('--plan',argv)
    def test_noninteractive_audit_and_missing_sudo_never_start(self):
        for changes,tty,available in (({'execute':False},True,True),({},False,True),({},True,False)):
            args=self.args()
            for key,value in changes.items():setattr(args,key,value)
            with patch('privilege.os.geteuid',return_value=1000),patch('privilege.sys.stdin.isatty',return_value=tty),patch('privilege.sudo_available',return_value=available),patch('privilege.subprocess.run') as run:
                with self.assertRaises(ValueError):interactive_execute(args)
                run.assert_not_called()
    def test_root_refusal_failure_and_cancel(self):
        args=self.args()
        with patch('privilege.os.geteuid',return_value=0),patch('privilege.subprocess.run') as run:
            self.assertIsNone(interactive_execute(args));run.assert_not_called()
        for response,expected in ((subprocess.CompletedProcess([],1),1),(subprocess.CompletedProcess([],-2),130),(KeyboardInterrupt(),130)):
            with patch('privilege.os.geteuid',return_value=1000),patch('privilege.sys.stdin.isatty',return_value=True),patch('privilege.sudo_available',return_value=True),patch('privilege.subprocess.run',side_effect=response if isinstance(response,BaseException) else None,return_value=response):
                self.assertEqual(interactive_execute(args),expected)
    def test_cli_sudo_forbidden_for_audit(self):
        with patch('sys.argv',['installer','--profile','APP','--audit','--sudo']),patch('privilege.subprocess.run') as run,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:main()
            self.assertEqual(error.exception.code,2);run.assert_not_called()
    def test_absolute_argv_preserves_spaces(self):
        args=self.args();argv=privileged_arguments(args)
        self.assertEqual(argv[argv.index('--plan')+1],str(Path('reviewed plan.json').resolve()))
        self.assertEqual(argv[argv.index('--npm-bundle')+1],str(Path('reviewed bundle').resolve()))


class RC4CompactAuditTests(unittest.TestCase):
    def test_compact_and_json_all_profiles_repeat_without_effects(self):
        for profile in PROFILES:
            for mode in ('--audit','--dry-run'):
                data=fixture();data.update(cpu=1,ram_mib=843,swap_bytes=0,swap_disk_bytes=94*10**9)
                for output_json in (False,True):
                    outputs=[]
                    for _ in range(2):
                        out=io.StringIO();argv=['installer','--profile',profile,mode]+(['--json'] if output_json else [])
                        with patch('sys.argv',argv),patch('cli.inventory',return_value=dict(data)),patch('cli.LocalRunner',side_effect=AssertionError('audit runner')),patch('privilege.subprocess.run',side_effect=AssertionError('audit effects')),contextlib.redirect_stdout(out):
                            self.assertEqual(main(),0)
                        outputs.append(out.getvalue())
                    self.assertEqual(outputs[0],outputs[1])
                    if output_json:self.assertFalse(json.loads(outputs[0])['installation_authorized'])
                    else:
                        self.assertIn('PASS swap-inventory: 0.00 GiB',outputs[0]);self.assertIn('WARN swap-preflight',outputs[0]);self.assertIn('--json',outputs[0])
                        if profile=='APP+DB':self.assertIn('insufficient for reliable',outputs[0])
    def test_failure_summary_and_json_diagnostic(self):
        data=fixture();data.update(sources_valid=False,errors=['source-inventory'],diagnostics=[{'stage':'source-inventory','code':'archive-key-fingerprint','tool':'gpg'}])
        for flags in ([],['--json']):
            out=io.StringIO()
            with patch('sys.argv',['installer','--profile','DB','--audit',*flags]),patch('cli.inventory',return_value=data),contextlib.redirect_stdout(out):
                self.assertEqual(main(),1)
            self.assertIn('archive-key-fingerprint',out.getvalue())
            if flags:self.assertEqual(json.loads(out.getvalue())['status'],'FAIL')
