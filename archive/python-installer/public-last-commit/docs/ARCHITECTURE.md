> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; do not use these commands for installation.

# Architecture and acceptance

Runtime is Python 3.11+ stdlib and POSIX sh. Privileged package/security tools are
Ubuntu target prerequisites verified by audit; npm locks are prepared in CI.

## Authorization and steps

Read-only audit probes independently: platform/capacity, active swap/storage,
source policy, Canonical key fingerprints, cached gpgv signatures, index dates,
APT candidates/dependencies and systemd/listeners. A mirror refusal must not
suppress other probes. Public URLs are exposed only after credential-free parsing.

Apply hashes schema-5 bounded intent before root directory/source/index changes.
Acknowledgements precede typed INSTALL confirmation. A target lock covers
preparation and execution. Preparation journal: cloud-init (idempotent), owned
universe extension (effectful), refresh+resolver+private outputs (idempotent).
Resolved workflow: sources(effectful), apt-refresh(idempotent),
package-preflight(readonly), swap(effectful), exact package transaction(effectful),
app-config/db-config/npm(effectful), final validators/guard removal(effectful).
The same validate_lock/build_workflow/package_preflight path serves manual and
automatically generated locks. No separate weaker executor exists.

Resolver simulates profile+ca-certificates without pins, obtains actual candidate
versions, simulates candidate roots and includes every Inst dependency. Installed
version changes go in updates; Remv and downgrades fail. The full closure is
validated against signed metadata and exact simulation before ANY swap/package
installation. Target locks are never fabricated or distributed universally.
An updated candidate disappearing between solve/execute produces a safe stop.
Created-at TTL is 2h; hand-edited old plans are refused.

## Journal and failures

Journal binding, checksum, atomic fsync, O_NOFOLLOW and host/process locks protect
private state against accidental drift and concurrent operators. This is not an
authenticated sandbox against root. Pending is persisted BEFORE effects. On error,
FAILED stores only known code/step/command/exit; private redacted 0600 logs hold
4KiB stderr maximum. AUTO_CLEARED permits readonly/idempotent retry, including
SIGKILL before FAILED; effectful pending requires independent recovery review.
No rollback, deletion of effects or silent adoption of another plan is implemented.
Once completed, each step is revalidated; drift/manual reboot stops execution.

## Swap

Target: at least 4GiB active capacity; allocate only deficit + header page, real
zeros (not holes), ext4/XFS only. Existing devices never change. Exclusive owned
0600 swapfile is inode/device/single-link bound to checksummed checkpoints.
Stages creating/allocated/formatted/persistent/active use fsync. Unknown existing
files, symlinks, permissions drift, fstab conflicts and insufficient reserve fail.
Formatting/activation is revalidated; interrupted owned partial allocation can
resume, unknown crash-before-checkpoint requires manual investigation. Atomic
fstab persistence preserves all existing rows. No swapoff/rollback is used.

## Three acceptance layers

1. Offline units/regressions: real temp files/fsync/permissions, injected command
   doubles, actual key and isolated apt-cache parser checks. Baseline RC4: 81 PASS;
   obsolete engine tests are removed and used behavior stays covered by Journal
   and actual LocalRunner tests. Test count alone is not real-tool compatibility.
2. Disposable ubuntu:26.04 container: real gpg/gpgv/swapon, archive refresh,
   all-profile exact closure and Ubuntu npm9/SRI ci. Capacity/systemd/swap admission
   is excluded explicitly. amd64 required; QEMU arm64 best effort with separate
   status. Output /tmp/rc5-layer2.json and console logs are retained in CI.
3. Disposable local QEMU VM (KVM or TCG) with systemd: tools/e2e-vm.sh creates a fresh
   writable overlay and cloud-init NoCloud seed; uses serial and a readonly
   installer seed, NEVER SSH or any remote host. Requires preinstalled qemu tools,
   cloud-localds, tar, curl and local trusted Ubuntu 26.04 cloud image.
   No host packages are installed by the harness. Cases: profile clean+repeat,
   0/2/4GiB swap, minimum CPU/RAM, dpkg contention, kill-after-journal-event recovery.
   Guest uploads nothing; logs/journals/diagnostics stay in its disk and serial log.
   A local 9p artifact directory receives guest logs after shutdown.
   Canonical image SHA256SUMS signatures are pinned and verified by CI.
   The provider source file reconstructs supplied fields; it is not a captured file.

Use `sh tools/e2e-vm.sh APP` for smoke; `RC5_E2E_MATRIX=1 sh tools/e2e-vm.sh APP`
for the scenarios, repeated for DB and APP+DB. Set RC5_E2E_IMAGE to a locally
verified cloud image and RC5_E2E_IMAGE_SHA256 to its trusted SHA256. The harness
refuses missing tools/image/hash rather than downloading/executing an unverified
image. It never claims live_validated; owner acceptance is a separate decision.
Production/real server installation remains outside scope.

Cloud-init installs only guest test prerequisites before the acceptance service;
these fixture-setup operations are separate from installer authorization.
At QEMU -m843, reserved memory can make actual MemTotal <843MiB: that case proves
correct read-only refusal and reports apply_executed=false, not a swap/apply PASS.
The exact 843MiB admission boundary is also covered by unit fixtures. VM listeners
must preserve the initial non-loopback set (including unchanged cloud-image SSH);
new service listeners are loopback only. The harness never connects to SSH.
Fault event count is taken from the baseline's actual journal, not guessed.
