"""Pure admission policy and injectable, bounded, read-only inventory."""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess

BASE = Path(__file__).resolve().parents[1]
PROFILES = json.loads((BASE/'profiles/profiles.json').read_text())

# Only installer-defined diagnostic codes may enter reports; never arbitrary
# exception messages, process output, source URLs or credentials.
PUBLIC_CODES = {
    'mirror-uri-invalid','archive-key-gpg-required','system-inventory','package-inventory','listener-inventory','swap-inventory-format',
    'apt-source-symlink','apt-source-owner','apt-source-format','apt-source-duplicate',
    'apt-source-enabled','apt-source-unreviewed-option','insecure-apt-source',
    'apt-source-keyring','apt-source-uri-required','unapproved-apt-source',
    'apt-source-path','apt-suite','apt-components','apt-source-type',
    'apt-source-architecture','no-approved-apt-sources','ubuntu-keyring-required',
    'archive-key-symlink','archive-key-owner','archive-key-invalid','archive-key-format',
    'archive-key-fingerprint','archive-signature-fingerprint','archive-signature-invalid',
    'signed-release-metadata-required','release-metadata-symlink','release-metadata-owner',
    'package-metadata-duplicate','package-authenticated-metadata','package-dependency-format','pinned-package-unavailable',
    'swap-mount','swap-filesystem','swap-capacity','swap-disk-reserve',
}
PROBE_ERRORS = (OSError,ValueError,KeyError,IndexError,StopIteration,TypeError,
                RuntimeError,subprocess.SubprocessError)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def query(argv):
    result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,
                          timeout=15,check=True,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
    return result.stdout


def inventory(root='/', query_fn=None, allow_mirrors=()):
    root=Path(root).absolute(); call=query if query_fn is None else query_fn
    result={'kernel':platform.system(),'arch':platform.machine(),'cpu':os.cpu_count(),
            'errors':[],'diagnostics':[],'warnings':[]}
    def failure(stage,error,tool=None):
        code=error.args[0] if isinstance(error,ValueError) and error.args and isinstance(error.args[0],str) and error.args[0] in PUBLIC_CODES else stage+'-probe-failed'
        if isinstance(error,FileNotFoundError): code=stage+'-input-or-tool-missing'
        if isinstance(error,PermissionError): code=stage+'-permission-denied'
        diagnostic={'stage':stage,'code':code}
        from sources import MirrorError
        if isinstance(error, MirrorError): diagnostic.update(host=error.host, remedy=error.remedy)
        if code == 'archive-key-gpg-required': diagnostic['remedy'] = 'Install gpg first: apt-get install gpg (explicit manual authorization required)'
        if tool: diagnostic['tool']=tool
        if isinstance(error,subprocess.CalledProcessError): diagnostic['exit_code']=error.returncode
        result['errors'].append(stage); result['diagnostics'].append(diagnostic)
    try:
        result['disk_gib']=shutil.disk_usage(root).free/2**30
        raw=(root/'etc/os-release').read_text()
        values=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        result['os']={k:v.strip('"') for k,v in values.items() if k in ('ID','VERSION_ID')}
        result['ram_mib']=int(next(line for line in (root/'proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')).split()[1])/1024
    except PROBE_ERRORS as error: failure('system-inventory',error)
    try:
        raw=call(['/usr/bin/dpkg-query','-W','-f=${Package}\t${Version}\t${Status}\n'])
        result['packages']={p:v for p,v,s in (line.split('\t',2) for line in raw.splitlines()) if s in ('install ok installed','hold ok installed')}
    except PROBE_ERRORS as error: failure('package-inventory',error,'dpkg-query')
    try:
        raw=call(['/usr/bin/ss','-H','-ltn'])
        result['tcp_ports']=sorted({int(line.split()[3].rsplit(':',1)[1]) for line in raw.splitlines()})
    except PROBE_ERRORS as error: failure('listener-inventory',error,'ss')
    try:
        from swap import active_swap
        result['swap_devices']=active_swap(call)
        result['swap_bytes']=sum(result['swap_devices'].values())
    except PROBE_ERRORS as error: failure('swap-inventory',error,'swapon')
    # Swap enumeration and filesystem probing have independent diagnostics.
    try:
        parent=root/'var/lib/universal-linux-installer/swap'
        while not parent.exists(): parent=parent.parent
        mounts=json.loads(call(['/usr/bin/findmnt','--json','--target',str(parent),'--output','FSTYPE,OPTIONS']))
        rows=mounts['filesystems']
        if len(rows)!=1: raise ValueError('swap-mount')
        result['filesystem']=rows[0]['fstype']
        result['swap_mount_rw']='rw' in rows[0]['options'].split(',')
        result['swap_disk_bytes']=shutil.disk_usage(parent).free
    except PROBE_ERRORS as error: failure('swap-storage-inventory',error,'findmnt')
    result['source_policy_valid']=False; result['key_valid']=False; result['sources_valid']=False
    try:
        from sources import source_summary
        result['source_summary']=source_summary(root,result['arch'],allow_mirrors)
        result['source_policy_valid']=True
        result['node_universe']=not result['source_summary']['universe_missing_suites']
    except PROBE_ERRORS as error: failure('source-inventory',error,'source-policy')
    # A rejected mirror must never suppress independent key/signature/cache probes.
    try:
        from node import verify_key
        verify_key(root,call); result['key_valid']=True
    except PROBE_ERRORS as error: failure('source-inventory',error,'gpg')
    result['sources_valid']=result['source_policy_valid'] and result['key_valid']
    result['source_metadata']='not-cached'
    try:
        from node import verify_releases
        verify_releases(root,call,allow_mirrors,enforce_policy=False)
        result['source_metadata']='verified-cached'
    except PROBE_ERRORS as error:
        if isinstance(error,ValueError) and error.args==('signed-release-metadata-required',):
            result['warnings'].append('source-metadata-not-cached; audit performs no refresh')
        else:
            result['sources_valid']=False; result['source_metadata']='failed'
            failure('cached-signatures',error,'gpgv')
    try:
        from index_age import index_age
        result['apt_index_age']=index_age(root,allow_mirrors)
    except PROBE_ERRORS:
        result['apt_index_age']={'status':'WARN','age_days':None,'indexes':[]}
    result['service_manager']=(root/'run/systemd/system').is_dir() and (root/'usr/bin/systemctl').is_file()
    result['services']={}
    if result['service_manager']:
        for service in ('nginx','postgresql'):
            try:
                result['services'][service]=call(['/usr/bin/systemctl','show',service,'--property=LoadState,ActiveState']).strip()
            except PROBE_ERRORS as error: failure('service-inventory',error,'systemctl')
    result['package_candidates']={}; result['node_package_metadata']={}
    for package in sorted({p for policy in PROFILES.values() for p in policy['packages']}):
        try:
            raw=call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','policy',package])
            candidate=next((line.split(':',1)[1].strip() for line in raw.splitlines() if line.strip().startswith('Candidate:')),'(none)')
            result['package_candidates'][package]=None if candidate=='(none)' else candidate
            if package in ('nodejs','npm') and candidate!='(none)':
                # Display dependencies from existing metadata only; never execute
                # an audit-time solver, download or update to guess availability.
                raw=call(['/usr/bin/apt-cache','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','show',package+'='+candidate])
                from node import package_metadata
                result['node_package_metadata'][package]=package_metadata(raw,package,candidate)
        except PROBE_ERRORS as error: failure('package-source-inventory',error,'apt-cache')
    return result


def plan(profile,observed):
    policy=PROFILES[profile]; failures=[]; warnings=list(observed.get('warnings',[]));checks=[]
    def check(name,status,detail): checks.append({'id':name,'status':status,'detail':detail})
    platform_fail=[]
    if observed.get('kernel')!='Linux': platform_fail.append('linux-required')
    if observed.get('os')!={'ID':'ubuntu','VERSION_ID':'26.04'}: platform_fail.append('unsupported-os')
    if observed.get('arch') not in ('x86_64','aarch64'): platform_fail.append('unsupported-architecture')
    failures.extend(platform_fail)
    check('platform','FAIL' if platform_fail else 'PASS','Ubuntu 26.04; x86_64/arm64 required')
    for key,minimum in (('cpu',policy['minimum']['cpu']),('ram_mib',policy['minimum']['ram_mib']),('disk_gib',policy['disk_gib'])):
        value=observed.get(key)
        valid=type(value) in (int,float) and math.isfinite(value)
        recommended=policy['recommended'].get(key,minimum)
        if not valid or value<minimum: failures.append(key); status='FAIL'
        elif value<recommended: warnings.append(key+'-below-recommendation');status='WARN'
        else: status='PASS'
        display=f'{value:.0f}' if valid else 'unknown'
        check(key,status,display+'; minimum '+str(minimum)+'; recommended '+str(recommended))
    if profile=='APP+DB' and type(observed.get('ram_mib')) in (int,float) and observed['ram_mib']<policy['recommended']['ram_mib']:
        warnings.append('APP+DB technically possible at test minimum; physical RAM insufficient for reliable builds and runtime; swap does not remedy RAM capacity.')
    existing=observed.get('swap_bytes')
    valid_swap=type(existing) is int and existing>=0
    check('swap-inventory','PASS' if valid_swap else 'FAIL',f'{existing/2**30:.2f} GiB active; zero is a valid initial state' if valid_swap else 'unknown; see diagnostics')
    try:
        from swap import swap_plan
        if observed.get('swap_mount_rw',True) is not True: raise ValueError('swap-mount')
        swap=swap_plan(existing,observed.get('swap_disk_bytes'),observed.get('filesystem'),policy['disk_gib']*2**30)
        if swap['deficit_bytes']: warnings.append('swap-deficit-requires-explicit-execution')
        swap['path']='/var/lib/universal-linux-installer/swap/swapfile'
        swap['persistent']=True;swap['mode']='0600';swap['audit_changes']=False
        check('swap-preflight','WARN' if swap['deficit_bytes'] else 'PASS',f"target 4 GiB; deficit {swap['deficit_bytes']/2**30:.2f} GiB; audit prepares only, no allocation/fstab/activation")
    except ValueError:
        failures.append('swap-preflight');swap={'required_bytes':4*2**30,'audit_changes':False}
        check('swap-preflight','FAIL','inventory/filesystem/free-space/reserve failed; no change')
    sources_valid=observed.get('sources_valid') is True
    if not sources_valid: failures.append('package-sources')
    source_data=observed.get('source_summary',{})
    if source_data.get('missing_base_suites'): failures.append('package-source-suites')
    source_status='FAIL' if not sources_valid or source_data.get('missing_base_suites') else 'WARN' if observed.get('source_metadata')=='not-cached' else 'PASS'
    check('package-sources',source_status,'source policy + Canonical key fingerprints; '+observed.get('source_metadata','metadata requires fresh execution-time verification'))
    check('source-policy','PASS' if observed.get('source_policy_valid',sources_valid) else 'FAIL','approved source URIs; see bounded host/remedy diagnostics')
    check('archive-key','PASS' if observed.get('key_valid',sources_valid) else 'FAIL','Canonical fingerprint allowlist; no homedir/keybox/lock/trustdb writes')
    cached=observed.get('source_metadata','not-cached')
    check('cached-signatures','PASS' if cached=='verified-cached' else 'FAIL' if cached=='failed' else 'WARN',cached+'; independent of URI approval')
    age=observed.get('apt_index_age',{'status':'WARN','age_days':None})
    check('apt-index-age',age['status'],'index '+(str(age['age_days'])+' days old' if age.get('age_days') is not None else 'age unknown')+'; candidates/closure unreliable until refresh' if age['status']=='WARN' else 'cached indexes <=7 days old')
    missing=[p for p in policy['packages'] if not observed.get('package_candidates',{}).get(p)]
    if missing: warnings.append('packages-unavailable-in-current-cache: '+','.join(missing))
    check('packages','WARN' if missing else 'PASS','missing in current cache: '+','.join(missing) if missing else 'profile candidates visible; exact signed dependency closure still required')
    if profile!='DB':
        from node import compatible_node_npm
        versions={name:observed.get('package_candidates',{}).get(name) for name in ('nodejs','npm')}
        status='WARN' if any(v is None for v in versions.values()) else 'PASS' if compatible_node_npm(versions) else 'FAIL'
        if status=='FAIL' and (observed.get('apt_index_age',{}).get('status','WARN')=='WARN' or observed.get('source_metadata')!='verified-cached'): status='WARN'
        if status=='FAIL':failures.append('node-npm-compatibility')
        check('node-npm',status,'Ubuntu universe; Node 22 LTS >=22.12 and npm 9; exact versions/dependencies in JSON')
    manager=observed.get('service_manager') is True
    if not manager: failures.append('systemd-required')
    services=all(s in observed.get('services',{}) for s in policy['services'])
    if not services: failures.append('service-inventory')
    check('services','PASS' if manager and services else 'FAIL','systemd and required service inventory; absent uninstalled services are valid')
    failures.extend(observed.get('errors',[])); failures=list(dict.fromkeys(failures))
    body={'schema':2,'profile':profile,'observations':observed,'packages':policy['packages'],
          'failures':failures,'checks':checks,'diagnostics':observed.get('diagnostics',[]),
          'capacity':{'minimum':policy['minimum'],'recommended':policy['recommended'],'disk_reserve_gib':policy['disk_gib'],'swap':swap},
          'required_services':policy['services'],'status':'FAIL' if failures else 'WARN','mode':'dry-run',
          'installation_authorized':False,'warnings':warnings+['Exact package/source lock and target approval required; live compatibility untested.']}
    body['plan_id']=digest(body)
    return body
