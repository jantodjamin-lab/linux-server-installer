# Universal Linux Installer V1.0

**v1.0.0-rc.2 — NIET LIVE GEVALIDEERD / NOT LIVE VALIDATED.**
A manually launched, local Ubuntu 26.04 installer with APP, DB and APP+DB
profiles. Python 3.11+ and POSIX shell are required. Default mode is read-only.
No SSH, remote provisioning, automatic rollback, firewall or SSH changes.

```sh
sh install.sh --profile APP --audit
python3 -B -W error::ResourceWarning -m unittest discover -s tests
```

In a parent project checkout, prefix these paths with `installer/`.
Audit outputs JSON; exit 0 is PASS/WARN, 1 is FAIL, 2 is a CLI error.
The public repository and release contain only generic installer files.

The implemented local adapter supports signed Ubuntu apt sources, exact package
and dependency pins, separately approved pinned updates, .NET 10, Node 22.12+ or 24,
Angular CLI 20, Nginx, PostgreSQL 18 and optional development-only Codex.
A reviewed npm v3 lock fixes integrity for the complete dependency graph.
Package scripts may run with root via apt; npm lifecycle scripts are disabled.
No actual Ubuntu package versions or npm tarballs are fabricated or bundled.
An operator must resolve and review exact locks for the target before execution.

See [operator guide](docs/GUIDE.md), [security policy](SECURITY.md),
[official sources](docs/SOURCES.md), and [offline acceptance](docs/ACCEPTANCE.md).
The RC has offline code/fixture validation only. A separate owner-approved test
installation on a fresh disposable Ubuntu target is still required. No stable
v1.0.0 release or production GO is implied.
