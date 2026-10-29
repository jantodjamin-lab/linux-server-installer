# Security

## Boundaries of the installer

- Nothing changes before explicit authorization (`ja` for installation, `bijwerken` for system updates).
- No `curl | bash`, no trust bypass, no database/user removal, no SSH or firewall changes, no automatic reboot.
  System updates run `apt-get update` and `apt-get upgrade` only after a shown plan; never
  `full-upgrade`, `autoremove` or package removals.
- Resume executes only the staged root-owned Bash copy and data-only state. Ambiguous ownership,
  package health, version or recovery stops safely.
- APT command output is not persisted in installer logs (source URLs may contain credentials).
  Do not enable shell tracing. Logs and state are root-only.

## Verifying downloads

Use the one-command route from the README: it checks the pinned SHA256 of `bootstrap.sh` before
running it, and the bootstrap checks the pinned SHA256 and contents of the release archive. The pin
in the README is published next to the download; compare it with a copy you obtained through a
second channel you trust. There are no publisher signatures.

## Scope

Releases are prereleases for test and development servers on Ubuntu 26.04 LTS and are not validated
for production. Older releases remain available for reference; use the version recommended in the
README.

## Reporting a problem

Please open a GitHub issue without including secrets, passwords, host addresses or private logs.
