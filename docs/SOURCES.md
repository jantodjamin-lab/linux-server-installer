# Primary sources

Reviewed during rc.4 development. Documentation support does not establish live
installation acceptance. Exact target locks and disposable-VM validation remain
required. No copied vendor installer or mutable curl-to-shell script is used.

- [.NET on Ubuntu](https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-install): Ubuntu 26.04 distro .NET 10 packages.
- [PostgreSQL Ubuntu packages](https://www.postgresql.org/download/linux/ubuntu/): Ubuntu resolute and PostgreSQL package availability. This installer uses approved Ubuntu feeds only; no PGDG repository is imported.
- [Angular compatibility](https://angular.dev/reference/versions): Angular 20 and Node 22.12+ LTS and npm 9 compatibility range used by this candidate.
- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli): optional @openai/codex package. Exact reviewed version required; no login setup.

APT package signature/dependency behavior and npm integrity are exercised through
bounded command doubles offline. No claim of verified live apt/npm transaction
or official package artifact authentication from offline fixtures is made.

RC3 primary references (reviewed 2026-10-10):

- [Ubuntu Node.js resolute](https://packages.ubuntu.com/resolute/nodejs): Node 22 in universe.
- [Ubuntu npm resolute](https://packages.ubuntu.com/resolute/npm): npm 9 and dependency metadata; catalog availability alone is insufficient.
- [Node release lifecycle](https://nodejs.org/en/about/previous-releases): supported LTS lines.
- [Canonical key fingerprints](https://documentation.ubuntu.com/security/software-integrity/image-verification/): installed keyring trust and official fingerprints.
- [Ubuntu archive integrity](https://documentation.ubuntu.com/security/software-integrity/archive-verification/): signed package checksum chain.
- [swapon manual](https://man7.org/linux/man-pages/man8/swapon.8.html): swap-file hole/CoW limitations and XFS support.

RC4 command-format references (reviewed 2026-10-10):

- [Ubuntu swapon](https://manpages.ubuntu.com/manpages/resolute/man8/swapon.8.html): supported raw byte inventory; empty output represents zero active swap.
- [Ubuntu sources.list](https://manpages.ubuntu.com/manpages/resolute/man5/sources.list.5.html): deb822 continuation fields, explicit Signed-By and consistent URI/suite bindings.
- [GnuPG configuration](https://gnupg.org/documentation/manuals/gnupg/GPG-Configuration-Options.html): explicit keyring and read-only listing options.

The catalog lists Node 22.22.1 and npm 9.2.0 for resolute. RC4 requires an exact
target-specific package lock and successful signed APT dependency simulation;
these catalog entries do not prove every dependency is currently downloadable.
