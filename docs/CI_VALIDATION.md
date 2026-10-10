# Isolated acceptance evidence

No SSH, real target connection or development host prerequisite installation is used. CI installs
QEMU prerequisites only on disposable GitHub-hosted Linux runners. The helper
`tools/ci-vm.sh` refuses execution outside that environment. Guest changes are
restricted to fresh local QEMU overlays and cloud-init fixture setup.

## Commands

Publication requires both `vm_security=true` and `vm_faults=true`, with every
required job successful. The default validation run cannot publish a release.

Normal push validation includes offline unit tests, real Ubuntu package closure
checks and a fresh systemd VM smoke scenario for APP, DB and APP+DB. To request
bounded swap/admission/lock scenarios and exhaustive journal-event interruptions:

```sh
gh workflow run release.yml --repo jantodjamin-lab/linux-server-installer \
  --ref release-candidate -f publish=false -f vm_security=true -f vm_faults=true
```

`vm_security=true` launches separate fresh-VM jobs per profile for existing
2 GiB and 4+ GiB swap, 843 MiB and 896 MiB QEMU memory, and real dpkg-lock contention.
Four security jobs may run concurrently after smoke succeeds; each job runs one
scenario, while the fault matrix can start independently from smoke evidence. A VM configured with 843 MiB may have
less than 843 MiB usable MemTotal; that case must refuse installation and records
`apply_executed=false`, rather than pretending that the swap path passed.
The separate 896 MiB fixture requires observed MemTotal >=843 MiB and must
complete the real swap/install/repeat path. Its measured RAM is recorded; it
is never described as an exactly 843 MiB usable-RAM test.

`vm_faults=true` first requires successful smoke evidence. The matrix builder
reads the actual first-run journal-event count per profile, before repeat apply.
Each resulting CI job boots a separate fresh VM and kills the installer after
exactly one event. At most eight fault jobs run concurrently. Read-only/idempotent
pending steps resume without review; effectful pending steps must reject normal
resume and succeed only after explicit review. Failed or missing smoke evidence
cannot generate a matrix. No guessed event count or package version is used.

## Evidence and limits

The image checksum file is verified with `gpgv` against the pinned Canonical
cloud-image signing fingerprint, then the downloaded image hash is checked.
KVM is used when available; otherwise QEMU TCG runs the same real guest kernel
and systemd without hardware acceleration. TCG is slower; timeouts or canceled
jobs are failures/incomplete evidence, never successful validation.

Artifacts contain signed-image status, serial logs, result JSON and private
fixture journals. Result JSON records actual `/etc/os-release`, initial swap,
profile, fault event, sudo authentication evidence and mirror-fixture origin.
The TransIP deb822 fixture uses the exact publicly supplied fields, not a claimed
capture of the original real target file. Guest password-authentication fixtures use
a random in-memory test password delivered to the guest OS account setup; the
installer never receives or stores it, and captured terminal output is checked
for leakage before any evidence is published.

A successful isolated run does not authorize installation on real target. The release
continues to report `live_validated=false` until separate owner acceptance. Scripts
alone provide no VM test result; reports must link the actual CI run/artifacts and
identify every skipped, failed or completed scenario.

## Cold-boot persistence

Smoke and security CI jobs set `RC5_E2E_REBOOT=1`. After successful apply and
repeat validation, the test guest writes a private pending-proof marker and
powers off. The local harness starts the same disposable overlay a second time,
never a replacement image. The enabled fixture service recognizes the marker
and performs read-only checks: a different kernel boot ID, active swap >=4 GiB,
existing fixture swap/fstab preservation, managed services on loopback and no
remaining package-start guard. Only then is `coldboot=true` recorded.

Existing 2/4+ GiB swap is created and added to fstab by fixture setup before the
installer starts; the installer does not take ownership of it. Minimum-resource
refusals do not reboot. Fault jobs omit cold-boot proof to keep the exhaustive
interruption matrix bounded. This is exclusively a test-harness restart, never
an installer-triggered reboot or permission to restart a real target.
