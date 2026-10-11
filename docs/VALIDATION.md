# Bash V1 acceptance evidence
> Historical bash.1 acceptance only: Codex was checked as root. See BASH-V1-001.md for the bash.2 correction and current normal-user evidence. The original source manifest is now `evidence/BASH1-TESTED-INSTALLER.sha256`; `evidence/TESTED-INSTALLER.sha256` describes bash.2.


**PASS — real installation acceptance completed, 2026-10-11.** Production GO additionally requires independent public-download verification, attached to the release as `PUBLICATION-VERIFICATION.md`.

Tested source: `1fe418f7ada859562bf80927d1a055d6e7fed51b`. Full [acceptance run](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38135968474): **9/9 successful jobs**, including eight fresh disposable QEMU VMs. Release documentation is added after acceptance; active installer bytes are checked against `evidence/TESTED-INSTALLER.sha256` before release creation.

| Actual Ubuntu 26.04.1 scenario | Result | Artifact |
|---|---|---|
| APP, no initial swap | PASS | 11701751618 |
| DATABASE, no initial swap, actual ubuntu/sudo entry | PASS | 11702205458 |
| APP + DATABASE, no initial swap | PASS | 11701717937 |
| DATABASE, existing 2 GiB swap | PASS | 11701691766 |
| DATABASE, existing 4 GiB swap | PASS | 11702136257 |
| DATABASE, interrupted package step and actual reboot/resume | PASS | 11702106349 |
| DATABASE, interrupted swap allocation and actual reboot/safe stop | PASS | 11702115911 |
| DATABASE, signed TransIP Ubuntu mirror | PASS | 11701306669 |

Each positive VM completed two actual boots, checked the resume service before manual rerun, verified at least 4 GiB active swap, checked component versions/services and repeated the installer without changing fstab. Resume Result=success, ExecMainStatus=0 and nonzero monotonic start times are preserved. Existing 2 GiB remained active alongside the added deficit; existing 4 GiB required no new managed file.

The interrupted package scenario recorded current=database, rebooted before package mutation and completed automatically. The interrupted swap scenario allocated a real 1 MiB partial file and rebooted: resume exit 1, state failed at swap, no activation, unchanged size/hash and fstab. This expected safe failure is a PASS of recovery safety, not a completed database installation. Partial SHA256: `30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58`.

All guests identify Ubuntu 26.04.1 LTS. Canonical image authentication used pinned signing fingerprint `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`, valid detached signature and image SHA256 `8800651811af9a85465ad1d552add729947bb16488dddb4a9b5305a3d97332b2`.

Actual versions: Git 2.53.0, .NET SDK 10.0.112, Node 22.22.1, npm 9.2.0, Codex CLI 0.128.0 and PostgreSQL 18.6. Nginx configuration and active service passed. Python 3 is only an APP development package; DATABASE and the installer execute no Python code.

Offline validation: 16 Bash contract groups plus swap/profile/sudo/npm matrices, syntax, ShellCheck, deterministic release rebuild, outer SHA256 and inner file manifest, extracted-release regression. Coverage includes menu/all profiles, 0/2/4/6 GiB swap, idempotence, interruption, unsuitable filesystem, insufficient disk, failed-write preservation, bounded APT errors, absent candidates, authorization/sudo, read-only audit, locking and strict state parsing. Historical archival suites: 155 tests passed with one skip; 66 private preflight tests passed.

Actual failures exposed and closed swap-column parsing, a test-service ordering cycle, npm duplicate configuration paths and PostgreSQL verification racing service startup. Full regression and actual VM scenarios were repeated. Independent source review found no remaining concrete high/critical finding.

Scope: actual amd64 Ubuntu 26.04.1 guests, ext4 swap creation and existing signed TransIP mirror. XFS is supported by checks but lacks a separate real-filesystem acceptance run; unsupported filesystems fail safely. Other OS/architectures are outside acceptance. Guest memory accounting below 4 GiB correctly produced WARN. An additional local dependency check hit /tmp quota; successful actual APP VMs supply installation evidence.

No system installation or target changes occurred on APP-O or TEST-O. History, historical releases and the original Ramin archive are preserved. Deliverable remains the requested prerelease; live TEST-O installation requires separate authorization.
