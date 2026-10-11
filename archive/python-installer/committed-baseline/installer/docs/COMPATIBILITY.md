> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Compatibility and implementation limits

Primary sources reviewed 2026-10-10:
- https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-install
  documents .NET 10 from the Ubuntu 26.04 feed.
- https://www.postgresql.org/download/linux/ubuntu/ lists Ubuntu resolute 26.04.
- https://angular.dev/reference/versions documents Angular 20 / Node 22.12+.

These sources establish vendor documentation, not installation acceptance.
The engine implements exact-version checks, offline artifact checksum checks,
role planning, update-list binding, development-only Codex selection, sanitized
journal, manual reboot stops, idempotence, interrupted-run review and validators.
No live runner is released. Bundle SHA256 is integrity, not publisher authentication.
The Ubuntu source allowlist deliberately rejects unreviewed third-party feeds.
Angular/Codex npm bundles, signed apt metadata, full transitive package closure,
service validators, firewall policy and system updates require additional work.
No fabricated production package lock is supplied. Test bundle bytes are fixtures.
This is WARN / incomplete installation implementation, not a production V1.0.
