# Primary sources

Reviewed during rc.3 development. Documentation support does not establish live
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
