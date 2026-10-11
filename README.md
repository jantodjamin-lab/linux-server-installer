# Universal Linux Server Installer — Bash V1

**BASH-V1-001 validation in progress: NO-GO until bash.2 real permissions and reboot tests pass.** See [correction and evidence](docs/BASH-V1-001.md). Prior bash.1 root-only validation is historical.

Active installer code is Bash. Python 3 is installed only as an APP development tool.
The previous implementation is **CLOSED – SUPERSEDED BY BASH V1** and retained under `archive/`.

Download the release archive and SHA256SUMS, verify `sha256sum -c SHA256SUMS`, extract, then start:

```bash
bash install.sh
```

The menu offers APP, DATABASE, APP + DATABASE and read-only status. One confirmation authorizes the chosen plan. Root or sudo is required only for installation. No live installation is authorized on APP-O or TEST-O.

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
└── archive/
    ├── python-installer/
    └── research/
```
