# Installation

For bash.4, run the one-time pinned registration command in the README. It authenticates the release before asking `ja` to register a root-owned bootstrap and `/usr/local/bin/install-now`. Registration does not install a server profile. Run `install-now` later as your ordinary account; downloads and SHA256 verification remain unprivileged. The existing menu offers 1 APP, 2 DATABASE, 3 combined, 4 read-only status and 5 exit. Type `ja` only after reviewing an installation plan. Direct `bash install.sh` and existing CLI options remain available for a verified offline archive.

Installation has 8/7/10 actual completed phases according to the selected profile. The terminal's ASCII bar shows completed percentage plus activity/elapsed time; time does not change percentage. TERM=dumb and noninteractive CLI use plain logs with periodic activity messages. Public status contains only sanitized metadata; full logs remain root-private.

Run `bash install.sh` from the verified, extracted release. Choose one profile, review the plan and confirm once. Checks and menu/status before authorization are read-only. Installation obtains root through sudo when needed. Do not run the installer on APP-O; TEST-O requires separate live-install permission.

| Profile | Components |
|---|---|
| APP | Git, Python 3 development tool, .NET 10 SDK, Node.js/npm, pinned Codex CLI, Nginx |
| DATABASE | PostgreSQL 18 with local authentication and service verification |
| APP + DATABASE | Both sets in sequence, shared preparation once |

No OS release upgrade, firewall/SSH change, database deletion or user deletion is performed. Existing unsafe or ambiguous database configurations require operator review rather than automatic rewriting.

APT uses existing signed Ubuntu sources, including TransIP. Authentication bypass settings and missing candidates cause FAIL. Third-party repositories are not silently introduced. Lock contention is bounded; lock files and running package processes are never removed or killed. APT may install dependency updates required by the selected packages; it does not run a general distribution upgrade.

## Swap

At least 4 GiB total active swap is required after authorization. With 0 GiB the installer adds 4 GiB; with 2 GiB it adds the remaining 2 GiB; with 4 GiB or more it retains the current swap. Values are computed from actual bytes and rounded safely for swap metadata overhead.

New swap files use mode 0600, `mkswap`, `swapon` and one persistent `/etc/fstab` entry. Existing swap remains untouched. Unsupported filesystems or insufficient free space stop the installation. Less than 4 GiB physical RAM produces WARN: swap cannot replace adequate RAM.

Persistence is verified again on reboot by the resume/verification service. A successfully activated file before reboot does not by itself prove reboot persistence; see the acceptance report.

## Codex permissions (bash.2)

The pinned Codex runtime remains root-owned. Only its required directories and executables are mode 0755; package metadata is 0644. Ordinary users cannot modify these paths. Private markers, temporary npm configuration/cache and unrelated files are not made public. No recursive permission reset is used.

Completion requires actual `codex --version` execution as both root and unprivileged `nobody`, with a clean environment for the latter. Authentication to use Codex is a separate user action; this installer does not distribute credentials. See [BASH-V1-001](BASH-V1-001.md) for real ordinary-user tests.
