> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Inventory and reuse decision

Read the complete CODEX_3_ITERATIONS.md contract. Current branch was clean.
Existing `infrastructure/installer/` contains stdlib preflight, pure planning,
SQLite dry-run/recovery, remote preflight and swap simulations. Existing `tests/`
cover those work packages. `applications/` contains no installer runtime.
Existing architecture, plan contract, dry-run architecture, project baseline,
source register and historical universal Ubuntu design were inspected read-only.
Historical references are ignored by Git and are not runtime dependencies.

Reuse policy: retain the established 1 CPU / 843 MiB minimum and profile disk
limits, JSON evidence, explicit review and uncertain-effect stop policy.
Keep this installer standalone; do not import remote adapters or historical code.
Existing functionality and archives remain untouched. Ubuntu 26.04 compatibility
and exact package closure need independent validation before live acceptance.
