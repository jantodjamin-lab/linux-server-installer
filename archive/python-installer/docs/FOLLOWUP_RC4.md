> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# RC4 private development evidence

Only code development and offline tests were performed on APP-O. TEST-O and
production were not accessed. The historical repository and main are untouched.

Concrete RC3 command defects: unsupported swapon --json, GnuPG --show-keys
requiring a missing home, and conflicting Signed-By when adding universe.
The exact TEST-O configuration was not inspected in this iteration.

81 offline tests PASS in source and standalone release, including all profiles,
no-write audit snapshots, 0/2/>=4 GiB swap arithmetic, recoverable interruptions,
rights/disk failures, source signatures, Node/npm metadata and dependency
preflight before swap, interactive sudo authorization safeguards with mocks.
Read-only real GnuPG, isolated apt-cache parsing and swapon supported-option
checks complement command doubles. No apt refresh/install or live swap/sudo
execution was performed.

Deterministic rebuild, generic allowlist, internal-data/secret scans, syntax and
archive member checks PASS. Archive SHA256: b44702a5ab65c77eb9ec72671512c5e5116a4cdbbf8da1b4ee5c4bd209d68a9b.

NO-GO for TEST-O installation. GO only for a separately authorized read-only
RC4 audit. 843 MiB RAM remains insufficient for reliable APP+DB builds/runtime.
Actual signed target dependency closure, interactive terminal authorization and
full-size swap/recovery remain live acceptance requirements.

## Confirmed delivery

Private implementation: cd12aba388ec80943dcc4b8dbaf0ac851f2629fc.
Public release commit: 30fe54e5a586d1029d92277f53d7b459b72204d9.
Release: https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-rc.4
Prerelease=true, draft=false; tag points to the release commit.
All five published asset SHA256 digests match the local files.
Source and extracted 81 tests, deterministic rebuild, and anonymous HTTPS
release download/checksum/extracted acceptance: PASS on GitHub-hosted runner.
Workflow: https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38085461201

Private outside-installer Git tree entries: all 85 unchanged. Public tree scope
checked; no private environment files/history exported. Local sparse working tree
clean and HEAD matched the private feature ref after implementation publication.
This delivery record receives the same final HEAD/ref check. No force-push,
main merge, stable release, historical repository or target changes occurred.

PASS: all seven requested RC4 code/offline validation areas and prerelease delivery.
WARN: live target capacity/dependency closure, actual sudo terminal flow and
full-size swap/power-loss validation. NO-GO for target installation remains.
