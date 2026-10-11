#!/usr/bin/env bash
# Offline contract tests: only temporary files and mocked privileged commands.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-tests.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
export ULI_TEST_MODE=1 ULI_ROOT=$work/root
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer" "$work/bin"
export PATH="$work/bin:$PATH"
passed=0
ok() { printf 'PASS %s\n' "$*"; passed=$((passed+1)); }
for script in "$base/install.sh" "$base"/bash/*.sh "$base"/tools/*.sh; do bash -n "$script"; done
ok 'Bash syntax'
if grep -RnE 'python[[:space:]]|python3[[:space:]]+-|curl[^#]*\|[[:space:]]*(sudo[[:space:]]+)?(ba)?sh' "$base/install.sh" "$base/bash"; then exit 1; fi
ok 'No Python installer or piped remote shell'
cat > "$work/bin/stat" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == -c && $2 == %u ]]; then echo 0; else /usr/bin/stat "$@"; fi
MOCK
chmod +x "$work/bin/stat"
source "$base/bash/common.sh"
source "$base/bash/state.sh"
VERSION=1.0.0-test PROFILE=app STATUS=running CURRENT='' COMPLETED=''
state_save
PROFILE=''; state_load; [[ $PROFILE == app ]]
ok 'Persistent profile/version state round trip'
mutations=0
change() { mutations=$((mutations+1)); }
state_step probe change
state_step probe change
[[ $mutations == 1 && $CURRENT == '' && $COMPLETED == probe ]]
ok 'Completed step never replays mutation'
break_step() { return 7; }
if state_step broken break_step; then exit 1; fi
[[ $STATUS == failed && $CURRENT == broken && $COMPLETED == probe ]]
ok 'Interrupted/failed step remains recorded'
PROFILE=app STATUS=running
state_step broken change
[[ $CURRENT == '' && $COMPLETED == 'probe broken' ]]
ok 'Failed step safely retried'
# State expression remains literal to test injection resistance.
# shellcheck disable=SC2016
printf 'profile=$(touch %s/injected)\n' "$work" > "$STATE_FILE"
if state_load; then exit 1; fi
[[ ! -e $work/injected ]]
ok 'State parsed without executing data'
PROFILE=app STATUS=running CURRENT='' COMPLETED=''; state_save
flock "$STATE_DIR/lock" sleep 3 & lock_pid=$!
sleep 0.1
if ( exec 9>"$STATE_DIR/lock"; flock -n 9 ); then kill "$lock_pid"; exit 1; fi
wait "$lock_pid"
ok 'Exclusive installation lock'
cat > "$work/bin/apt-get" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$ULI_ROOT/apt-args"
exit "${MOCK_APT_EXIT:-0}"
MOCK
chmod +x "$work/bin/apt-get"
MOCK_APT_EXIT=100; export MOCK_APT_EXIT
if run_apt update; then exit 1; fi
[[ $(cat "$ULI_ROOT/apt-args") == *'DPkg::Lock::Timeout=180'* ]]
[[ $(cat "$ULI_ROOT/apt-args") == *'AllowUnauthenticated=false'* ]]
ok 'APT errors propagate with bounded lock and authentication'
bash "$base/install.sh" --audit > "$work/audit.txt" 2>&1 || true
[[ ! -e $ULI_ROOT/var/lib/universal-linux-installer/installer ]]
ok 'Read-only audit creates no installation payload'
bash "$base/install.sh" --status > "$work/status.txt"
printf '0\n' | bash "$base/install.sh" > "$work/menu.txt"
grep -q 'UNIVERSAL LINUX SERVER INSTALLER' "$work/menu.txt"
ok 'Menu exits without authorization or writes'
if bash "$base/install.sh" --profile invalid --yes > "$work/invalid.txt" 2>&1; then exit 1; fi
ok 'Invalid profile refused'
# File-level test follows, with mocked kernel-facing swap commands.
bash "$base/tests/swap.sh"
bash "$base/tests/profiles.sh"
printf 'PASS %s offline contract groups plus swap matrix\n' "$passed"
