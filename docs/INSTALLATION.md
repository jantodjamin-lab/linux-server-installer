# Installation

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
