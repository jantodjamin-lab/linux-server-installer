# BASH-V1-001 — Codex execution permissions

Version: **1.0.0-bash.2**. Technical acceptance: **PASS** for the tested Ubuntu 26.04.1 LTS amd64/ext4 environment. The independent public-download verification and final repository commit IDs are recorded in the release attachment `BASH-V1-001-VERIFICATION.md`. A TEST-O installation still requires separate permission.

Root cause: installer umask 077 was inherited by npm; the implicit `/opt/universal-linux-installer` parent and extracted executable files became 0700. Root-only `--version` validation missed the permission failure.

Correction: explicit 0755 managed parents, npm-only umask 022, private temporary HOME/cache/config/output, and an exact allowlist for pinned Codex runtime directories (0755), package metadata (0644) and executables (0755). Files remain root-owned with no group/other write access. Private markers/cache/config and unrelated files are never recursively chmodded. Symlinks, foreign ownership, writable runtime paths and special permission bits are rejected. Final verification executes the actual CLI as root and unprivileged `nobody` with a clean environment; VM acceptance additionally runs as ordinary `ubuntu`.

Authorized reruns of completed bash.1 APP/combined installations may apply this precise permissions patch and update root-owned versioned resume code. Incomplete or unrelated version migrations remain refused. A persistent root-only authorization marker handles reboot after unit switching but before state-version commit. Preparation failure leaves the original state intact and requires authorized retry; no new success is recorded. Failed completed verification remains verification-only, without APT or swap allocation, and becomes complete only after mandatory checks pass.

The complete [acceptance run](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38174989285) tests commit `8cb7122d2b2478970b10130be556e2082e821a48`: offline regression plus nine disposable QEMU VMs using a Canonical-signed Ubuntu 26.04.1 cloud image. Earlier run `38161936100` passed all nine VMs but exposed an offline fixture coupling to writable GitHub-runner directories; that fixture was isolated and the entire matrix repeated. Active installer bytes did not change between the runs. The published active bytes match `evidence/TESTED-INSTALLER.sha256`.

| Test | Result and actual evidence |
|---|---|
| Fresh APP, APP+DATABASE and DATABASE | PASS: real signed APT/npm package installations, service/version checks |
| Root, ordinary ubuntu and clean-environment nobody Codex execution | PASS: actual CLI 0.128.0 execution after reboot |
| Runtime ownership/modes and non-writability | PASS: UID 0; exact 0755/0644; ordinary user cannot write any allowlisted path |
| Private data protection | PASS: marker 0600; old-install private fixture directory 0700/file 0600, unchanged checksum and unreadable by ubuntu |
| Repeated installation | PASS: completed verification, no duplicate fstab entries or package replay |
| Existing wrong-permission bash.1 installation | PASS: actual old combined installer reproduces root success/user denial; authorized patch repairs it |
| Interrupted permissions migration and actual reboot resume | PASS: paused after new service switch with old version still in state; automatic resume saves bash.2 complete and retains old staged code |
| Root-only execution rejection / complete status | PASS: VM-only nobody-probe fault injection blocks new APP completion and rejects formerly complete APP, recording failed/verification |
| Verification-only recovery | PASS: --resume succeeds with an APT wrapper that fails on any invocation; no unexpected APT occurred |
| Swap 0→4 GiB, 2→4 GiB and retained 4 GiB | PASS: actual files/activation/persistent fstab and post-reboot verification |
| Interrupted swap creation | PASS: actual interruption stops safely; uncertain allocation is not automatically reused |
| PostgreSQL 18, Nginx and general reboot resume | PASS: actual services and retained swap verified after real reboot |
| Other APP components as ordinary user | PASS: Git, Python, .NET, Node.js/npm and Nginx command output; no matching permissions defect found |
| Read-only audit, sudo, locks, missing packages/APT failure, no Python installer dependency | PASS: isolated Bash regressions; actual ubuntu/sudo entry in DATABASE VM |
| Release integrity / ShellCheck | PASS: deterministic rebuild, internal/external checksums, extracted offline regression; public verification in release attachment |

**NOT TESTED:** live TEST-O or its specific `o2-admin` account; ARM64; XFS/Btrfs; interactive Codex login/API use. This patch proves CLI execution and installer permissions, not credentials or application workloads. The implementation contains an ARM64 allowlist, but this release's actual VM acceptance is amd64/ext4 only. Incomplete bash.1 migrations require operator review and are deliberately refused.

No TEST-O connection/execution, SSH/firewall/provider changes, Python/archive changes or history rewriting were performed. No critical or high findings remain open in the targeted permission/state review. The historical bash.1 reports are explicitly marked as root-only evidence; their original source manifest is retained separately.
