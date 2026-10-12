#!/usr/bin/env bash
# Authorization and state-display checks; no real sudo or system mutations.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-frontend.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
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
export PATH="$work/bin:$PATH" ULI_TEST_MODE=1 ULI_ROOT=$work/root ULI_SUDO_LOG=$work/sudo-log
for selection in 1 2 3; do
  printf '%s\nnee\n' "$selection" | bash "$work/fixture/install.sh" > "$work/cancel-$selection"
  grep -q 'Installatie geannuleerd' "$work/cancel-$selection"
  [[ ! -e $ULI_ROOT && ! -e $ULI_SUDO_LOG ]]
done
printf '4\n' | bash "$work/fixture/install.sh" > "$work/status"
grep -q 'Installerversie: 1.0.0-bash.3' "$work/status"
printf '5\n' | bash "$work/fixture/install.sh" > "$work/exit"
printf 'geen\n0\n5\n' | bash "$work/fixture/install.sh" > "$work/invalid" 2>&1
[[ $(grep -c 'Ongeldige keuze' "$work/invalid") == 2 && ! -e $ULI_ROOT ]]
if (( EUID != 0 )); then
  for selection in 1 2 3; do
    printf '%s\nja\n' "$selection" | bash "$work/fixture/install.sh" > "$work/authorized-$selection"
    case $selection in 1) profile=app;; 2) profile=database;; 3) profile=combined;; esac
    grep -qx "$profile" "$ULI_SUDO_LOG"
    [[ ! -e $ULI_ROOT ]]
  done
fi
echo 'PASS menu 1-5, invalid input, explicit ja, cancellation and read-only preauthorization'
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
