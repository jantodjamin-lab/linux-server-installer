# Changelog

## 1.0.0-bash.5 (kandidaat, niet gepubliceerd)

- Restore the traceable Bash source (Git `78f8c2c`) as the maintained source of truth; the published bash.4 archive is byte-for-byte reproducible from it.
- One simple menu: 1 APP, 2 DB, 3 APP + DB, 4 Controle (read-only preflight), 0 Stoppen; `5` remains a silent stop alias.
- New read-only preflight (`bash/preflight.sh`) before every confirmation: privileges, swap, free disk, existing Nginx/PostgreSQL and listeners on 80/443/5432. FAIL stops before any question, sudo or write.
- `tools/render-bootstrap.sh` emits `ONE-COMMAND.txt`: one readable line that verifies the pinned bootstrap before execution.
- `tools/release.sh` builds only the executed distribution payload (the actual bash.4 layout); `tests/release.sh` checks the exact layout.
- Tests for every profile, EOF, low disk, port conflicts, unknown swapfile, missing sudo, older-release rerun STOP, secrets in output, tampered/unreachable/wrong-version downloads.

## 1.0.0-bash.4

- Add a pinned, checksum-verified one-time bootstrap that registers a persistent `install-now` command.
- Store the verified bootstrap root-owned/read-only; keep archive downloads and verification unprivileged on every run.
- Require explicit `ja` before registration; refuse conflicting files and symlinks; make exact repeat registration leave files untouched.
- Add isolated launcher tests for registration, menu exit, download/checksum failures, protected modes and idempotence.

## 1.0.0-bash.3

- BASH-V1-002: pinned two-hash bootstrap trust chain, strict archive path/type validation and automatic interactive launch.
- Menu choices 1–5 and explicit ja; CLI audit/status/profile options preserved.
- Real completed-phase progress (APP 8 / DATABASE 7 / combined 10), ASCII/no-color TTY display, elapsed/activity and plain periodic log output.
- Granular package/service phases, backward-compatible private metadata, public sanitized status and login display; existing safe resume retained.
- Isolate progress-worker traps and restrict failure-state writes to the installation owner; real VM acceptance requires stable final COMPLETE after background settlement.
- Historical Python/research archives retained in Git but excluded from new release archives.

## 1.0.0-bash.2

- BASH-V1-001: repair root-only Codex permissions using a bounded runtime allowlist and actual unprivileged validation.
- Private npm HOME/cache/config remains protected; completed bash.1 APP/combined reruns can safely apply the precise patch with versioned resume code.
- Add real ordinary-user, negative complete-status and old-release repair/reboot regression coverage.

## 1.0.0-bash.1

- New standalone Bash architecture with APP, DATABASE and combined profile.
- Persistent minimum 4 GiB swap, bounded recovery, root-owned systemd resume and read-only audit.
- Signed APT validation, no general OS upgrade, pinned Codex dependency metadata.
- Bash regression and disposable VM acceptance tooling; checksum release artifacts.
- Python route: **CLOSED – SUPERSEDED BY BASH V1**. Historical source, documentation, research, releases and the uncommitted working-tree patch are archived; Git history remains intact.
- Prerelease only until all required real package, swap and reboot acceptance criteria pass. See docs/VALIDATION.md.
- All eight actual Ubuntu 26.04.1 scenarios and the full regression passed on source commit 1fe418f7ada859562bf80927d1a055d6e7fed51b. Closed real-test defects in swap inventory, reboot service ordering and isolated npm configuration. Independent public release verification is delivered as a release attachment; the requested prerelease designation is retained.
