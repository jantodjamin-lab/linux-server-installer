"""Offline checks prevent false cold-boot claims; no real guest/host effects."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('e2e_guest_test',BASE/'tools/e2e-guest.py')
guest=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guest)


class SudoPromptSafety(unittest.TestCase):
    def test_documented_classic_and_rs_prompts_with_echo_disabled(self):
        self.assertTrue(guest.sudo_password_prompt(b'[sudo] password for fixture: ',False))
        self.assertTrue(guest.sudo_password_prompt(b'[sudo: authenticate] Password: ',False))
        self.assertTrue(guest.sudo_password_prompt(b'\x1b[1m[sudo: authenticate] Password:\x1b[0m ',False))

    def test_echo_enabled_or_unknown_prompt_never_receives_secret(self):
        self.assertFalse(guest.sudo_password_prompt(b'[sudo] password for fixture: ',True))
        self.assertFalse(guest.sudo_password_prompt(b'[sudo: authenticate] Password: ',True))
        self.assertFalse(guest.sudo_password_prompt(b'Password: ',False))
        self.assertFalse(guest.sudo_password_prompt(b'[sudo: authenticate] Password: \nother output',False))


class ColdBootEvidence(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='installer-coldboot-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.path('/proc/sys/kernel/random/boot_id').write_text('second-boot\n')
        self.path('/etc/fstab').write_text('/e2e-existing-swap none swap sw 0 0\n')
        self.path('/var/lib/universal-linux-installer').mkdir(parents=True,exist_ok=True)
        self.marker=self.path('/var/lib/universal-linux-installer/e2e-reboot-pending.json')
        self.result={'status':'PASS','installation_status':'PASS','profile':'DB','swap_initial_gib':2,
                     'journal_events':18,'coldboot':False,'fault_event':0}
        self.pending={'result':self.result,'boot_id':'first-boot','external_sockets':['0.0.0.0:22']}
        self.marker.write_text(json.dumps(self.pending))
        self.swap={'/e2e-existing-swap':2*2**30,'/owned-swap':2*2**30}
        self.sockets='LISTEN 0 128 127.0.0.1:5432 0.0.0.0:*\nLISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n'

    def path(self,value):
        path=self.root/str(value).lstrip('/')
        path.parent.mkdir(parents=True,exist_ok=True)
        return path

    def checked(self,argv):
        if argv[0]=='/usr/bin/ss':return self.sockets
        if argv[0]=='/usr/sbin/runuser':return 'scram-sha-256|localhost\n'
        raise AssertionError('unexpected external command: '+argv[0])

    def proof(self):
        with patch.object(guest,'Path',side_effect=self.path), patch.object(guest,'checked',side_effect=self.checked), \
             patch('swap.active_swap',return_value=self.swap), patch.object(guest.subprocess,'run',return_value=SimpleNamespace(returncode=0)), \
             contextlib.redirect_stdout(io.StringIO()):
            guest.postboot_proof(self.marker)

    def test_actual_second_boot_keeps_first_event_count_and_consumes_marker(self):
        self.proof()
        result=json.loads(self.path('/var/lib/universal-linux-installer/e2e-result.json').read_text())
        self.assertTrue(result['coldboot'])
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['journal_events'],18)
        self.assertEqual(result['postboot_swap_bytes'],4*2**30)
        self.assertEqual((result['boot_id_before'],result['boot_id_after']),('first-boot','second-boot'))
        self.assertFalse(self.marker.exists())

    def test_same_kernel_boot_cannot_be_reported_as_coldboot(self):
        self.path('/proc/sys/kernel/random/boot_id').write_text('first-boot\n')
        with self.assertRaisesRegex(AssertionError,'same kernel boot'):self.proof()
        self.assertTrue(self.marker.exists())
        self.assertFalse(self.path('/var/lib/universal-linux-installer/e2e-result.json').exists())

    def test_missing_existing_swap_refuses_even_if_total_target_is_met(self):
        self.swap={'/owned-swap':4*2**30}
        with self.assertRaisesRegex(AssertionError,'fixture swap'):self.proof()

    def test_insufficient_active_swap_cannot_be_reported_as_persistent(self):
        self.swap={'/e2e-existing-swap':2*2**30,'/owned-swap':2*2**30-4096}
        with self.assertRaisesRegex(AssertionError,'persistent swap absent'):self.proof()

    def test_known_external_postgres_still_must_bind_loopback(self):
        self.pending['external_sockets'].append('0.0.0.0:5432')
        self.marker.write_text(json.dumps(self.pending))
        self.sockets+='LISTEN 0 128 0.0.0.0:5432 0.0.0.0:*\n'
        with self.assertRaises(AssertionError):self.proof()

    def test_failed_initial_validation_cannot_be_promoted_to_pass(self):
        self.pending['result']['status']='FAIL'
        self.marker.write_text(json.dumps(self.pending))
        with self.assertRaisesRegex(AssertionError,'initial validation'):self.proof()

    def test_remaining_package_start_guard_blocks_pass(self):
        self.path('/usr/sbin/policy-rc.d').write_text('fixture guard\n')
        with self.assertRaises(AssertionError):self.proof()


if __name__=='__main__':unittest.main()
