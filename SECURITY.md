# Security boundaries

Default audit is read-only. Execute needs a reviewed plan, its exact INSTALL
hash, matching local machine identity, root, explicit snapshot confirmation and
explicit acknowledgement of this unvalidated release candidate. These flags
are operator statements, not identity authentication or proof of a backup.

Only Ubuntu archive/security/ports feeds and resolute suites are accepted.
APT validates signatures against the installed Ubuntu keyring. No key is
imported, no PPA added, and no insecure apt flag is enabled. HTTP mirrors are
permitted because signed apt metadata authenticates package hashes. Full apt
simulation must match pinned changes, including every new/changed dependency.
Ubuntu package maintainer scripts remain trusted privileged code.

Npm registry URLs must use HTTPS, have no credentials/query, and include SHA512
integrity in a reviewed lockfile. npm ci disables lifecycle scripts and uses a
private installer prefix. No Codex login or API token is read or configured.
Locks contain public package metadata only. Do not include sensitive information.

Fresh targets only: existing service configuration/data or an existing service
start policy blocks initial execution. A package-service-start guard prevents
premature starts. Explicit service activation happens only after configuration.
Nginx listens on loopback 8080; PostgreSQL uses localhost and SCRAM for TCP,
peer for Unix sockets. No external ingress, application deployment, database
account/password generation, TLS certificate issuance or firewall opening is
included. These require a separately reviewed application/network deployment.

A private journal uses atomic fsync writes, exclusive process lock, content
checksum and plan binding. It detects accidental tampering, not a malicious
root user or rollback to a prior consistent journal. Unknown pending effects
require manual review; completed steps are revalidated. No destructive rollback.
Arbitrary process stderr is suppressed to prevent credentials entering reports.

The trusted local administrator controls root, apt configuration and keyring.
This installer is not a sandbox against a compromised administrator/host.
No secrets, private history, environment credentials or target identity records
are included in the public release. Report security issues privately to the
repository owner; do not post credentials or internal host details in issues.
