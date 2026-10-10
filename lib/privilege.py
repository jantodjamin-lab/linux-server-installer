"""Explicit interactive sudo re-execution; no password API, pipe or storage."""
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def sudo_available():
    path=Path('/usr/bin/sudo')
    try:
        s=path.resolve(strict=True).stat()
        return stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode & 0o022
    except OSError: return False


def privileged_arguments(args):
    # Absolute, separate argv elements preserve spaces and cannot become shell
    # syntax. The elevated CLI repeats plan integrity, identity and preflight.
    if getattr(args,'apply',False) or getattr(args,'resolve',False):
        result=['--profile',args.profile,'--apply' if args.apply else '--resolve',
                '--state-dir',str(Path(args.state_dir).absolute()),
                '--max-new-packages',str(args.max_new_packages),'--max-updates',str(args.max_updates)]
        if args.resolve:result.extend(['--out',str(Path(args.out).absolute()),'--refresh-metadata'])
        if args.approval:result.extend(['--approval',args.approval])
        if args.snapshot_confirmed:result.append('--snapshot-confirmed')
        if args.allow_unvalidated:result.append('--allow-unvalidated')
    else:
        result=['--profile',args.profile,'--execute','--plan',str(Path(args.plan).resolve()),
                '--approval',args.approval,'--snapshot-confirmed','--allow-unvalidated',
                '--state-dir',str(Path(args.state_dir).absolute())]
    for uri in getattr(args,'allow_mirror',[]):result.extend(['--allow-mirror',uri])
    for attr,flag in (('allow_proxy_env','--allow-proxy-env'),('no_wait_cloud_init','--no-wait-cloud-init'),('show_diagnostics','--show-diagnostics')):
        if getattr(args,attr,False):result.append(flag)
    if args.npm_bundle: result.extend(['--npm-bundle',str(Path(args.npm_bundle).resolve())])
    for attr,flag in (('development','--development'),('system_updates','--system-updates'),
                      ('recovery_reviewed','--recovery-reviewed'),('json','--json')):
        if getattr(args,attr): result.append(flag)
    return result


def interactive_execute(args):
    if os.geteuid()==0: return None
    if not (args.execute or getattr(args,'apply',False) or getattr(args,'resolve',False)) or not args.sudo: raise ValueError('sudo-execute-only')
    if not sys.stdin.isatty(): raise ValueError('sudo-interactive-terminal-required')
    if not sudo_available(): raise ValueError('sudo-trusted-executable-required')
    script=Path(__file__).resolve().with_name('cli.py')
    proxy_keys=('HTTP_PROXY','HTTPS_PROXY','NO_PROXY','http_proxy','https_proxy','no_proxy')
    preserve=['--preserve-env='+','.join(proxy_keys)] if getattr(args,'allow_proxy_env',False) else []
    argv=['/usr/bin/sudo','-k','-u','root',*preserve,'--','/usr/bin/python3','-E','-s','-B',str(script),*privileged_arguments(args)]
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'}
    if preserve:
        for key in proxy_keys:
            if key in os.environ:env[key]=os.environ[key]
    term=os.environ.get('TERM','')
    if re.fullmatch(r'[A-Za-z0-9+_.-]{1,64}',term): env['TERM']=term
    try:
        # Inherit the interactive terminal. sudo owns the password prompt; do
        # not capture input/output, use -S/-A, read a password, or keep a token.
        completed=subprocess.run(argv,check=False,env=env)
    except KeyboardInterrupt: return 130
    except OSError: raise ValueError('sudo-start-failed') from None
    return completed.returncode if completed.returncode>=0 else 128-completed.returncode
