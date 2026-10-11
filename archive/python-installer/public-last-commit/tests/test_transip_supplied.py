"""Offline regressions reconstructed from operator-supplied source fields.

This is not a captured provider file, signed metadata or cloud-init template.
GnuPG/APT outputs are injected; these tests make no network or target changes.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_rc4 import audit_tree, Probe
from core import inventory, plan, PROFILES
from index_age import index_age
from node import ALLOWED_KEYS, ARCHIVE_KEY, universe_source, verify_releases
from sources import KEYRING, MirrorError, read_sources, release_paths


URI = 'https://mirror.transip.net/ubuntu/ubuntu/'
SUITES = ['resolute', 'resolute-security', 'resolute-updates']
COMPONENTS = ['main', 'multiverse', 'restricted', 'universe']
SOURCE = ('Types: deb\nURIs: '+URI+'\n'
          'Suites: resolute resolute-updates resolute-security\n'
          'Components: main universe restricted multiverse\n'
          'Signed-By: '+KEYRING+'\n')


def tree(root):
    audit_tree(root)
    (root/'etc/apt/sources.list.d/ubuntu.sources').write_text(SOURCE)
    (root/'etc/os-release').write_text(
        'ID=ubuntu\nVERSION_ID="26.04"\nVERSION="26.04.1 LTS (Resolute Raccoon)"\n'
        'VERSION_CODENAME=resolute\n')
    for path in (root/'var/lib/apt/lists').glob('*InRelease'):
        path.unlink()
    for name in release_paths(root, [URI]):
        path = root/'var/lib/apt/lists'/name
        path.write_text(
            '# Unsigned mock metadata: signature command is injected.\n')
        path.chmod(0o644)


def inspect(root, probe, mirrors=()):
    usage = shutil._ntuple_diskusage(120*10**9, 26*10**9, 94*10**9)
    with patch('core.platform.system', return_value='Linux'), \
         patch('core.platform.machine', return_value='x86_64'), \
         patch('core.os.cpu_count', return_value=1), \
         patch('core.shutil.disk_usage', return_value=usage):
        return inventory(root, probe, allow_mirrors=mirrors)


def state(root):
    return {str(path.relative_to(root)): (
        path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns,
        path.read_bytes() if path.is_file() else None)
        for path in [root, *root.rglob('*')]}


class SuppliedTransIPTests(unittest.TestCase):
    def test_exact_fields_and_mirror_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root)
            with self.assertRaises(MirrorError) as error:
                read_sources(root)
            self.assertEqual(error.exception.host, 'mirror.transip.net')
            self.assertEqual(error.exception.remedy, 'rerun with --allow-mirror '+URI)
            entry = read_sources(root, [URI])['entries'][0]
            self.assertEqual(entry['uris'], [URI])
            self.assertEqual(entry['suites'], SUITES)
            self.assertEqual(entry['components'], COMPONENTS)
            self.assertEqual(entry['types'], ['deb'])
            self.assertEqual(entry['signed_by'], KEYRING)
            for other in ('https://mirror.transip.net/ubuntu/',
                          'https://mirror.transip.net/ubuntu/ubuntu',
                          'http://mirror.transip.net/ubuntu/ubuntu/',
                          'https://other.example/ubuntu/ubuntu/'):
                with self.subTest(other=other), self.assertRaises(MirrorError):
                    read_sources(root, [other])

    def test_canonical_list_prefix_and_universe_signed_by(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root)
            expected = {'mirror.transip.net_ubuntu_ubuntu_dists_'+suite+'_InRelease':
                        suite for suite in SUITES}
            self.assertEqual(release_paths(root, [URI]), expected)
            probe = Probe(); self.assertTrue(verify_releases(root, probe, [URI]))
            self.assertEqual(len(probe.calls), 3)
            extension = universe_source('x86_64', root=root, allow_mirrors=[URI])
            self.assertEqual(extension.count('URIs: '+URI), 3)
            self.assertEqual(extension.count('Signed-By: '+KEYRING+'\n'), 3)
            self.assertNotIn(KEYRING+' '+ARCHIVE_KEY, extension)

    def test_rejected_mirror_does_not_cascade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root); probe = Probe()
            data = inspect(root, probe)
            self.assertFalse(data['source_policy_valid'])
            self.assertTrue(data['key_valid'])
            self.assertEqual(data['source_metadata'], 'verified-cached')
            self.assertTrue(data['package_candidates']['nodejs'])
            self.assertTrue(data['package_candidates']['npm'])
            for profile in PROFILES:
                checks = {item['id']: item['status'] for item in plan(profile, data)['checks']}
                self.assertEqual(checks['source-policy'], 'FAIL')
                self.assertEqual(checks['archive-key'], 'PASS')
                self.assertEqual(checks['cached-signatures'], 'PASS')

    def test_all_profiles_point_release_audit_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root); before = state(root)
            data = inspect(root, Probe(), [URI])
            self.assertEqual(data['os'], {'ID': 'ubuntu', 'VERSION_ID': '26.04'})
            for profile in PROFILES:
                report = plan(profile, data)
                self.assertFalse(report['failures'])
                self.assertEqual(report['status'], 'WARN')
            self.assertEqual(before, state(root))

    def test_stale_dates_and_stamp_warn_without_rejecting_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root); now = datetime.now(timezone.utc)
            for index, name in enumerate(release_paths(root, [URI])):
                path = root/'var/lib/apt/lists'/name
                old = now-timedelta(days=17 if index == 0 else 14)
                path.write_text('Date: '+old.strftime('%a, %d %b %Y %H:%M:%S +0000')+'\n')
                os.utime(path, (old.timestamp(), old.timestamp()))
            periodic = root/'var/lib/apt/periodic'; periodic.mkdir()
            stamp = periodic/'update-success-stamp'; stamp.touch()
            fresh = now-timedelta(days=1)
            os.utime(stamp, (fresh.timestamp(), fresh.timestamp()))
            before = state(root)
            age = index_age(root, [URI], now)
            self.assertEqual(age['status'], 'WARN')
            self.assertEqual(age['age_days'], 17.0)
            self.assertEqual(age['update_success_stamp_age_days'], 1.0)
            data = inspect(root, Probe(), [URI])
            self.assertTrue(data['sources_valid'])
            self.assertFalse(plan('APP+DB', data)['failures'])
            self.assertEqual(before, state(root))

    def test_wrong_key_and_signature_are_independent_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root); probe = Probe()
            def wrong_key(argv):
                output = probe(argv)
                if Path(argv[0]).name == 'gpg':
                    return output.replace(ARCHIVE_KEY, '1'*40)
                return output
            data = inspect(root, wrong_key, [URI])
            self.assertFalse(data['key_valid'])
            self.assertEqual(data['source_metadata'], 'verified-cached')
            def wrong_signature(argv):
                output = probe(argv)
                if Path(argv[0]).name == 'gpgv':
                    return output.replace(ARCHIVE_KEY, '2'*40)
                return output
            data = inspect(root, wrong_signature, [URI])
            self.assertTrue(data['key_valid'])
            self.assertEqual(data['source_metadata'], 'failed')
            self.assertTrue(data['package_candidates']['nodejs'])

    def test_full_primary_fingerprints_accept_supplied_key_id_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root); probe = Probe()
            self.assertEqual({fingerprint[-16:] for fingerprint in ALLOWED_KEYS},
                             {'3B4FE6ACC0B21F32', 'D94AA3F0EFE21092', '871920D1991BC93C'})
            def all_keys(argv):
                if Path(argv[0]).name == 'gpg':
                    return ''.join('pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::'+key+':\n'
                                   for key in sorted(ALLOWED_KEYS))
                return probe(argv)
            self.assertTrue(inspect(root, all_keys, [URI])['key_valid'])

    def test_wrong_signed_by_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); tree(root)
            (root/'etc/apt/sources.list.d/ubuntu.sources').write_text(
                SOURCE.replace(KEYRING, '/usr/share/keyrings/provider.gpg'))
            with self.assertRaisesRegex(ValueError, 'apt-source-keyring'):
                read_sources(root, [URI])


if __name__ == '__main__':
    unittest.main()
