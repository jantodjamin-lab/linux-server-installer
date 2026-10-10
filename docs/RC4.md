# Universal Linux Installer v1.0.0-rc.4

**Prerelease — NOT LIVE VALIDATED.**

RC4 repairs three independently reproduced RC3 defects:

- util-linux swapon does not support --json. Inventory now uses --show --bytes
  --noheadings --raw --output NAME,SIZE. Successful empty output is valid zero swap.
- GnuPG --show-keys with an absent home fails. Inspection now lists the explicit
  installed keyring without creating a home, keybox, lock or trust database.
  Fingerprints remain allowlisted; repository signatures independently require
  the pinned Ubuntu archive signing fingerprint through gpgv.
- Adding universe with a different Signed-By value for an existing URI/suite
  causes an APT conflict. Extension preserves the already validated binding and
  adds only missing suites. A real isolated apt-cache test reproduces the old
  conflict and accepts the repaired configuration without filesystem changes.

These are demonstrated code defects, not a claim that the exact remote target
configuration was inspected. Source inventory accepts explicit trusted legacy
.list and deb822 formats, continuation lines, disabled entries and configured
backports. Unknown sources, insecure options, altered keys/signatures and unsafe
permissions fail with bounded reasons. Missing cached signed metadata or package
candidates is a WARN in audit; it never authorizes installation or a version
fallback. Execution refreshes only approved signed feeds and simulates the full
exact dependency closure before swap or package installation. Node 22.12+ LTS
and npm 9 remain the explicit provider selection.

Zero swap yields PASS inventory and WARN preflight for a 4 GiB deficit. Existing
swap is preserved and only the deficit is added. The owned file requires safe
ext4/XFS storage, disk reserve, mode 0600, controlled fstab persistence, activation
validation and reviewed interruption checkpoints. Audit and dry-run only read
these conditions. All three profiles keep physical RAM separate from swap.
An APP+DB target with 843 MiB RAM meets only the test admission minimum; it lacks
recommended capacity for reliable builds and runtime even with 4 GiB swap.

Audit prints compact PASS/WARN/FAIL rows; --json exposes optional details.
Exit codes: 0 PASS/WARN, 1 FAIL, 2 argument/approval error. No audit source refresh,
sudo, package transaction or swap action occurs.

Explicitly approved execution can use --sudo from a terminal. Sudo itself prompts
for authorization, without password storage, stdin piping or askpass. The child
revalidates the saved schema-4 plan and target. Older plans must be regenerated
and reviewed. Noninteractive execution cannot silently request credentials.

81 offline tests cover all profiles, repeatability, signatures, missing packages,
0/2/at-least-4 GiB swap, disk/rights/fstab failures, interrupted recovery,
source parsing, dependency preflight ordering, compact/JSON audit with unchanged
fixture bytes/modes/mtimes, and mocked sudo authorization/cancellation.
Real public-key and isolated APT parser checks complement command doubles.
No system installation, package update, swap activation, remote connection or
production change was performed. Live terminal sudo authorization, live package
closure, full-size swap and power-loss recovery remain unvalidated.

GO for a separately authorized read-only candidate audit. NO-GO for installation
until a fresh target audit, verified dependency lock, capacity decision and
separate installation approval are obtained. No stable release is implied.
