#!/usr/bin/env python3
"""Developer/CI only: resolve explicit public npm versions, never on a target."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE/'lib'))
from local import check_npm_lock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--angular', required=True)
    parser.add_argument('--codex')
    parser.add_argument('--out', type=Path, default=BASE/'bundle')
    args = parser.parse_args()
    pins = {}
    for folder, name, version in [('angular','@angular/cli',args.angular), ('codex','@openai/codex',args.codex)]:
        if version is None: continue
        if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version): parser.error('explicit semantic version required')
        if folder == 'angular' and not version.startswith('20.'): parser.error('Angular 20 required')
        destination = args.out/folder
        if destination.is_symlink(): raise ValueError('npm-symlink')
        destination.mkdir(parents=True, exist_ok=True)
        package = {'name':'universal-installer-'+folder,'version':'1.0.0','private':True,'dependencies':{name:version}}
        (destination/'package.json').write_text(json.dumps(package, indent=2)+'\n')
        env = {'PATH':os.environ.get('PATH','/usr/bin:/bin'), 'HOME':str(destination.resolve()), 'NPM_CONFIG_USERCONFIG':'/dev/null', 'NPM_CONFIG_GLOBALCONFIG':str(Path(tempfile.gettempdir())/'universal-npm-global-empty'), 'NPM_CONFIG_CACHE':str(Path(tempfile.gettempdir())/'universal-npm-cache')}
        subprocess.run(['npm','install','--package-lock-only','--lockfile-version=3','--ignore-scripts','--no-audit','--no-fund','--registry=https://registry.npmjs.org'], cwd=destination, check=True, env=env, timeout=600)
        pin = {'version':version, 'lock_sha256':hashlib.sha256((destination/'package-lock.json').read_bytes()).hexdigest()}
        check_npm_lock(destination, name, pin); pins[name] = pin
    (BASE/'profiles/npm-pins.json').write_text(json.dumps(pins, sort_keys=True, indent=2)+'\n')
    print(json.dumps(pins, sort_keys=True))


if __name__ == '__main__': main()
