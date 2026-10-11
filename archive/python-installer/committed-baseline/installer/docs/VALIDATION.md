> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Three-iteration validation record

All validation used Python stdlib and disposable local fixtures. No installer
commands were run on hosts. No live updates, package installs, SSH, reboots,
service changes or archive changes were performed.

| Iteration | Tests | Delivery assessment |
| --- | --- | --- |
| 1 | 3 installer + 66 existing PASS | WARN: audit foundation; package inventory and profile policy implemented |
| 2 | 7 installer + 66 existing PASS | WARN: injectable offline engine; full live installation incomplete |
| 3 | 15 installer + 66 existing PASS | WARN: development RC; no production/live acceptance |

Covered: all three profiles, deterministic plans, unsupported OS/resources,
source rejection, checksum tampering, artifact traversal/symlinks, repeat run,
interrupted action and explicit recovery, version conflict, failed validator,
reboot stop, checkpoint mismatch/corruption/symlink, rejected remote/live CLI,
AST parse and shell syntax. Release rebuild and SHA256 checks are separately
performed before the third commit. Existing 66 tests remain unchanged.

Limitations: fake package bytes, no actual deb/npm extraction or dependency
resolution, no signed apt metadata verification, no system update implementation,
no live Nginx/PostgreSQL health/config validation, no concurrency/host identity
proof, no power-loss test, no authentication of local checkpoint or bundle hash.
Optional Codex is represented in manifest policy but has no live installer.
A complete Universal Linux Installer V1.0 is therefore not delivered. The RC
preserves the fail-closed execution boundary and makes remaining work explicit.
