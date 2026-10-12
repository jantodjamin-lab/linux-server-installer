# Universal Linux Server Installer — Bash V1

**BASH-V1-002 / bash.3: publication blocked pending final progress-process isolation regression.** Final public one-liner verification is recorded in the release attachment `BASH-V1-002-VERIFICATION.md`. See [bootstrap, menu, progress and test limits](docs/BASH-V1-002.md) and [prior Codex correction](docs/BASH-V1-001.md).

Active installer code is Bash. Python 3 is installed only as an APP development tool.
The previous implementation is **CLOSED – SUPERSEDED BY BASH V1** and retained under `archive/`.

Download the release archive and SHA256SUMS, verify `sha256sum -c SHA256SUMS`, extract, then start:

```bash
bash install.sh
```

The menu offers choices 1–5: APP, DATABASE, APP + DATABASE, read-only status and exit. Invalid input is retried; explicit `ja` authorizes the selected plan. Root or sudo is required only for installation. No live installation is authorized on APP-O or TEST-O.

The pinned release bootstrap downloads and verifies both bootstrap and archive before execution. Its exact trusted one-liner is published below after the archive is finalized. This publication block is omitted from the archive README to avoid a circular checksum; rebuilding the archive does not depend on that block. Both downloads use immutable versioned release URLs, never “latest”.

<!-- RELEASE-BOOTSTRAP:BEGIN -->
Exact trusted command pending successful bash.3 acceptance and publication.
<!-- RELEASE-BOOTSTRAP:END -->

Progress counts actual completed phases: APP 8, DATABASE 7, combined 10. A terminal displays an ASCII bar, activity, current phase and elapsed time. Noninteractive execution uses plain step messages and periodic activity messages. Percentages never advance with elapsed time. State and private resume code persist independently of bootstrap temporary files.

Targets: Ubuntu 26.04.1 LTS, signed Ubuntu repositories including the existing TransIP mirror. Filesystem support for newly created swap is deliberately bounded; unsupported filesystems fail safely. Existing swap is never removed.

See [installation](docs/INSTALLATION.md), [recovery](docs/RECOVERY.md), [architecture](docs/ARCHITECTURE.md), [validation](docs/VALIDATION.md) and [archive inventory](docs/ARCHIVE.md).

```text
linux-server-installer/
├── install.sh
├── README.md
├── VERSION
├── CHANGELOG.md
├── bash/              # common, checks, state, swap, app, database
├── docs/              # installation, recovery, architecture, archive, validation
├── tests/             # isolated Bash regression tests
├── tools/             # Bash validation and release tools
├── .github/workflows/ # disposable VM acceptance
└── archive/           # Git repository only; excluded from bash.3 release archives
```
