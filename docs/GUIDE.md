# Operator guide

## Audit and plan

Use an unprivileged shell for audit. Use --json to save details in a new private file. A failing
inventory blocks installation. Candidate OS: Ubuntu 26.04, amd64/arm64; live
support on either architecture remains unverified. Minimum 1 CPU, 843 MiB RAM
and APP/DB/APP+DB 10/20/30 GiB free disk; these are test minima, not capacity
assurance. Execution adds only the swap deficit to 4 GiB on ext4/XFS during explicitly approved execution. Free disk reserves must remain after allocation.

A lock is schema 2 with apt, npm and updates maps. Apt names map to exact Debian
versions. Include every profile package, ca-certificates, and the full new or
changed dependency closure. APP additionally includes curl for its validator.
Unpinned dependencies, removals, downgrades or initial version conflicts stop.
No mutable latest/channel version is accepted. No guessed lock is shipped.
Review apt simulation and signed metadata on the target to construct the lock;
this release has no universal pre-resolved dependency closure.

Npm entries are @angular/cli (APP) and optionally @openai/codex (development
APP only), each with exact version and SHA256 of its package-lock.json. Provide
bundle/angular and optional bundle/codex directories, each containing a
package.json with only that exact direct dependency and a v3 package-lock.json
with registry.npmjs.org HTTPS URLs and SHA512 integrity for dependencies.
Angular 20 uses the explicitly selected Ubuntu Node 22.12+ LTS provider; major 24 is not a fallback.
Do not embed credentials, scripts, local paths, git URLs or mutable tags.

```json
{"schema":2,"apt":{"git":"EXACT-DEBIAN-VERSION"},"npm":{},"updates":{}}
```

This fragment describes structure only; it deliberately fails validation as
an incomplete lock. Resolve and review a complete target-specific lock first.

```sh
sh install.sh --profile APP --lock reviewed-lock.json > reviewed-plan.json
```

An explicit --system-updates flag is required when updates is nonempty.
Only its exact listed package versions are upgraded; no full/dist-upgrade.
Add --development for Codex. Use the same flags at execution.
Plan hashes bind the profile, pins, options, target identity digest and actions.
Protect saved plans privately. Inspect effects before granting INSTALL approval.

## Later manual installation — not performed during development

Confirm the exact target through an independent channel and a fresh restorable
snapshot. Use a new/disposable target; existing service/data directories or an
existing policy-rc.d are rejected. Review the source keyring and apt configuration.
Confirm sufficient space, current signed repository metadata, pinned versions,
network access to official feeds and npm, and no existing listener on 8080/5432.
A separate owner approval for the actual target is still mandatory.

```sh
sh install.sh --profile APP --plan reviewed-plan.json --execute \
  --npm-bundle reviewed-bundle --approval INSTALL:REVIEWED_PLAN_SHA256 \
  --snapshot-confirmed --allow-unvalidated
```

Run manually as root using the operator's normal privilege policy, or add --sudo
to the explicitly approved --execute command from an interactive terminal.
Sudo performs authorization itself; no password is read, stored or piped by the
installer. No askpass or stdin-password mode is allowed. Audit never invokes sudo.
RC4 plans use schema 4; regenerate and review older plans before execution. The example's hash placeholder is not valid approval.
No automatic reboot is performed. Reboot-required stops return WARN. Review and
reboot manually, then resume the same plan. A failed/pending step requires
--recovery-reviewed after effects have been checked. A process lock never grants
review or retries by itself. Different plans cannot adopt ownership state.

## Failure and repeat

JSON reports contain bounded error codes only. Private checkpoints reside under
/var/lib/universal-linux-installer/checkpoints. Preserve evidence and investigate
actual effects before retry. A pending package operation can leave installed
packages; revalidate before resuming. Existing exact versions are idempotent.
New configuration files are never replaced with different contents. Drift stops.
A failed package step retains /usr/sbin/policy-rc.d to block unattended package
service starts. Do not remove it blindly; review why execution stopped and either
resume the reviewed plan or repair/restore the target manually. Other package
maintenance is blocked by this guard until final validation removes it.

Successful final validation checks package pins, npm installed versions,
Nginx syntax/service/HTTP, .NET SDK, Node major, PostgreSQL readiness/version,
loopback binding and authentication settings. PASS means adapter validators
passed, not that live acceptance or production suitability was demonstrated.
No databases or database roles for an application are created. Codex authentication
is a separate manual user action. Tool paths are under
/opt/universal-linux-installer/{angular,codex}/node_modules/.bin/.

## Release verification

Download the versioned archive and SHA256SUMS from the matching GitHub release.
Verify SHA256SUMS against a separately trusted checksum before extracting.
`sha256sum -c SHA256SUMS` detects corruption; unsigned checksums do not establish
publisher identity. Never pipe an unverified downloaded script into a shell.
Inspect the archive, run tests, and use audit before any installation decision.
