#!/usr/bin/env bash
# Authorization and state-display checks; no real sudo or system mutations.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-frontend.XXXXXXXX)
trap '[[ ${ULI_KEEP:-0} == 1 ]] || rm -rf -- "$work"' EXIT
mkdir -p "$work/fixture" "$work/bin"
cp "$base/install.sh" "$base/VERSION" "$work/fixture/"
cp -a "$base/bash" "$work/fixture/"
printf 'checks_system() { pass "Systeemcontroles fixture"; }\n' > "$work/fixture/bash/checks.sh"
printf 'swap_active_bytes() { echo 0; }\n' >> "$work/fixture/bash/swap.sh"
cat > "$work/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$ULI_SUDO_LOG"
MOCK
cat > "$work/bin/stat" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == -c && $2 == %u ]]; then echo 0; else /usr/bin/stat "$@"; fi
MOCK
chmod +x "$work/bin/"*
# Read-only host probes used by the preflight are mocked: disk, listeners, packages.
cat > "$work/bin/df" <<'MOCK'
#!/usr/bin/env bash
printf 'Avail\n%s\n' "${MOCK_DF_AVAIL:-107374182400}"
MOCK
cat > "$work/bin/ss" <<'MOCK'
#!/usr/bin/env bash
for port in ${MOCK_SS_PORTS:-}; do printf 'LISTEN 0 4096 0.0.0.0:%s 0.0.0.0:*\n' "$port"; done
MOCK
cat > "$work/bin/dpkg-query" <<'MOCK'
#!/usr/bin/env bash
package=${!#}
[[ " ${MOCK_INSTALLED:-} " == *" $package "* ]] || exit 1
printf 'install ok installed'
MOCK
chmod +x "$work/bin/"*
export PATH="$work/bin:$PATH" ULI_TEST_MODE=1 ULI_ROOT=$work/root ULI_SUDO_LOG=$work/sudo-log
version=$(cat "$base/VERSION")
menu() { printf '%b' "$1" | bash "$work/fixture/install.sh" > "$2" 2>&1; }
no_writes() { [[ ! -e $ULI_ROOT && ! -e $ULI_SUDO_LOG ]]; }

for selection in 1 2 3; do
  menu "$selection\nnee\n" "$work/cancel-$selection"
  grep -q 'Installatie geannuleerd' "$work/cancel-$selection"
  grep -q 'Controle-uitslag: PASS' "$work/cancel-$selection"
  grep -q 'Er is geen herstart nodig' "$work/cancel-$selection"
  no_writes
done
echo 'PASS every profile shows plan, read-only preflight and cancels on nee without writes'

menu '4\n' "$work/control"
for expected in 'Controle (read-only) voor alle profielen' 'Schijf APP:' 'Schijf DB:' 'Schijf APP + DB:' 'Controle-uitslag: PASS' "Installerversie: $version"; do
  grep -q "$expected" "$work/control"
done
bash "$work/fixture/install.sh" --audit > "$work/audit-flag" 2>&1
grep -q 'Controle-uitslag: PASS' "$work/audit-flag"
no_writes
echo 'PASS menu 4 and --audit run the same read-only control'

menu '0\n' "$work/exit"; grep -q 'Gestopt; er is niets gewijzigd' "$work/exit"
menu '5\n' "$work/exit-legacy"; grep -q 'Gestopt; er is niets gewijzigd' "$work/exit-legacy"
menu 'geen\n9\n0\n' "$work/invalid"
[[ $(grep -c 'Ongeldige keuze' "$work/invalid") == 2 ]]
eof_result=0; bash "$work/fixture/install.sh" < /dev/null > "$work/eof" 2>&1 || eof_result=$?
[[ $eof_result == 1 ]] && grep -q 'Geen menukeuze ontvangen' "$work/eof"
eof_result=0; printf '2\n' | bash "$work/fixture/install.sh" > "$work/eof-confirm" 2>&1 || eof_result=$?
[[ $eof_result == 1 ]] && grep -q 'Geen bevestiging ontvangen' "$work/eof-confirm"
no_writes
echo 'PASS stop 0/legacy 5, invalid input, EOF at menu and confirmation stop without writes'

blocked() {
  local result=0
  menu "$1\nja\n" "$2" || result=$?
  [[ $result == 1 ]] && grep -q 'Installatieplan geblokkeerd' "$2" && ! grep -q 'Bevestig installatie' "$2"
  no_writes
}
MOCK_DF_AVAIL=2147483648 blocked 2 "$work/low-disk"
grep -q 'nodig voor swap plus 1 GiB reserve' "$work/low-disk"
MOCK_DF_AVAIL=8589934592 menu '1\nnee\n' "$work/small-disk"
grep -q 'WARN  Schijf APP: 8.0 GiB vrij; advies minimaal 10 GiB' "$work/small-disk"
grep -q 'Installatie geannuleerd' "$work/small-disk"
MOCK_SS_PORTS=5432 blocked 2 "$work/port-db"
MOCK_SS_PORTS=443 blocked 1 "$work/port-app"
MOCK_SS_PORTS=443 blocked 3 "$work/port-combined"
MOCK_SS_PORTS=5432 MOCK_INSTALLED=postgresql-18 menu '2\nnee\n' "$work/existing-postgres"
grep -q 'PostgreSQL 18 is al aanwezig' "$work/existing-postgres" && grep -q 'Installatie geannuleerd' "$work/existing-postgres"
MOCK_SS_PORTS='80 443' MOCK_INSTALLED=nginx menu '1\nnee\n' "$work/existing-nginx"
grep -q 'Nginx is al geïnstalleerd' "$work/existing-nginx" && grep -q 'Installatie geannuleerd' "$work/existing-nginx"
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer"; chmod 700 "$ULI_ROOT/var/lib/universal-linux-installer"
: > "$ULI_ROOT/var/lib/universal-linux-installer/swapfile"
result=0; menu '2\nja\n' "$work/foreign-swap" || result=$?
[[ $result == 1 ]] && grep -q 'onbekend bestaand installer-swapbestand' "$work/foreign-swap"
[[ ! -s $ULI_ROOT/var/lib/universal-linux-installer/swapfile && ! -e $ULI_SUDO_LOG ]]
rm -rf "$ULI_ROOT"
echo 'PASS low disk, port conflicts and unknown swapfile STOP before confirmation; small disk and existing services WARN'

# Non-root flows: real unprivileged user, mocked sudo; and a PATH without sudo.
as_user=()
if (( EUID == 0 )) && command -v runuser >/dev/null && id nobody >/dev/null 2>&1; then
  chmod 755 "$work" "$work/fixture" "$work/bin"
  as_user=(runuser -u nobody --)
fi
mkdir -p "$work/userlogs"; chmod 1777 "$work/userlogs"
if (( EUID == 0 )) && (( ${#as_user[@]} == 0 )); then :
fi
if (( EUID != 0 )) || (( ${#as_user[@]} )); then
  for selection in 1 2 3; do
    printf '%s\nja\n' "$selection" | "${as_user[@]}" env PATH="$PATH" ULI_TEST_MODE=1 ULI_ROOT="$ULI_ROOT" ULI_SUDO_LOG="$work/userlogs/sudo-log-$selection" bash "$work/fixture/install.sh" > "$work/authorized-$selection" 2>&1 || true
    case $selection in 1) profile=app;; 2) profile=database;; 3) profile=combined;; esac
    grep -qx "$profile" "$work/userlogs/sudo-log-$selection"
    grep -qx -- '--yes' "$work/userlogs/sudo-log-$selection"
    grep -q 'sudo wordt pas na uw bevestiging gevraagd' "$work/authorized-$selection"
    [[ ! -e $ULI_ROOT ]]
  done
  printf '1\nnee\n' | "${as_user[@]}" env PATH="$PATH" ULI_TEST_MODE=1 ULI_ROOT="$ULI_ROOT" ULI_SUDO_LOG="$work/userlogs/sudo-log-nee" bash "$work/fixture/install.sh" > "$work/user-cancel" 2>&1
  [[ ! -e $work/userlogs/sudo-log-nee ]]
  mkdir -p "$work/nosudo"
  for tool in /usr/bin/* /bin/*; do
    name=${tool##*/}
    [[ $name == sudo || -e $work/nosudo/$name ]] || ln -s "$tool" "$work/nosudo/$name"
  done
  for tool in df ss dpkg-query stat; do ln -sf "$work/bin/$tool" "$work/nosudo/$tool"; done
  chmod 755 "$work/nosudo"
  result=0
  printf '2\nja\n' | "${as_user[@]}" env PATH="$work/nosudo" ULI_TEST_MODE=1 ULI_ROOT="$ULI_ROOT" bash "$work/fixture/install.sh" > "$work/no-sudo" 2>&1 || result=$?
  [[ $result == 1 ]] && grep -q 'Rechten: sudo ontbreekt' "$work/no-sudo" && ! grep -q 'Bevestig installatie' "$work/no-sudo"
  echo 'PASS non-root: sudo only after explicit ja; nee never calls sudo; missing sudo stops before confirmation'
else
  echo 'WARN non-root authorization tests skipped: no unprivileged user available'
fi
source "$base/bash/common.sh"
source "$base/bash/state.sh"
VERSION=1.0.0-bash.3 PROFILE=app STATUS=running CURRENT=codex COMPLETED='system plan swap app_packages'
STARTED=2026-10-12T00:00:00Z ENDED='' LAST_ERROR=''
mkdir -p "$STATE_DIR"
state_save
state_load
[[ $STARTED == 2026-10-12T00:00:00Z && $CURRENT == codex && $(state_progress) == '4/8 (50%)' ]]
grep -q 'Voortgang: 4/8 (50%)' "$ULI_ROOT/var/lib/universal-linux-installer-status/status"
[[ $(stat -c %a "$ULI_ROOT/var/lib/universal-linux-installer-status/status") == 644 ]]
cp "$STATE_FILE" "$work/state-good"
sed '/^started=/d; /^ended=/d; /^error=/d' "$work/state-good" > "$STATE_FILE"
state_load
[[ -z $STARTED && -z $ENDED && -z $LAST_ERROR ]]
cp "$work/state-good" "$STATE_FILE"
printf 'error=duplicate\n' >> "$STATE_FILE"
if state_load; then exit 1; fi
sed 's/^started=.*/started=untrusted/' "$work/state-good" > "$STATE_FILE"
if state_load; then exit 1; fi
sed 's/^current=.*/current=unknown_phase/' "$work/state-good" > "$STATE_FILE"
if state_load; then exit 1; fi
cp "$work/state-good" "$STATE_FILE"
bash "$work/fixture/install.sh" --status > "$work/state-view"
grep -q '4/8 (50%)' "$work/state-view"
cmp "$STATE_FILE" "$work/state-good"
bash "$work/fixture/install.sh" --audit > "$work/audit"
cmp "$STATE_FILE" "$work/state-good"
echo 'PASS backward 6-field state, strict 9-field metadata, sanitized progress snapshot and read-only status/audit'
# Real signal handling with only the privilege reexec guard replaced. All state
# paths stay under the explicit test root; no privileged host operation occurs.
cp -a "$work/fixture" "$work/rootfixture"
# Historical migration fixture: only BASH.2 -> BASH.3 is authorized.
printf '1.0.0-bash.3\n' > "$work/rootfixture/VERSION"
sed 's/if (( EUID != 0 )); then/if false; then/' "$work/fixture/install.sh" > "$work/rootfixture/install.sh"
export ULI_ROOT=$work/signal-root
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer"
chmod 700 "$ULI_ROOT/var/lib/universal-linux-installer"
printf 'profile=app\nversion=1.0.0-bash.2\ncompleted=app\ncurrent=\nstatus=complete\nupdated=2026-10-12T00:00:00Z\n' > "$ULI_ROOT/var/lib/universal-linux-installer/state"
chmod 600 "$ULI_ROOT/var/lib/universal-linux-installer/state"
cp "$ULI_ROOT/var/lib/universal-linux-installer/state" "$work/signal-before"
cat >> "$work/rootfixture/bash/progress.sh" <<'SIGNAL_FIXTURE'
progress_init() { kill -TERM "$BASHPID"; }
SIGNAL_FIXTURE
signal_result=0
bash "$work/rootfixture/install.sh" --profile app --yes > "$work/signal-output" 2>&1 || signal_result=$?
[[ $signal_result == 143 ]]
cmp "$work/signal-before" "$ULI_ROOT/var/lib/universal-linux-installer/state"
[[ ! -e $ULI_ROOT/var/lib/universal-linux-installer/installer-1.0.0-bash.3 ]]
grep -q 'oorspronkelijke status behouden' "$work/signal-output"
echo 'PASS real TERM during pre-unit migration setup preserves original bash.2 state'
# Use the production owner declaration and handler, not a reimplementation.
awk '/^readonly INSTALLER_OWNER_PID=/ {print} /^installer_error\(\) \{/ {capture=1} capture {print} capture && /^}$/ {exit}' "$base/install.sh" > "$work/actual-error-handler.sh"
grep -q '^readonly INSTALLER_OWNER_PID=' "$work/actual-error-handler.sh"
grep -q '^installer_error() {' "$work/actual-error-handler.sh"
cat > "$work/error-owner-fixture.sh" <<'OWNER_FIXTURE'
#!/usr/bin/env bash
set -Eeuo pipefail
source "$ULI_HANDLER_BASE/bash/common.sh"
source "$ULI_HANDLER_BASE/bash/state.sh"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
VERSION=1.0.0-bash.3 PROFILE=app STATUS=complete CURRENT='' COMPLETED='system plan swap app_packages codex nginx resume verification'
STARTED=2026-10-12T00:00:00Z ENDED=2026-10-12T00:01:00Z LAST_ERROR=''
migration_preparing=0
state_save
source "$ULI_HANDLER_SOURCE"
trap 'installer_error "$?"' ERR
case $1 in
  asynchronous)
    # Background renderer-like failures inherit ERR but do not own the lock.
    ( sleep 0.1; false ) & child=$!
    child_status=0
    wait "$child" || child_status=$?
    [[ $child_status == 1 ]]
    grep -qx 'status=complete' "$STATE_FILE"
    grep -qx 'Status: COMPLETE' "$ROOT/var/lib/universal-linux-installer-status/status"
    ;;
  synchronous)
    # A command substitution fails in a descendant and then its nonzero status
    # reaches the assignment in the real owner; this must still record FAIL.
    CURRENT=codex
    ignored=$(false)
    printf 'UNREACHABLE %s\n' "$ignored"
    ;;
  *) exit 2;;
esac
OWNER_FIXTURE
export ULI_HANDLER_BASE=$base ULI_HANDLER_SOURCE=$work/actual-error-handler.sh
ULI_ROOT=$work/async-owner-root bash "$work/error-owner-fixture.sh" asynchronous > "$work/async-owner-output" 2>&1
grep -qx 'status=complete' "$work/async-owner-root/var/lib/universal-linux-installer/state"
echo 'PASS actual asynchronous ERR descendant cannot overwrite persisted COMPLETE or public status'
synchronous_result=0
ULI_ROOT=$work/sync-owner-root bash "$work/error-owner-fixture.sh" synchronous > "$work/sync-owner-output" 2>&1 || synchronous_result=$?
[[ $synchronous_result == 1 ]]
grep -qx 'status=failed' "$work/sync-owner-root/var/lib/universal-linux-installer/state"
grep -qx 'error=step_codex_exit_1' "$work/sync-owner-root/var/lib/universal-linux-installer/state"
grep -qx 'Status: FAIL' "$work/sync-owner-root/var/lib/universal-linux-installer-status/status"
[[ $(grep -c 'FAIL Stap codex onderbroken' "$work/sync-owner-output") == 1 ]]
if grep -q 'UNREACHABLE' "$work/sync-owner-output"; then exit 1; fi
echo 'PASS synchronous child failure reaches owning process and records exactly one FAILED state'
# A host completed by an earlier release is never silently re-run by this one.
cp -a "$work/fixture" "$work/upgradefixture"
cp "$base/VERSION" "$work/upgradefixture/VERSION"
sed 's/if (( EUID != 0 )); then/if false; then/' "$base/install.sh" > "$work/upgradefixture/install.sh"
export ULI_ROOT=$work/upgrade-root
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer"
chmod 700 "$ULI_ROOT/var/lib/universal-linux-installer"
printf 'profile=database\nversion=1.0.0-bash.4\ncompleted=system plan swap postgres database_check resume verification\ncurrent=\nstatus=complete\nupdated=2026-10-12T00:00:00Z\n' > "$ULI_ROOT/var/lib/universal-linux-installer/state"
chmod 600 "$ULI_ROOT/var/lib/universal-linux-installer/state"
cp "$ULI_ROOT/var/lib/universal-linux-installer/state" "$work/upgrade-before"
for attempt in first second; do
  result=0
  bash "$work/upgradefixture/install.sh" --profile database --yes > "$work/upgrade-$attempt" 2>&1 || result=$?
  [[ $result == 1 ]]
  grep -q 'Bestaande status gebruikt een andere installerversie' "$work/upgrade-$attempt"
  cmp "$work/upgrade-before" "$ULI_ROOT/var/lib/universal-linux-installer/state"
done
result=0
bash "$work/upgradefixture/install.sh" --profile app --yes > "$work/upgrade-profile" 2>&1 || result=$?
[[ $result == 1 ]] && grep -q 'Bestaand profiel verschilt' "$work/upgrade-profile"
cmp "$work/upgrade-before" "$ULI_ROOT/var/lib/universal-linux-installer/state"
echo 'PASS repeated run over an older release or other profile is a hard STOP with unchanged state'

# Secrets from the operator environment never appear in plan or control output.
export ULI_ROOT=$work/secret-root
PGPASSWORD=uli-secret-value-1 GITHUB_TOKEN=uli-secret-value-2 menu '4\n' "$work/secret-control"
PGPASSWORD=uli-secret-value-1 GITHUB_TOKEN=uli-secret-value-2 menu '3\nnee\n' "$work/secret-plan"
if grep -q 'uli-secret-value' "$work/secret-control" "$work/secret-plan"; then exit 1; fi
echo 'PASS plan and control output contain no environment secrets'
