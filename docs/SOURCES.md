# Primary sources

Reviewed during rc.2 development. Documentation support does not establish live
installation acceptance. Exact target locks and disposable-VM validation remain
required. No copied vendor installer or mutable curl-to-shell script is used.

- [.NET on Ubuntu](https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-install): Ubuntu 26.04 distro .NET 10 packages.
- [PostgreSQL Ubuntu packages](https://www.postgresql.org/download/linux/ubuntu/): Ubuntu resolute and PostgreSQL package availability. This installer uses approved Ubuntu feeds only; no PGDG repository is imported.
- [Angular compatibility](https://angular.dev/reference/versions): Angular 20 and Node 22.12+ or 24 compatibility range used by this candidate.
- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli): optional @openai/codex package. Exact reviewed version required; no login setup.

APT package signature/dependency behavior and npm integrity are exercised through
bounded command doubles offline. No claim of verified live apt/npm transaction
or official package artifact authentication from offline fixtures is made.
