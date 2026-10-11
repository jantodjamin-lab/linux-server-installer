# Bash V1 architecture

`install.sh` provides the menu, profile plan, one authorization and orchestration. Active implementation modules are solely Bash:

| Module | Responsibility |
|---|---|
| `bash/common.sh` | output, guarded commands, package helpers |
| `bash/checks.sh` | read-only OS, RAM, signed-source and package checks |
| `bash/state.sh` | atomic persistent progress, locking, staged systemd resume |
| `bash/swap.sh` | byte inventory, deficit allocation, ownership/recovery, activation, fstab |
| `bash/app.sh` | APP package/tool installation and verification |
| `bash/database.sh` | PostgreSQL 18 installation and safe local verification |

The archived Python modules are never imported or executed. npm lock data is immutable dependency metadata for Codex, not installer code. System tools such as APT, systemd and util-linux are OS prerequisites. The APP profile intentionally includes Python as a development tool.

Tests use temporary filesystem fixtures and mocked command boundaries, plus disposable QEMU VMs for real package/swap/reboot acceptance. Host APP-O/TEST-O installation is excluded. Bash release tooling builds a deterministic archive and SHA256SUMS without Python.

Sources: [Ubuntu APT documentation](https://ubuntu.com/server/docs/how-to/software/package-management/), [PostgreSQL 18 authentication](https://www.postgresql.org/docs/18/auth-pg-hba-conf.html), [.NET Ubuntu support](https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-install).

The GlennR script supplied by the owner was reviewed only for simple menu/installation structure. No UniFi code is copied.
