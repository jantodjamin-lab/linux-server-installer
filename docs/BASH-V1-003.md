# BASH-V1-003 — install-now launcher

The one-time command in the README downloads a pinned bootstrap, verifies its SHA256, downloads and validates the matching release archive, then asks for `ja` before registering the launcher. It does not select or install a profile.

Registration writes a root-owned 0644 bootstrap under `/usr/local/lib/universal-linux-installer/` and a root-owned 0755 `/usr/local/bin/install-now`. The launcher forwards existing CLI arguments to the verified bootstrap. Each invocation downloads the same pinned release as an ordinary user; the existing menu, installation engine, progress display and reboot-resume code remain the release payload.

Registration refuses symlinked, nonregular, incorrectly owned, writable or conflicting destinations. It stages updates atomically, completes safely if interrupted between the bootstrap and launcher writes, and makes an exact repeat leave both files unchanged. Download or checksum failures stop before registration.

`tests/launcher.sh` uses a private temporary installation root, fixture HTTPS downloads and a real PTY. It checks confirmation, one-time registration, file ownership/modes, idempotence, menu choice 5, bootstrap/archive download failures, checksum mismatch and symlink conflict. It never invokes sudo, installs packages or writes to system paths. Full profile, VM and reboot tests were not part of BASH-V1-003 acceptance.
