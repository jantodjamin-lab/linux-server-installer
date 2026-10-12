# Universal Linux Server Installer — Bash V1

**BASH-V1-002 / bash.3: installation and candidate-bootstrap acceptance PASS on actual Ubuntu 26.04.1 amd64/ext4 VMs (12/12 executed jobs).** Final public one-liner verification is recorded in the release attachment `BASH-V1-002-VERIFICATION.md`. See [bootstrap, menu, progress and test limits](docs/BASH-V1-002.md) and [prior Codex correction](docs/BASH-V1-001.md).

Active installer code is Bash. Python 3 is installed only as an APP development tool.
The previous implementation is **CLOSED – SUPERSEDED BY BASH V1** and retained under `archive/`.

Start from an SSH/PuTTY terminal with the trusted one-liner below. It downloads the pinned release, verifies both hashes, safely extracts the payload and opens the menu. No manual download or extraction is needed.

The menu offers choices 1–5: APP, DATABASE, APP + DATABASE, read-only status and exit. Invalid input is retried; explicit `ja` authorizes the selected plan. Root or sudo is required only for installation. No live installation is authorized on APP-O or TEST-O.

The pinned release bootstrap downloads and verifies both bootstrap and archive before execution. Its exact trusted one-liner is published below after the archive is finalized. This publication block is omitted from the archive README to avoid a circular checksum; rebuilding the archive does not depend on that block. Both downloads use immutable versioned release URLs, never “latest”.

<!-- RELEASE-BOOTSTRAP:BEGIN -->
Fixed prerelease: **v1.0.0-bash.3**. Run this single command from your terminal:

```bash
bash -c set\ -Eeuo\ pipefail\;\ trap\ \'printf\ \"FAIL\ bootstrapdownload\ of\ validatie\\n\"\ \>\&2\'\ ERR\;\ umask\ 077\;\ command\ -v\ curl\ \>/dev/null\;\ command\ -v\ sha256sum\ \>/dev/null\;\ exec\ 3\<\>/dev/tty\;\ w=\$\(mktemp\ -d\ /tmp/uli-loader.XXXXXXXX\)\;\ trap\ \'rm\ -rf\ --\ \"\$w\"\'\ EXIT\;\ curl\ -q\ --fail\ --location\ --proto\ =https\ --proto-redir\ =https\ --connect-timeout\ 30\ --max-time\ 300\ --max-filesize\ 262144\ \"https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.3/bootstrap.sh\"\ --output\ \"\$w/bootstrap.sh\"\;\ \[\[\ -f\ \$w/bootstrap.sh\ \&\&\ \!\ -L\ \$w/bootstrap.sh\ \&\&\ \$\(wc\ -c\ \<\ \"\$w/bootstrap.sh\"\)\ -le\ 262144\ \]\]\;\ printf\ \'cc6a7e3a4dbf5761b3bf408af04e12d406f28cf3a9de3c8bbbd025e1a856f913\ \ %s\\n\'\ \"\$w/bootstrap.sh\"\ \|\ sha256sum\ --check\ --status\;\ bash\ -n\ \"\$w/bootstrap.sh\"\;\ bash\ \"\$w/bootstrap.sh\"\ \"\$@\"\ \<\&3\ \>\&3\ 2\>\&3 --
```

Trusted archive SHA256: `399cc074823fcb97d8ac9c180d9717650387563e9ed1244807cba729841024ea`.
Trusted bootstrap SHA256: `cc6a7e3a4dbf5761b3bf408af04e12d406f28cf3a9de3c8bbbd025e1a856f913`.
Final public acceptance and repository commits: release attachment `BASH-V1-002-VERIFICATION.md`. Live TEST-O requires separate authorization.
<!-- RELEASE-BOOTSTRAP:END -->

For an already independently verified and extracted offline release:

```bash
bash install.sh
```

Progress counts actual completed phases: APP 8, DATABASE 7, combined 10. A terminal displays an ASCII bar, activity, current phase and elapsed time. Noninteractive execution uses plain step messages and periodic activity messages. Percentages never advance with elapsed time. State and private resume code persist independently of bootstrap temporary files.

Targets: Ubuntu 26.04.1 LTS, signed Ubuntu repositories including the existing TransIP mirror. Filesystem support for newly created swap is deliberately bounded; unsupported filesystems fail safely. Existing swap is never removed.

See [installation](docs/INSTALLATION.md), [recovery](docs/RECOVERY.md), [architecture](docs/ARCHITECTURE.md), [validation](docs/VALIDATION.md) and [archive inventory](docs/ARCHIVE.md).

```text
linux-server-installer/
├── install.sh
├── README.md
├── VERSION
├── CHANGELOG.md
├── bash/              # common, checks, state, swap, app, database
├── docs/              # installation, recovery, architecture, archive, validation
├── tests/             # isolated Bash regression tests
├── tools/             # Bash validation and release tools
├── .github/workflows/ # disposable VM acceptance
└── archive/           # Git repository only; excluded from bash.3 release archives
```
