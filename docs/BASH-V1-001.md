# BASH-V1-001 — Codex normal-user execution

Version: 1.0.0-bash.2. **NO-GO until this correction's real VM matrix and public-release verification pass.** Prior bash.1 evidence only tested Codex as root and does not establish normal-user usability.

Root cause: installer umask 077 was inherited by npm; the implicit /opt/universal-linux-installer parent and extracted executable files became 0700. The root-only --version check missed the permission failure.

Correction: explicit 0755 managed parents, npm-only umask 022, private temporary HOME/cache/config/output, and an exact allowlist for pinned Codex runtime directories (0755), package metadata (0644) and executables (0755). Files remain root-owned with no group/other write access. Private marker/cache/config and unrelated files are never recursively chmodded. Symlinks, foreign ownership, writeable runtime paths and special permission bits are rejected. The final verifier executes the actual CLI as unprivileged nobody with a clean environment; real VM tests additionally run as ordinary ubuntu.

Authorized reruns of completed bash.1 APP/combined installations may apply this precise permissions patch and update root-owned versioned resume code. Incomplete or unrelated version migrations remain refused. A persistent root-only authorization marker handles reboot after unit switching but before state-version commit. Preparation failure leaves the original state intact and requires authorized retry; no new success is recorded. Failed completed verification remains verification-only, without APT or swap allocation, and becomes complete only after mandatory checks pass.

Planned real tests: fresh APP and combined, actual root/ordinary-user CLI execution, exact ownership/modes and non-writability, private-file preservation, repeated install, actual old bash.1 installation and patch interrupted at unit switch followed by real automatic resume. Existing swap/PostgreSQL/Nginx/reboot regressions remain in the matrix. Other APP tools are checked as the ordinary user. Results and limits will be added before publication.

No TEST-O connection/execution, SSH/firewall/provider changes, Python/archive changes or history rewriting are authorized or performed.
