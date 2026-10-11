"""Pure review contract builder. No probes, writes, commands or executor."""
import copy
import hashlib
import json

from infrastructure.installer import preflight


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def build_plan(evidence):
    """Accept current schema-2 evidence; reject inconsistent evaluations.

    The digest binds JSON content, not publisher authenticity or host identity.
    Caller owns reading and saving through preflight.save_evidence.
    """
    evidence = copy.deepcopy(evidence)
    try:
        canonical(evidence)
        if evidence['schema_version'] != 2 or evidence['scope'] != 'local-read-only':
            raise ValueError('Expected local schema-2 preflight evidence')
        if not isinstance(evidence['timestamp_utc'], str) or not evidence['timestamp_utc']:
            raise ValueError('Missing evidence timestamp')
        profile = evidence['profile']
        current = preflight.evaluate(profile, evidence['observations'], evidence['errors'])
        for key in ('checks', 'policy', 'status'):
            expected, observed = current[key], evidence[key]
            if key == 'checks':
                # Probe-error messages contain dict reprs whose key order changes
                # after sorted JSON storage. Error content is bound in the digest.
                def check_content(check):
                    if check['name'] in evidence['errors']:
                        return canonical({k: check[k] for k in ('name', 'status')})
                    return canonical(check)
                expected = sorted(check_content(c) for c in expected)
                observed = sorted(check_content(c) for c in observed)
            if expected != observed:
                raise ValueError('Evidence evaluation inconsistent with current policy')
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('Malformed preflight evidence') from exc
    digest = hashlib.sha256(canonical(evidence).encode()).hexdigest()
    components = []
    for role, ports in (('APP', [80, 443]), ('DB', [5432])):
        if profile not in (role, 'APP-DB'):
            continue
        components.append({
            'role': role, 'state': 'PROPOSED',
            'purpose': 'Application runtime and HTTPS ingress' if role == 'APP' else 'Database engine and isolated application database',
            'package_source': None, 'package_versions': None,
            'paths': {'configuration': None, 'data': None, 'release': None},
            'ports': {'proposed_tcp': ports, 'bind_addresses': None, 'approved': False},
            'account': None, 'service_unit': None,
            'dependencies': ['approved package source and exact versions', 'scoped service account and filesystem ownership'] +
                            (['database connection contract when application requires DB'] if role == 'APP' else ['backup and application/database compatibility policy']),
            'required_privileges': ['scoped package installation', 'scoped account/directory/configuration management', 'scoped service management'],
            'preconditions': ['verified target and fresh target preflight', 'review existing services/ports; no automatic takeover'],
            'postconditions': ['independent version/configuration/ownership validation', 'service health and listener binding match approved contract'],
        })
    decisions = ['target identity, provider instance, generation and verified hostkey',
                 'supported OS/kernel/version compatibility',
                 'installer release and separate application release',
                 'package sources, trust, exact versions and compatibility',
                 'configuration/data/release paths and disk mount scope',
                 'accounts, bind addresses, approved ports and service units',
                 'least-privilege operator actions and authentication',
                 'swap size, persistence and approved resource policy',
                 'backup, rollback and app/DB compatibility',
                 'freshness policy and independent validator']
    missing = [name for name in ('os', 'kernel', 'cpu', 'memory', 'disk', 'services',
                                'ssh_sockets', 'ports', 'ssh_binary', 'sudo_binary', 'identity')
               if evidence['observations'].get(name) is None or name in evidence['errors']]
    return {
        'schema_version': 1, 'kind': 'installation-review-contract',
        'profile': profile, 'scope': 'offline-read-only-plan',
        'preflight_status': evidence['status'],
        'status': 'FAIL' if evidence['status'] == 'FAIL' else 'WARN',
        'installation_authorized': False, 'executable': False,
        'completeness': 'OPEN', 'missing_observations': missing,
        'evidence_binding': {'sha256': digest, 'timestamp_utc': evidence['timestamp_utc'],
                             'scope': evidence['scope'], 'authenticity_verified': False},
        'target': {'identity': None, 'generation': None, 'hostkey': None,
                   'observed_target_verified': False},
        'releases': {'installer': None, 'application': None},
        'policy': evidence['policy'], 'components': components,
        'open_decisions': [{'decision': item, 'status': 'OPEN'} for item in decisions],
        'stop_conditions': ['preflight FAIL', 'missing critical inventory or unresolved decisions',
                            'target identity/generation drift or stale evidence',
                            'unexpected service/port/path conflict', 'validation failure or uncertain partial effects'],
        'operator_steps': ['resolve and review all OPEN decisions', 'verify target identity and collect fresh PRE evidence',
                           'confirm recoverable snapshot and evidence storage outside target',
                           'obtain separate human GO for the exact target/release/plan and scoped privileges'],
        'recovery': {'automatic_retry': False, 'automatic_restore': False,
                     'on_interruption': 'Stop; preserve sanitized evidence; inspect actual effects and obtain recovery review',
                     'acceptance_sequence': ['PRE1', 'installation1', 'independent POST1',
                                             'user snapshotrestore via TransIP', 'renewed identity verification',
                                             'PRE2', 'installation2', 'independent POST2', 'cross-run comparison on APP-O'],
                     'normalization': 'Only explicitly approved volatile fields; preserve security/configuration/versions/permissions',
                     'proven': False},
    }
