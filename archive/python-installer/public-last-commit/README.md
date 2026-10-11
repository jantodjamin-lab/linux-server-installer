> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; do not use these commands for installation.

# Universal Linux Installer

**1.0.0-rc.5 — NIET LIVE GEVALIDEERD / NOT LIVE VALIDATED.**
Local Ubuntu 26.04 installer for fresh disposable APP, DB or APP+DB VMs.
Runtime: Python 3.11+ and POSIX sh. Audit is read-only.

```sh
sh install.sh --profile APP+DB --audit
sh install.sh --profile APP+DB --apply --sudo
```

Apply shows bounded installation intent before requesting `INSTALL <hash-prefix>`.
It asks explicit snapshot/risk questions unless those acknowledgements are supplied
as flags. Only after authorization does it refresh signed metadata, resolve the
exact dependency closure and install. No manual lock, plan or npm bundle is needed.
Existing package upgrades require `--system-updates`; absence means stop rather
than silently upgrade. An explicitly allowed provider mirror uses its exact URI.

[Operator guide](docs/GUIDE.md) · [Security](SECURITY.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md) ·
[Sources](docs/SOURCES.md)

```sh
python3 -B -W error::ResourceWarning -m unittest discover -s tests
```

No SSH, remote execution, automatic rollback, firewall changes or production GO.
Signed sources, exact pins, reviewed npm/SRI locks and private recovery evidence
remain mandatory. Neither unit nor container tests establish live VM acceptance.
