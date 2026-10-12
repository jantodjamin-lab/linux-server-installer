Universal Linux Installer **1.0.0-bash.3 — BASH-V1-002**.

**PASS: installation and candidate-bootstrap acceptance on actual Ubuntu 26.04.1 amd64/ext4 VMs.** The final exact-public-one-liner check, final repository commits and asset hashes are recorded in the release attachment `BASH-V1-002-VERIFICATION.md`. Live TEST-O remains separately authorized.

The trusted one-liner authenticates a fixed bootstrap SHA256 before checking or executing it. That authenticated bootstrap embeds the fixed versioned archive URL and trusted archive SHA256. Neither remote checksum file is the trust anchor. GNU tar member checks reject traversal, absolute/ambiguous/control-character paths, symlinks/hardlinks, special files/modes, duplicates, missing modules and excessive sizes before extraction. Both downloads/extraction run as an ordinary account. Sudo is obtained only for the confirmed installer.

The bootstrap and exact command are rendered outside the archive after its hash exists. The repository README's marked postbuild command block is stripped when packaging, eliminating the circular hash problem and preserving deterministic rebuilds. The active payload excludes historical Python/research archives; they remain unchanged in Git and earlier releases. `.gitattributes` excludes them from source exports too; the public verification checks both archives.

Menu 1 APP, 2 DATABASE, 3 combined, 4 status, 5 exit. Invalid input is retried, there is no default profile, and only explicit `ja` authorizes changes. Existing CLI audit/status/profile/yes options remain available. Profile phases are system, plan, swap; APP packages/Codex/Nginx and/or PostgreSQL/database check; resume and final verification. Totals are 8/7/10.

Percentage is an equal-weight count of genuinely completed phases, never elapsed-time based. A 20-cell ASCII bar, activity indicator and total/step elapsed time are rendered within terminal width minus one column. Full phase descriptions are logged once; long phases produce one warning and periodic activity. TERM=dumb/no-color and noninteractive plain logs are supported. Progress is reconstructed from persistent state after reboot. Reverification makes final validation pending again until it succeeds.

Private state/log/code remain root-owned under `/var/lib/universal-linux-installer/`. The old six-field schema remains readable; the new schema records start/end and bounded error identifiers. Ordinary users read only a sanitized root-owned 0644 status projection in a separate 0755 directory. A managed interactive `/etc/profile.d` helper displays it on login, registered before package/swap changes. No SSH/firewall/provider configuration changes are made.

Completed bash.2 profiles can be explicitly authorized for verification-only migration, without package replay. Completed bash.1 APP/combined permissions repair remains available. Incomplete old-version migrations stop safely and retain their matching staged code. A root-only marker bridges interruption during unit switching. All preparation signals preserve original metadata, uncertain interrupted dpkg state stops, and unknown resume phases are rejected. Final component and swap verification cannot be skipped before COMPLETE.

The [full accepted matrix](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38189090388) tests source `6e4cf9740b0bbb0eedafbbc053a3ee736592f94f`: **12/12 executed jobs successful**, comprising offline regression and eleven real disposable QEMU VM scenarios. The separately gated public-bootstrap job is deliberately skipped in this matrix and dispatched after publication. The active bytes match `evidence/TESTED-INSTALLER.sha256`; old bash.2 bytes remain in `evidence/BASH2-TESTED-INSTALLER.sha256`.

| Actual VM scenario | Result |
|---|---|
| Fresh APP, 0→4 GiB swap | PASS |
| Fresh DATABASE, 0→4 GiB swap and ordinary ubuntu/sudo entry | PASS |
| Fresh APP+DATABASE, 0→4 GiB swap | PASS |
| DATABASE, existing 2 GiB / retained 4 GiB swap | PASS, both scenarios |
| DATABASE, interrupted package phase / interrupted swap allocation | PASS, safe resume or expected fail-closed stop respectively |
| DATABASE, signed existing TransIP mirror | PASS |
| Old bash.1 combined root-only Codex repair interrupted at unit switch | PASS, actual reboot and automatic repair |
| Working bash.2 combined migration interrupted at unit switch | PASS, actual reboot and zero APT calls during reuse |
| Exact candidate one-liner, two HTTPS downloads with trusted fixture CA | PASS, real ubuntu PTY menu/ja, bar 7/7, status/login read-only and reboot |

All positive VM scenarios verify actual services, post-reboot swap, idempotent rerun and automatic resume. APP scenarios execute Codex 0.128.0 as root, ordinary ubuntu and clean-environment nobody; exact root ownership/0755/0644 runtime modes, non-writability and private 0600/0700 files are checked. Fault injection blocks COMPLETE when unprivileged Codex verification fails, then verification-only retry succeeds without APT. Other APP tools and PostgreSQL/Nginx are exercised normally.

Offline/real-PTY tests cover every menu option, invalid/cancel/ja input, no preauthorization changes, corrupt hashes/archives, traversal/links/duplicates/special types, required files, 8/7/10 counts, idempotent restore, unchanged percentage during blocked phases, width-80 frames, ASCII/no-color/TERM=dumb, sparse plain activity, strict old/new state, unknown phases and a real TERM during pre-unit migration setup preserving bash.2 metadata. Release tests prove deterministic rebuild, internal/external checksums and extracted regression; ShellCheck passes.

Three bounded iteration controls: first implementation/local review; second terminal-width/recovery correction with full latest-source VM regression (the obsolete earlier matrix was canceled); third final publication verification and fresh-VM exact public one-liner. No further RC line or unrelated profiles were introduced.

**NOT TESTED:** TEST-O/APP-O, the specific `o2-admin` account, physical PuTTY/SSH transport, ARM64, XFS/Btrfs and Codex login/API workloads. Actual terminal evidence is PTY/ASCII/ANSI compatible with standard SSH terminals. No critical/high findings remain open in targeted reviews. No production, old Python/archive or Git-history changes were made.
