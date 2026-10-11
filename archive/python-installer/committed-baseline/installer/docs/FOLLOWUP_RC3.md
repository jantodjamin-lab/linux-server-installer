> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Private RC3 development record

Authorized scope: private feature/universal-linux-installer-v1, generic public
release-candidate and prerelease v1.0.0-rc.3. No APP-O package/service/swap effects,
TEST-O access, production work, historical repository changes, force push, main
merge or stable release. Baseline private branch was
8c50569dcb6e5f0b025a1881b0ed6493273628bf. All 19 RC2 archive source blobs match
the branch's installer blobs. No applicable AGENTS.md exists in its recursive tree.

RC3 implements Ubuntu universe Node 22 LTS/npm 9 with Canonical fingerprint and
independent InRelease signature verification, exact package availability and full
pinned dependency closure; deficit-only 4 GiB swap with filesystem/disk/permission
checks, atomic fstab edits, ownership and recovery checkpoints; profile capacity
inventory with RAM independent of swap and explicit APP+DB reliability warnings.

54 offline tests PASS, including standalone extracted tests. Real gpgv rejects
malformed local fixture data; APT/npm/format/swapon effects use command doubles.
Exact GiB swap arithmetic plus proportional MiB temporary allocation/recovery
avoid real host swap. Two builds match byte-for-byte. All release checksums pass.
Source allowlist/secret patterns, Python AST and POSIX syntax pass. Parent app
regressions were not rerun; application code is outside the patch.

Archive SHA256: 7db205704a4d5adfe18d06b47c824e70767484534c3d848a436340fb58b1df6c.
Publication must be independently confirmed after pushing. Local git/gh cannot
reach GitHub (DNS unavailable; gh auth check fails); authenticated connector Git
object/ref operations and a pinned public GitHub Actions prerelease workflow are
used instead. The workflow runs offline acceptance and fails on any checksum
mismatch; it has no server credentials and no target connection commands.

TEST-O: NO-GO pending separate installation GO, target-specific authenticated
package/dependency lock and fresh read-only audit. Ubuntu catalog npm metadata
has unavailable dependency links, so the exact target closure must resolve or
execution safely stops. At 843 MiB / one CPU, APP+DB remains insufficient for
reliable builds/runtime even after adding swap. Node 22 is the explicit LTS line,
not an automatic latest release. Universe security update cadence, actual root
package scripts, full-size swap/power-loss behavior and architecture differences
remain live acceptance risks.

## Confirmed delivery

Private implementation commit: 245bce90c5c7607197eb1df2f3c9f2a501964675.
Public release commit: cc2dda4464599f6def8765fc63fa452d6d532ca3.
Public anonymous-download verification commit:
7224b0dd9214afdb351909b5958ff2cee48b6b92.

Release: https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-rc.3
Release metadata confirms prerelease=true, draft=false, correct release commit.
All five GitHub asset digests match local files, including the pinned archive.
Release/offline build workflow: PASS
https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38061963354
Anonymous curl download + SHA256SUMS + pinned archive + extracted 54 tests: PASS
https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38062170855
Anonymous downloads execute on an isolated GitHub-hosted runner, with no user
credentials or target access; local APP-O network/DNS remains unavailable.

A local shallow sparse Git checkout was reconstructed from verified Git object
hashes through the connector. The working tree is clean, includes installer
only, and local HEAD matched the private feature ref after the implementation
push. Final documentation commit receives the same HEAD/ref verification.
The private base tree retains all 85 entries outside installer unchanged. Public
history extends only the existing generic installer root, not private history.

Iteration 1: PASS offline; WARN target npm dependency closure / live acceptance.
Iteration 2: PASS offline; WARN real swap/full-size/power-loss acceptance.
Iteration 3: PASS; physical-RAM reliability warnings remain explicit.
Iteration 4: PASS; 54 tests in source, standalone archive, sparse checkout and
GitHub hosted source/extracted/downloaded acceptance. No parent-app tests rerun.
Iteration 5: PASS; source refs, prerelease, all release assets and anonymous
artifact verification confirmed. No stable release, force push or main merge.

TEST-O remains NO-GO for actual installation until separate GO and authenticated
full target-specific closure. 843 MiB / one CPU APP+DB is not a reliable build or
runtime profile, regardless of 4 GiB swap. Neither TEST-O nor production was
contacted or modified during this iteration.
