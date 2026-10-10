# Offline acceptance — v1.0.0-rc.2

**NIET LIVE GEVALIDEERD / NOT LIVE VALIDATED. NO GO for live installation.**

The five development phases are foundation/source policy, local implementation,
offline acceptance, clean public distribution and release/download verification.
No separate five-phase contract was present in the checkout; this is the explicit
operational mapping used for this continuation.

Code acceptance covers all APP/DB/APP+DB workflows; optional development Codex;
pinned update opt-in; deterministic plan hashes; unsupported OS/resources;
exact package and dependency versions; safe source allowlist; npm integrity;
Nginx and PostgreSQL configuration; service-start guard; idempotent repeat;
checkpoint reopening; uncertain-step review; process lock; failure journal;
version/configuration drift; checksum corruption; symlink/path rejection;
credential-safe errors; and refusal without explicit execution consent.

Tests use temporary directories and command doubles. They exercise LocalRunner
itself, not only a substitute installation engine. No apt/npm install, service
change, database action or reboot is executed on the development machine.
The old offline bundle Engine API remains for regression tests; the CLI now uses
the schema-2 workflow and LocalRunner. No compatibility acceptance is inferred
from the old Engine's fake package bytes.

Release acceptance additionally requires deterministic byte-identical rebuild,
SHA256 verification, standalone extracted tests, an explicit public file allowlist,
secret/internal-data scan, new public Git history and verified anonymous download.
Machine-specific locks, journal data and audit output are excluded from releases.

Remaining live risks: target-specific signed package closure, actual Ubuntu
maintainer scripts and package-created cluster layout, npm native optional
packages with scripts disabled, memory/disk under build load, interrupted real
package operations, power loss, architecture differences and package/service
compatibility. Actual root/filesystem isolation cannot be proven by command
fixtures. A compromised root/keyring/apt configuration is outside the trust model.
A separate disposable target run and owner approval are mandatory before live GO.
A stable v1.0.0 release must wait for live validation.

## Recorded offline result

35 installer tests PASS; 66 parent-project regression tests PASS (unchanged).
The standalone extracted RC runs the same 35 installer tests successfully.
Two builds are byte-identical; every release checksum verifies. Static Python
parsing and POSIX shell syntax checks pass. The host lock spans checkpoint
paths; a subprocess exiting abruptly retains its durable pending checkpoint.
No actual host package or service mutation was used to obtain these results.
