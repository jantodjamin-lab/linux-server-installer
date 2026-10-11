> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# RC3 implementation and operator limits

Default audit/dry-run performs inventory and planning only: no source write,
APT update/install, cache write, swap allocation, fstab write or activation.
Python bytecode writes and apt-cache disk caches are disabled.

## Explicit Node.js source

RC3 selects Ubuntu 26.04 universe, Node 22 LTS (at least 22.12 for Angular 20)
and npm 9. This is an explicit supported LTS line, not latest-version discovery.
No NodeSource, PPA, vendor setup script or alternate version fallback is used.
The official catalog lists Node 22.22.1 and npm 9.2.0; these catalog versions are
not shipped as a fabricated target lock. Installed/cache availability is verified
again on the eventual target. Catalog entries alone cannot prove an installable
closure; missing npm dependencies are a safe installation stop.

The installed Ubuntu keyring must be a regular, trusted-owner file without
writable group/world permissions. Primary fingerprints must match Canonical's
published 2012 archive/CD and 2018 archive keys; the 2018 archive key is required.
Keys are inspected without importing or writing a user trust database.
Unknown/revoked/expired keys are refused. Fresh InRelease signatures are independently
checked with gpgv and must bind to the 2018 archive fingerprint. APT checks
metadata expiry and the signed checksum chain to every downloaded package.
Any refresh failure (including unavailable repositories) stops all later steps.
No unauthenticated, weak or downgraded repository policy is accepted.

Every active source requires explicit Signed-By, supported resolute suites and
approved Ubuntu archive/security/ports URLs. Legacy globally trusted sources
and unreviewed source options are refused. If universe is entirely absent,
execution creates one owned deb822 source with archive fingerprint binding.
A partial universe configuration stops for source review, avoiding duplicate
repository targets. Existing source files are preserved. Installing requires
preinstalled gpg, gpgv, util-linux and a reviewed schema-2 exact APT/npm lock,
including all new/changed dependencies. Schema-3 plans bind the source provider,
architecture, swap action and profile. Regenerate RC2 plans for RC3.

## Swap and recovery

Target is at least 4 GiB active swap for all three test profiles. Existing active
files/partitions count towards the target and are never disabled, resized or
removed. Only the deficit plus one header page is allocated; 4 GiB or more means
no new file and no fstab edit. Allocation writes real zeros, avoiding holes and
copy-on-write filesystem assumptions. Only writable ext4 and XFS are accepted.
Btrfs, overlay, tmpfs, NFS and unknown filesystems stop if a deficit exists.

The fixed owned path is /var/lib/universal-linux-installer/swap/swapfile. Exclusive
creation, 0600 permissions, inode/device binding, single-link checks, allocation
checks, and private checksummed fsync checkpoints protect recovery. Unknown files
or permission drift stop. A crash between exclusive file creation and its first
checkpoint deliberately requires manual investigation; it is never adopted.
An interrupted allocation resumes only its own partial file, and an interrupted
formatter checks the swap signature before retry. Never run two operator actions
against the same host or manually edit fstab while execution is active.

fstab edits preserve existing entries and refuse conflicting/duplicate references.
An atomic fsync append is followed by activation and active-capacity validation.
Failure preserves the owned file, fstab evidence and existing swap; no rollback,
truncate, swapoff, existing-file replacement or automatic removal is performed.
Unknown effects require the outer journal's --recovery-reviewed operator gate.
Reports include existing_bytes, deficit_bytes, required_bytes and active_bytes.
An externally lost existing swap may prevent the target from being reached;
execution stops without resizing an existing file.

## Capacity

These are disposable-test admission minima, not reliable-runtime promises.
Physical RAM is checked separately from swap and cannot be compensated by it.

| Profile | Minimum CPU / RAM | Recommended CPU / RAM | Disk reserve after swap | Swap target |
|---|---|---|---|---|
| APP | 1 / 843 MiB | 2 / 2048 MiB | 10 GiB | 4 GiB |
| DB | 1 / 843 MiB | 2 / 2048 MiB | 20 GiB | 4 GiB |
| APP+DB | 1 / 843 MiB | 4 / 4096 MiB | 30 GiB | 4 GiB |

Ubuntu 26.04 (including point releases reported as VERSION_ID=26.04), x86_64 or
aarch64, trusted sources, service manager, package inventory and required service
inventory are checked. Packages absent from the current read-only cache are
reported as warnings; execution refuses missing exact versions or dependencies.
Required services are Nginx for APP, PostgreSQL for DB and both for APP+DB.
Their actual operation and package versions are checked after installation.
At 843 MiB and one CPU, APP+DB may pass the technical test admission minimum but
is explicitly insufficient for reliable builds/runtime. More swap cannot change
this assessment. Build-pressure/OOM and runtime performance remain unvalidated.

## Offline evidence and later acceptance

Pure tests calculate exact 0→4 GiB, 2→4 GiB and >=4 GiB transitions. Recovery and
filesystem tests allocate proportional MiB-sized files in temporary directories,
with simulated formatting/activation; no real swap is created or activated.
Tests cover bad keys/signatures, unavailable packages, strict dependencies,
space/filesystem/permissions, interrupted allocation/formatting/activation,
idempotence, fstab conflicts, all profiles, CLI audit/dry-run and journal recovery.
A gpgv rejection test invokes the real verifier on malformed local fixture bytes.
No authentic live repository transaction or full-size live swap acceptance is
claimed. Full package closure, VM power-loss recovery, RAM/build load and both
architectures require later, separately authorized disposable-target validation.

The release workflow runs offline tests, scans the explicit public allowlist,
rebuilds byte-identically, verifies pinned archive SHA256, and creates only
v1.0.0-rc.3 as a prerelease. It cannot install target software or access any server.
