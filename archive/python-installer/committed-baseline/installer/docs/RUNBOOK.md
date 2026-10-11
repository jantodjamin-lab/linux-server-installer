> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Operator runbook — development candidate 1.0.0-rc.1

1. Clone the feature branch and review the implementation and compatibility limits.
2. Verify release/SHA256SUMS from installer/release with `sha256sum -c SHA256SUMS`.
   Checksums detect corruption; they are not publisher signatures.
3. Run both offline suites from repository root:
   `python3 -B -W error::ResourceWarning -m unittest discover -s installer/tests`
   and `python3 -B -W error::ResourceWarning -m unittest discover -s tests`.
4. Run audit manually on an approved local machine with a chosen profile.
   JSON contains installed package versions and resource observations, no credentials.
   Store output privately. Unknown/unsupported system observations fail closed.
5. Do not interpret fixture PASS as installation readiness. No execute option exists.

## Recovery contract

Offline Engine uses injected disposable runners. Reopen does not resume a pending
step. Review actual effects first, then pass literal review=True. It performs no
rollback, database reset, reboot or service restart. Different binding, corrupt
checkpoint or existing-version conflict stops. Completed packages are revalidated.
The checkpoint is not authenticated or tamper resistant; do not use it as authority.
Do not put secrets into bundle metadata, package names, versions or checkpoint paths.

## Live gate — NO GO

Before any later manual installation: implement/review a least-privilege local
adapter, signed repository metadata, authenticated version lock, full dependency
closure, apt update/upgrade semantics, package maintainer-script policy, Node/Angular
compatibility, offline npm integrity, independent Nginx/PostgreSQL validators,
localhost DB binding and SCRAM policy, service/user conflicts, security updates,
reboot handling, and lock/concurrency protections. Test on disposable Ubuntu 26.04
VMs for each supported architecture. Current amd64/arm64 policy is a candidate only.

Owner must independently confirm target identity and a fresh restorable snapshot,
then explicitly approve manual installation. APP-O, TEST-O and production were
not changed. No SSH or remote execution is part of this installer. Firewall is
managed through TransIP; SSH, existing databases, accounts and services must never
be silently adopted. Codex remains optional and development-only; no login tokens
or API keys belong in a bundle. No public publication or merge is authorized.
