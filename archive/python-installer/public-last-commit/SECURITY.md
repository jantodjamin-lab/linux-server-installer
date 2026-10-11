> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; do not use these commands for installation.

# Security boundaries

This candidate remains **NIET LIVE GEVALIDEERD** until the owner separately accepts
a successful disposable VM test. No SSH/remote, production, firewall changes,
SSH configuration, automatic reboot or automatic rollback is implemented.

Audit/dry-run reads only: no apt cache/index, source, fstab, swap, journal, npm
cache or Python bytecode writes. GPG uses an explicit installed keyring with
`--homedir /nonexistent`, no default keyring, no trustdb checks or locking.
It never creates a homedir/keybox/lock/trustdb. Missing gpg is a hard, actionable
audit stop: explicitly arrange `apt-get install gpg` before using the installer.
The installer never installs its own trust-verification prerequisites.

Apply authorizes a schema-5 intent before ANY target write, including metadata
refresh. Its hash binds profile, target identity, source bindings, explicitly
allowed mirror URIs, npm pins, proxy/cloud-init options and package/update limits.
Snapshots and acceptance of this unvalidated candidate require explicit flags or
separate affirmative answers; the final typed confirmation has no default.
`--resolve --out DIR --refresh-metadata` is a separate explicit refresh-only
authorization. Its saved plan still needs full INSTALL approval for execution.
Saved plans are exact, integrity-bound and expire after two hours. Schema 4 is
refused. A fully completed checkpoint may be revalidated after expiry only when
its root ownership, private modes, digest, exact binding and full completed-step
set match. This permits no new effects; partial installations still expire.
Limit overflow stops before package installation, swap or service changes;
authorized metadata refresh and an owned universe extension may already exist.

Only supported resolute suites and the installed Ubuntu archive keyring are
accepted. Canonical fingerprints remain allowlisted. Every configured InRelease
is independently verified by gpgv with the pinned 2018 archive fingerprint, and
APT checks dates/expiry, signed hashes and package authenticity. No PPA, imported
key, unauthenticated/weak repository, downgrade, removal, latest/version fallback
or unpinned changed dependency is accepted. Package scripts are privileged code.

Non-Canonical mirrors are refused by default. `--allow-mirror URI` opts into one
exact http(s) host/path; no wildcard, credentials, port, query or fragment is
accepted. HTTP is an explicit operator choice; cryptographic signatures remain
the trust anchor. Mirror errors include the bounded public host and remedy.
Rejecting URI policy never suppresses independent key/signature/candidate checks.
Index age (header Date, mtime and update-success stamp) is advisory, never proof
of integrity/freshness or of an installable closure. Audit never refreshes it.

APT simulates the complete profile closure after an authorized refresh, validates
exact pins through the same executor, and refuses Remv/downgrades. Updates require
`--system-updates`. One combined pinned transaction avoids splitting dependencies
between new packages and updates. `--no-remove`, no recommendations and a 600s
DPkg lock timeout remain active. Cloud-init waiting follows authorization.

Npm bundles contain public metadata only: one exact direct dependency, no root
scripts, v3 lock, registry.npmjs.org HTTPS, SHA512 SRI per dependency, and pinned
lock SHA256. Target uses npm ci with lifecycle scripts disabled, no audit/fund,
and a private prefix. Locks are generated only in development/CI, never on target.
No Codex login or API token is configured. npm user/global config is isolated.

Fresh-target checks refuse existing service config/data or policy-rc.d. A guard
blocks package service starts until explicit configuration and final validation.
Nginx listens on loopback 8080; PostgreSQL on localhost with SCRAM TCP and peer
Unix authentication. No external ingress, application deployment, database users,
passwords, TLS issuance or firewall opening is included.

Root-only journals use private 0700 directories, 0600 atomic/fsynced files,
process locks, checksums, plan/host binding and revalidation. Temporary test roots
are injectable for unprivileged unit tests; the CLI exposes no alternate root.
Readonly/idempotent failed or interrupted steps auto-clear pending state; unknown
package/config/swap/npm/validate effects require `--recovery-reviewed`. Failed
state is retained; no rollback or automatic removal is attempted. Plan expiry
never grants recovery/adoption of a different plan. Preserve partial installs.

Commands expose only bounded code, binary/subcommand and exit status. Stderr
is redacted BEFORE truncation (4KiB maximum) and stored only in private diagnostic
logs. Events/stdout/JSON contain no stderr. `--show-diagnostics` prints redacted
logs to stderr. Redaction is defense in depth, not a guarantee about arbitrary
application output. Treat all diagnostic artifacts as private.

Sudo owns the terminal/password prompt; no password API, storage, -S, askpass or
captured authentication output. Proxy variables are stripped unless explicitly
opted in with `--allow-proxy-env`; only HTTP(S)_PROXY/NO_PROXY and lowercase forms
are forwarded. Proxy values/credentials are never persisted in a plan/report.
The trusted administrator controls root, package policy and keyring; this is not
a sandbox against a malicious administrator. Public exports contain no private
history, host identity, internal names/IPs, journals or credentials.
