# Changelog

## 1.0.0-bash.1

- New standalone Bash architecture with APP, DATABASE and combined profile.
- Persistent minimum 4 GiB swap, bounded recovery, root-owned systemd resume and read-only audit.
- Signed APT validation, no general OS upgrade, pinned Codex dependency metadata.
- Bash regression and disposable VM acceptance tooling; checksum release artifacts.
- Python route: **CLOSED – SUPERSEDED BY BASH V1**. Historical source, documentation, research, releases and the uncommitted working-tree patch are archived; Git history remains intact.
- Prerelease only until all required real package, swap and reboot acceptance criteria pass. See docs/VALIDATION.md.
- All eight actual Ubuntu 26.04.1 scenarios and the full regression passed on source commit 1fe418f7ada859562bf80927d1a055d6e7fed51b. Closed real-test defects in swap inventory, reboot service ordering and isolated npm configuration. Independent public release verification is delivered as a release attachment; the requested prerelease designation is retained.
