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
    result=['--profile',args.profile,'--execute','--plan',str(Path(args.plan).resolve()),
            '--approval',args.approval,'--snapshot-confirmed','--allow-unvalidated',
            '--state-dir',str(Path(args.state_dir).absolute())]
    if args.npm_bundle: result.extend(['--npm-bundle',str(Path(args.npm_bundle).resolve())])
    for attr,flag in (('development','--development'),('system_updates','--system-updates'),
                      ('recovery_reviewed','--recovery-reviewed'),('json','--json')):
        if getattr(args,attr): result.append(flag)
    return result


def interactive_execute(args):
    if os.geteuid()==0: return None
    if not args.execute or not args.sudo: raise ValueError('sudo-execute-only')
    if not sys.stdin.isatty(): raise ValueError('sudo-interactive-terminal-required')
    if not sudo_available(): raise ValueError('sudo-trusted-executable-required')
    script=Path(__file__).resolve().with_name('cli.py')
    argv=['/usr/bin/sudo','-k','-u','root','--','/usr/bin/python3','-E','-s','-B',str(script),*privileged_arguments(args)]
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'}
    term=os.environ.get('TERM','')
    if re.fullmatch(r'[A-Za-z0-9+_.-]{1,64}',term): env['TERM']=term
    try:
        # Inherit the interactive terminal. sudo owns the password prompt; do
        # not capture input/output, use -S/-A, read a password, or keep a token.
        completed=subprocess.run(argv,check=False,env=env)
    except KeyboardInterrupt: return 130
    except OSError: raise ValueError('sudo-start-failed') from None
    return completed.returncode if completed.returncode>=0 else 128-completed.returncode
