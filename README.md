# Universal Linux Server Installer — Bash V1

**BASH-V1-003 / bash.4:** register the reusable `install-now` command once using the verified bootstrap below. After registration, run `install-now` from SSH/PuTTY to open the existing menu. See [launcher behavior and tests](docs/BASH-V1-003.md).

Active installer code is Bash. Python 3 is installed only as an APP development tool.
The previous implementation is **CLOSED – SUPERSEDED BY BASH V1** and retained under `archive/`.

Run the one-time bootstrap below from an SSH/PuTTY terminal. It downloads the fixed bash.4 release, verifies the pinned bootstrap and archive, safely validates/extracts the archive, asks before registration, then installs a protected launcher. It does not install a server profile.

The menu offers choices 1–5: APP, DATABASE, APP + DATABASE, read-only status and exit. Invalid input is retried; explicit `ja` authorizes the selected plan. Root or sudo is required only for installation. No live installation is authorized on APP-O or TEST-O.

Each later `install-now` invocation runs the installed root-owned bootstrap as the ordinary user. That bootstrap downloads and verifies the same fixed archive before opening the unchanged menu. Both downloads use immutable versioned release URLs, never “latest”. The exact registration command is published after the archive hash is finalized. This block is omitted from the archive README to avoid a circular checksum.

<!-- RELEASE-BOOTSTRAP:BEGIN -->
Fixed prerelease: **v1.0.0-bash.4**. Run this one-time registration command:

```bash
bash -c set\ -Eeuo\ pipefail\;\ trap\ \'printf\ \"FAIL\ bootstrapdownload\ of\ validatie\\n\"\ \>\&2\'\ ERR\;\ umask\ 077\;\ command\ -v\ curl\ \>/dev/null\;\ command\ -v\ sha256sum\ \>/dev/null\;\ exec\ 3\<\>/dev/tty\;\ w=\$\(mktemp\ -d\ /tmp/uli-loader.XXXXXXXX\)\;\ trap\ \'rm\ -rf\ --\ \"\$w\"\'\ EXIT\;\ curl\ -q\ --fail\ --location\ --proto\ =https\ --proto-redir\ =https\ --connect-timeout\ 30\ --max-time\ 300\ --max-filesize\ 262144\ \"https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.3/bootstrap.sh\"\ --output\ \"\$w/bootstrap.sh\"\;\ \[\[\ -f\ \$w/bootstrap.sh\ \&\&\ \!\ -L\ \$w/bootstrap.sh\ \&\&\ \$\(wc\ -c\ \<\ \"\$w/bootstrap.sh\"\)\ -le\ 262144\ \]\]\;\ printf\ \'cc6a7e3a4dbf5761b3bf408af04e12d406f28cf3a9de3c8bbbd025e1a856f913\ \ %s\\n\'\ \"\$w/bootstrap.sh\"\ \|\ sha256sum\ --check\ --status\;\ bash\ -n\ \"\$w/bootstrap.sh\"\;\ bash\ \"\$w/bootstrap.sh\"\ \"\$@\"\ \<\&3\ \>\&3\ 2\>\&3 --
```

After registration, run `install-now` whenever you want to open the menu.
<!-- RELEASE-BOOTSTRAP:END -->

For an already independently verified and extracted offline release, start the existing installer directly:

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
