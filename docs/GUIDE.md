# Operator guide

## Read-only inspection

```sh
sh install.sh --profile APP+DB --audit
sh install.sh --profile APP+DB --audit --json
```

Fresh Ubuntu 26.04 amd64/arm64 only. Admission minima are 1 CPU, 843 MiB physical
RAM, 10/20/30 GiB disk reserve for APP/DB/APP+DB AFTER swap. Recommended RAM is
2/2/4 GiB. These are disposable-test minima; 843 MiB is insufficient for reliable
APP+DB builds/runtime even with swap. Only writable ext4/XFS may add a swap file.
Existing swap counts toward 4 GiB and is never resized/disabled/removed.

Source policy, Canonical keys, cached signatures and candidates appear separately.
A refused mirror no longer causes a not-checked cascade. Index >7 days old gives
WARN with Date/mtime/stamp details in JSON: candidates/closure remain unreliable
until authorized refresh. Missing nodejs/npm before refresh is not evidence they
will become available. Missing gpg: manually authorize prerequisite installation;
see audit remedy. The installer does not initialize ~/.gnupg.

For an exact public provider URI shown in diagnostics:

```sh
sh install.sh --profile APP+DB --audit --allow-mirror https://mirror.example/ubuntu/path
```

Use the ACTUAL URI, including scheme and path, not this placeholder. Repeat for
additional URIs. HTTP requires explicit opt-in too. Ports/wildcards/userinfo/query
and fragments are refused. Signatures are still required for every InRelease.
Captured provider source fixtures must be supplied by their owner; synthetic
fixtures never establish compatibility with an unseen provider configuration.

## Apply with one typed INSTALL confirmation

On an independently verified fresh disposable target with restorable snapshot:

```sh
sh install.sh --profile APP+DB --apply --sudo --snapshot-confirmed --allow-unvalidated
```

The flags explicitly acknowledge snapshot and candidate risk. Without them,
there are separate yes/no questions BEFORE the INSTALL confirmation. Sudo may
also prompt for its own authorization; the installer never reads that password.
Add `--development` for the shipped optional Codex pin (APP profiles only).
Cloud-image upgrades often require `--system-updates`; this must be explicit.
Add the same reviewed `--allow-mirror URI` exceptions used during audit.

The operator types `INSTALL <first 12 characters of authorization hash>` on the
TTY. This binds installation intent and limits, NOT a fabricated/stale package
lock. No target writes occur before this confirmation. Afterwards: wait for
cloud-init (default), warn about unattended upgrades, append only missing universe
components if needed, refresh signed indexes, resolve exact closure and self-test
through executor preflight. Exceeding limits stops before swap/packages/services.
`--max-new-packages` defaults to 1000 and `--max-updates` to 100; updates are still
forbidden without `--system-updates`. No broad full/dist-upgrade is performed.
`--no-wait-cloud-init` explicitly disables waiting, at the operator's discretion.

A compact resolved summary shows counts, upper-bound package sizes, swap deficit,
npm pins and exact plan hash. It and lock.json/plan.json are stored root-only in
`/var/lib/universal-linux-installer/checkpoints/<authorization-hash>/` (0700/0600).
Package-size estimates exclude npm/swap; unavailable size metadata is unknown.
All packages are installed as one exact closure, with no-remove/no-downgrade.
Target npm locks come from bundle/angular and bundle/codex automatically; override
with `--npm-bundle DIR` only when matching the reviewed profiles/npm-pins.json.
Behind a proxy, explicitly add `--allow-proxy-env`; credentials are not persisted.

Noninteractive: supply `--approval INSTALL:<full-authorization-hash>`, snapshot
and candidate flags. The printed bounded intent must match exactly. There is no
auto-yes flag, default acceptance or silent expansion of limits/source policy.

## Separate resolution/review/execution

Resolution intentionally WRITES metadata, unlike audit. Run as root, or use
interactive --sudo:

```sh
sh install.sh --profile APP --resolve --out /root/installer-review --refresh-metadata --sudo --system-updates
sh install.sh --profile APP --execute --plan /root/installer-review/plan.json \
  --approval INSTALL:EXACT_PLAN_HASH --snapshot-confirmed --allow-unvalidated --sudo --system-updates
```

Repeat matching development/mirror/proxy options. The first flag is explicit
refresh authorization only; the second INSTALL binds the exact resolved plan.
Manual schema-2 locks use `--lock FILE` and the same workflow/validation path.
Schema-5 plans have a UTC created_at and expire after 2h. Schema-4 plans are refused:
regenerate rather than changing schema/hash manually. Expired partial installations
need reviewed recovery; never replace their ownership marker to adopt a new plan.

## Diagnostics, interruption and repeat

Exit codes: 0 PASS/WARN, 1 failure, 2 argument error, 130 cancellation.
`--show-diagnostics` prints the redacted private failure tail to stderr only.
Stdout/JSON and journal events hold bounded code + step + command + exit status.
Preserve checkpoints/diagnostics (root-only). A safe network/read-only interruption
clears pending automatically; packages/swap/config/npm/validate require explicit
`--recovery-reviewed` AFTER inspecting effects. SIGKILL safe-step recovery follows
the same rule on next invocation. Completed steps revalidate; drift stops.

Re-run the SAME --apply options within 2h to resume/revalidate the SAME saved plan.
A fully completed, root-owned checkpoint may also be revalidated after expiry.
Its journal digest, plan binding, ownership and every completed step must match;
this exception authorizes no new effects. Partial or interrupted plans still expire.
A successful repeat does not reinstall packages/npm or allocate/edit swap again.
No automatic reboot: WARN manual-reboot-required requires operator review/reboot
then resume. The policy-rc.d guard remains after failure; do not remove blindly.
Other package maintenance may remain blocked until approved recovery completes.
A failed resolver summary gives a bounded cause without requiring the owner to
guess stderr. Incomplete preparation also has its own journal and retry classes.

Nginx: 127.0.0.1:8080; PostgreSQL: localhost:5432, SCRAM/peer. Tool binaries are
under /opt/universal-linux-installer/{angular,codex}/node_modules/.bin. No database
roles/application deployment/login/network opening is included.

## Validation layers and development

Layer 1: `python3 -B -W error::ResourceWarning -m unittest discover -s tests`.
Layer 2: `docker run --rm -v "$PWD:/work" -w /work ubuntu:26.04 sh tools/container-test.sh`
(installs packages ONLY in the disposable container). The script checks real
signed metadata and resolvers for every profile plus Ubuntu npm9 npm-ci. Container
resource/systemd admission is synthetic; no service/swap e2e claim follows.
Layer 3: `sh tools/e2e-vm.sh APP` (local KVM or QEMU TCG; prerequisites are checked without host installation).
See docs/ARCHITECTURE.md for scenarios and retained artifacts, and
docs/CI_VALIDATION.md for security/fault matrix dispatch instructions. Neither unit nor
container PASS changes NOT LIVE VALIDATED. Owner acceptance remains required.

Generate public npm locks in development/CI with explicit versions:
`python3 -B tools/make-npm-bundle.py --angular 20.3.39 --codex 0.128.0`.
Manual refresh-npm-lock CI opens a review PR, never auto-merges it.

Build: `python3 -B release/build.py`; generated tarballs are ignored by Git and
belong in GitHub Releases. Verify SHA256SUMS against an independently trusted
checksum, inspect/extract the archive and audit. Never pipe a download into sh.
