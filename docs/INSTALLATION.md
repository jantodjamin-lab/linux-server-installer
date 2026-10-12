# Installation

For bash.3, copy the exact pinned one-liner from the repository README. It handles verified downloads, safe extraction and interactive launch as your ordinary account. Neither bootstrap download needs sudo. Choose 1 APP, 2 DATABASE or 3 combined and type `ja` after the plan; 4 is read-only status and 5 exits. The direct `bash install.sh` and CLI options remain available for verified offline archives.

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
