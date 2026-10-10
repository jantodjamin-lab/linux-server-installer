# Offline acceptance — v1.0.0-rc.3

**NIET LIVE GEVALIDEERD / NOT LIVE VALIDATED.**

RC3 adds verified Ubuntu universe Node 22 LTS/npm 9 provisioning, deficit-only
persistent swap, and physical-resource/profile admission plus recommendations.
See [RC3](RC3.md) for implementation, exact safety limits and test methodology.

54 offline tests PASS. Regression coverage includes three profiles, optional
Codex, exact APT/npm dependency pins, service guards/configuration, checksum and
path integrity, host locking, durable interruption and reviewed recovery.
RC3 covers key/signature failures (including real gpgv malformed-fixture refusal),
missing packages, swap 0/2/>=4 GiB capacity arithmetic, proportional temporary
file allocation/recovery, rights/disk/filesystem/fstab failures, repeat execution,
RAM independent of swap, and CLI audit/dry-run without execution.

No live APT/npm install, actual swap format/activation, service change, remote
connection, database action or reboot is part of these tests. Parent application
regressions have not been rerun in this RC3 workspace. Temporary files and command
doubles do not establish live Ubuntu compatibility or production performance.

Release checks include deterministic rebuild, checksums, extracted-archive tests,
Python/POSIX syntax, explicit generic-only allowlist, secret/internal-data patterns
and workflow pinning. Publication and anonymous download checks must be recorded
separately; passing local tests is not proof of a published release.
