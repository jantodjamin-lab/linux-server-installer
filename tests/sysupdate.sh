#!/usr/bin/env bash
# shellcheck disable=SC2016 # fixture code is written literally into mock files
# Menu 5 / --system-update with mocked apt-get, apt-cache, dpkg, dpkg-query,
# apt-mark, df and sudo. No real package index, upgrade, reboot or sudo.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-sysupdate.XXXXXXXX)
trap '[[ ${ULI_KEEP:-0} == 1 ]] || rm -rf -- "$work"' EXIT
mkdir -p "$work/fixture" "$work/bin" "$work/fixtures"
cp "$base/install.sh" "$base/VERSION" "$work/fixture/"
cp -a "$base/bash" "$work/fixture/"
printf 'checks_system() { [[ ${MOCK_CHECKS_FAIL:-0} == 0 ]] || { fail "Systeemcontroles fixture"; return 1; }; pass "Systeemcontroles fixture"; }\n' > "$work/fixture/bash/checks.sh"
printf 'PRETTY_NAME="Ubuntu 26.04.1 LTS"\n' > "$work/fixtures/os-release"
sim() { # name old new ...
  local name old new
  while (( $# )); do name=$1 old=$2 new=$3; shift 3
    if [[ $old == - ]]; then printf 'Inst %s (%s Ubuntu:26.04/resolute-updates [amd64])\n' "$name" "$new"
    else printf 'Inst %s [%s] (%s Ubuntu:26.04/resolute-updates [amd64])\n' "$name" "$old" "$new"; fi
  done
}
cat > "$work/bin/apt-get" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MOCK_LOG"
simulate=0 action=''
for argument in "$@"; do
  case $argument in -s|--simulate) simulate=1;; update|upgrade|install|dist-upgrade|full-upgrade|autoremove) action=$argument;; esac
done
# Credential-bearing source lines (update/simulation) must never reach logs, reports or the console.
[[ $action == upgrade && $simulate == 0 ]] || printf 'Hit:1 https://user:uli-apt-secret@mirror.invalid/ubuntu resolute InRelease\n'
if (( simulate )); then
  if [[ -e $MOCK_STATE/updated ]]; then cat "$MOCK_SIM_AFTER"; else cat "$MOCK_SIM_BEFORE"; fi
  exit "${MOCK_SIM_EXIT:-0}"
fi
case $action in
  update) [[ ${MOCK_UPDATE_EXIT:-0} == 0 ]] || exit "$MOCK_UPDATE_EXIT"; : > "$MOCK_STATE/updated";;
  upgrade)
    if [[ ${MOCK_UPGRADE_PARTIAL:-0} == 0 ]]; then
      sed -nE 's/^Inst ([^ ]+) (\[[^]]+\] )?\(([^ ]+).*/\1 \3/p' "$MOCK_SIM_AFTER" >> "$MOCK_STATE/dpkgdb"
    fi
    [[ ${MOCK_REBOOT:-0} == 0 ]] || { mkdir -p "$ULI_ROOT/run"; : > "$ULI_ROOT/run/reboot-required"; }
    [[ ${MOCK_AUDIT_AFTER:-0} == 0 ]] || : > "$MOCK_STATE/audit-dirty"
    exit "${MOCK_UPGRADE_EXIT:-0}";;
esac
MOCK
cat > "$work/bin/apt-cache" <<'MOCK'
#!/usr/bin/env bash
printf ' 500 https://mirror.invalid/ubuntu resolute/main amd64 Packages\n     release v=26.04,o=%s,a=resolute,n=resolute,l=Ubuntu,c=main,b=amd64\n' "${MOCK_ORIGIN:-Ubuntu}"
MOCK
cat > "$work/bin/dpkg" <<'MOCK'
#!/usr/bin/env bash
[[ $1 == --audit ]] || exit 2
if [[ -n ${MOCK_DPKG_AUDIT:-} || -e $MOCK_STATE/audit-dirty ]]; then printf 'The following packages are only half configured\n'; fi
MOCK
cat > "$work/bin/dpkg-query" <<'MOCK'
#!/usr/bin/env bash
package=${!#}
version=$(awk -v p="$package" '$1==p {v=$2} END {print v}' "$MOCK_STATE/dpkgdb")
[[ -n $version ]] || exit 1
printf '%s' "$version"
MOCK
cat > "$work/bin/apt-mark" <<'MOCK'
#!/usr/bin/env bash
[[ $1 == showhold ]] && printf '%s\n' ${MOCK_HOLDS:-}
MOCK
cat > "$work/bin/df" <<'MOCK'
#!/usr/bin/env bash
printf 'Avail\n%s\n' "${MOCK_DF_AVAIL:-107374182400}"
MOCK
cat > "$work/bin/stat" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == -c && $2 == %u ]]; then echo 0; else /usr/bin/stat "$@"; fi
MOCK
cat > "$work/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MOCK_SUDO_LOG"
[[ ${MOCK_SUDO_FAIL:-0} == 0 ]] || exit 1
[[ $1 == -- ]] && shift
ULI_TEST_PRIVILEGED=1 exec "$@"
MOCK
for command in reboot shutdown systemctl; do
  printf '#!/usr/bin/env bash\nprintf "%%s %%s\\n" %s "$*" >> "$MOCK_FORBIDDEN_LOG"\n' "$command" > "$work/bin/$command"
done
chmod 755 "$work/bin/"*
export PATH="$work/bin:$PATH" ULI_TEST_MODE=1 ULI_TEST_TTY=1 ULI_OS_RELEASE=$work/fixtures/os-release
export MOCK_FORBIDDEN_LOG=$work/forbidden.log
sim openssl 3.0.13-0ubuntu3 3.0.13-0ubuntu3.1 nginx 1.26.0-1ubuntu1 1.26.0-1ubuntu2 > "$work/fixtures/two"
sim openssl 3.0.13-0ubuntu3 3.0.13-0ubuntu3.1 nginx 1.26.0-1ubuntu1 1.26.0-1ubuntu2 linux-image-generic 7.0.0.38 7.0.0.39 > "$work/fixtures/three"
: > "$work/fixtures/none"
{ sim openssl 3.0.13-0ubuntu3 3.0.13-0ubuntu3.1; printf 'Remv libold1 [1.0]\n'; } > "$work/fixtures/removal"
{ printf 'The following packages have been kept back:\n  libheld2 libheld3\n'; sim openssl 3.0.13-0ubuntu3 3.0.13-0ubuntu3.1; printf '1 upgraded, 0 newly installed, 0 to remove and 2 not upgraded.\n'; } > "$work/fixtures/kept"

case_no=0
setup() { # before-fixture after-fixture
  case_no=$((case_no+1))
  export MOCK_STATE=$work/state-$case_no ULI_ROOT=$work/root-$case_no
  export MOCK_LOG=$MOCK_STATE/apt.log MOCK_SUDO_LOG=$MOCK_STATE/sudo.log
  export MOCK_SIM_BEFORE=$work/fixtures/$1 MOCK_SIM_AFTER=$work/fixtures/${2:-$1}
  mkdir -p "$MOCK_STATE"; : > "$MOCK_LOG"
  sed -nE 's/^Inst ([^ ]+) \[([^]]+)\].*/\1 \2/p' "$MOCK_SIM_BEFORE" > "$MOCK_STATE/dpkgdb"
}
run() { # input output [args]
  local input=$1 output=$2; shift 2
  printf '%b' "$input" | bash "$work/fixture/install.sh" "$@" > "$output" 2>&1
}
apt_actions() { awk '{s=0; a=""; for(i=1;i<=NF;i++){ if($i=="-s") s=1; if($i ~ /^(update|upgrade)$/) a=$i } if(a!="") print (s?"simulate":a)}' "$MOCK_LOG" | paste -sd' '; }
no_forbidden_flags() { ! grep -qE '(^| )(-y|--yes|--assume-yes|dist-upgrade|full-upgrade|autoremove|--allow-remove|--force)( |$)' "$MOCK_LOG"; }

# Decline, EOF and non-interactive: plan only, nothing executed, no sudo.
setup two
run '\n' "$work/decline" --system-update
grep -q 'Upgrades: 2 pakket(ten)' "$work/decline" && grep -q 'OS: Ubuntu 26.04.1 LTS' "$work/decline"
grep -q 'nginx 1.26.0-1ubuntu1 -> 1.26.0-1ubuntu2' "$work/decline" && grep -q 'Mogelijke korte dienstonderbreking' "$work/decline"
grep -q 'Systeemupdate geannuleerd' "$work/decline"
[[ $(apt_actions) == simulate && ! -e $ULI_ROOT && ! -s $MOCK_SUDO_LOG ]]
setup two; result=0; run '' "$work/eof" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'Geen bevestiging ontvangen' "$work/eof" && [[ $(apt_actions) == simulate && ! -e $ULI_ROOT ]]
setup two; result=0; ULI_TEST_TTY=0 run 'bijwerken\n' "$work/notty" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'interactieve terminal' "$work/notty" && [[ ! -s $MOCK_LOG && ! -e $ULI_ROOT ]]
setup two; run 'ja\n' "$work/wrong-word" --system-update
grep -q 'Systeemupdate geannuleerd' "$work/wrong-word" && [[ $(apt_actions) == simulate ]]
echo 'PASS plan shown read-only; decline, wrong word, EOF and non-interactive change nothing'

# Happy path (started as administrator): update strictly before upgrade.
setup two
run 'bijwerken\n' "$work/happy" --system-update
[[ $(apt_actions) == 'simulate simulate update simulate upgrade' ]]
no_forbidden_flags
grep -q -- '--no-remove --with-new-pkgs upgrade' "$MOCK_LOG"
grep -q 'Systeemupdate voltooid: 2 pakket(ten) op de geplande versie' "$work/happy"
grep -q 'Geen herstart gemeld' "$work/happy"
report=$(ls "$ULI_ROOT"/var/lib/universal-linux-installer/system-update-*.txt)
[[ $(stat -c %a "$report") == 600 ]]
grep -q 'Resultaat: PASS' "$report" && grep -q 'U nginx 1.26.0-1ubuntu1 1.26.0-1ubuntu2' "$report"
if grep -q 'uli-apt-secret' "$report" "$work/happy"; then exit 1; fi
[[ ! -s $MOCK_FORBIDDEN_LOG ]]
echo 'PASS bijwerken runs apt-get update before apt-get upgrade, no -y/full-upgrade/autoremove, verified versions, sanitized 0600 report'

# Metadata refresh changes the plan: shown again; declining stops after update only.
setup two three
run 'bijwerken\n\n' "$work/changed-decline" --system-update
[[ $(apt_actions) == 'simulate simulate update simulate' ]]
grep -q 'Na het verversen is het plan anders' "$work/changed-decline" && grep -q 'alleen de pakketindex is ververst' "$work/changed-decline"
grep -q 'Herstart waarschijnlijk nodig' "$work/changed-decline"
setup two three
MOCK_REBOOT=1 run 'bijwerken\nbijwerken\n' "$work/changed-accept" --system-update
[[ $(apt_actions) == 'simulate simulate update simulate upgrade' ]]
grep -q 'Systeemupdate voltooid: 3 pakket(ten)' "$work/changed-accept"
grep -q 'Herstart aanbevolen; plan die zelf in' "$work/changed-accept"
grep -q 'Herstart aanbevolen: ja' "$ULI_ROOT"/var/lib/universal-linux-installer/system-update-*.txt
[[ ! -s $MOCK_FORBIDDEN_LOG ]]
echo 'PASS changed plan after refresh is re-shown and re-confirmed; reboot only advised, never executed'

# Approved digest differs from the privileged re-check: re-confirm or STOP.
setup two
result=0; run '\n' "$work/stale-approval" --system-update --approved-plan "$(printf '%064d' 0)" || result=$?
[[ $result == 1 ]] && grep -q 'Het plan is gewijzigd sinds uw bevestiging' "$work/stale-approval"
[[ $(apt_actions) == simulate ]]
setup none
run '\n' "$work/uptodate" --system-update
grep -q 'Upgrades: 0 pakket(ten)' "$work/uptodate"
setup none; run 'bijwerken\n' "$work/uptodate-run" --system-update
[[ $(apt_actions) == 'simulate simulate update simulate' ]] && grep -q 'Systeem is up-to-date' "$work/uptodate-run"
echo 'PASS stale approval STOPs unless re-confirmed; up-to-date system refreshes index without upgrade'

# STOP conditions before anything changes.
stop_case() { # label fixture expected-message [env...]
  local label=$1 fixture=$2 message=$3; shift 3
  setup "$fixture"; local result=0
  env "$@" bash -c 'printf "bijwerken\n" | bash "$1" --system-update' _ "$work/fixture/install.sh" > "$work/stop-$label" 2>&1 || result=$?
  [[ $result == 1 ]] && grep -q "$message" "$work/stop-$label"
  if [[ $(apt_actions) == *update* || $(apt_actions) == *upgrade* ]]; then exit 1; fi
}
stop_case removal removal 'verwijdert pakketten'
stop_case dpkg two 'Onvoltooide dpkg-transactie' MOCK_DPKG_AUDIT=1
stop_case origin two 'Niet-Ubuntu APT-repository' MOCK_ORIGIN=Example
stop_case unsafe two 'Systeemcontrole mislukt' MOCK_CHECKS_FAIL=1
stop_case simfail two 'APT-simulatie mislukt' MOCK_SIM_EXIT=100
setup two
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer"; chmod 700 "$ULI_ROOT/var/lib/universal-linux-installer"
flock "$ULI_ROOT/var/lib/universal-linux-installer/lock" sleep 5 & holder=$!
sleep 0.2
result=0; run 'bijwerken\n' "$work/locked" --system-update || result=$?
kill "$holder" 2>/dev/null || true; wait "$holder" 2>/dev/null || true
[[ $result == 1 ]] && grep -q 'Installatielock bezet' "$work/locked" && [[ $(apt_actions) == simulate ]]
setup two
mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer"; chmod 700 "$ULI_ROOT/var/lib/universal-linux-installer"
printf 'profile=app\nversion=%s\ncompleted=system plan\ncurrent=swap\nstatus=running\nupdated=2026-10-28T00:00:00Z\n' "$(cat "$base/VERSION")" > "$ULI_ROOT/var/lib/universal-linux-installer/state"
chmod 600 "$ULI_ROOT/var/lib/universal-linux-installer/state"
result=0; run 'bijwerken\n' "$work/running" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'Onderbroken of mislukte installatie' "$work/running" && [[ $(apt_actions) == simulate ]]
echo 'PASS removal, dpkg conflict, foreign origin, unsafe system, simulation error, installer lock and interrupted install STOP before update'

# Holds and kept-back packages are visible warnings, not silent changes.
setup kept
run '\n' "$work/kept" --system-update
grep -q 'Tegengehouden door APT (kept back): libheld2 libheld3' "$work/kept"
MOCK_HOLDS='postgresql-18' run '\n' "$work/held" --system-update
grep -q 'Vastgehouden (hold), blijven ongewijzigd: postgresql-18' "$work/held"
echo 'PASS held and kept-back packages are shown as WARN'

# Failures during execution.
setup two; result=0; MOCK_UPDATE_EXIT=100 run 'bijwerken\n' "$work/update-fail" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'apt-get update mislukt; geen upgrade' "$work/update-fail" && [[ $(apt_actions) == 'simulate simulate update' ]]
setup two; result=0; MOCK_UPGRADE_EXIT=100 MOCK_UPGRADE_PARTIAL=1 run 'bijwerken\n' "$work/upgrade-fail" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'apt-get upgrade niet voltooid (exit 100); 2 pakket' "$work/upgrade-fail"
grep -q 'Resultaat: FAIL' "$ULI_ROOT"/var/lib/universal-linux-installer/system-update-*.txt
setup two; result=0; MOCK_UPGRADE_PARTIAL=1 run 'bijwerken\n' "$work/mismatch" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'wijken af van het plan' "$work/mismatch"
setup two; result=0; MOCK_AUDIT_AFTER=1 run 'bijwerken\n' "$work/audit-after" --system-update || result=$?
[[ $result == 1 ]] && grep -q 'onvoltooide transactie; handmatig herstel' "$work/audit-after"
[[ ! -s $MOCK_FORBIDDEN_LOG ]]
echo 'PASS update failure, upgrade failure, version mismatch and post-upgrade dpkg conflict are FAIL without automatic repair'

# Unprivileged operator: sudo only after confirmation, with the approved digest.
if (( EUID == 0 )) && command -v runuser >/dev/null && id nobody >/dev/null 2>&1; then
  chmod 755 "$work" "$work/fixture" "$work/bin" "$work/fixtures"
  as_user() { local input=$1 output=$2; shift 2; printf '%b' "$input" | runuser -u nobody -- env PATH="$PATH" ULI_TEST_MODE=1 ULI_TEST_TTY=1 ULI_OS_RELEASE="$ULI_OS_RELEASE" ULI_ROOT="$ULI_ROOT" MOCK_STATE="$MOCK_STATE" MOCK_LOG="$MOCK_LOG" MOCK_SUDO_LOG="$MOCK_SUDO_LOG" MOCK_SIM_BEFORE="$MOCK_SIM_BEFORE" MOCK_SIM_AFTER="$MOCK_SIM_AFTER" MOCK_FORBIDDEN_LOG="$MOCK_FORBIDDEN_LOG" "$@" bash "$work/fixture/install.sh" --system-update > "$output" 2>&1; }
  open_state() { chmod 777 "$MOCK_STATE"; chmod 666 "$MOCK_STATE"/*; mkdir -p "$ULI_ROOT"; chmod 777 "$ULI_ROOT"; touch "$MOCK_SUDO_LOG"; chmod 666 "$MOCK_SUDO_LOG"; : > "$MOCK_FORBIDDEN_LOG"; chmod 666 "$MOCK_FORBIDDEN_LOG"; }
  setup two; open_state
  as_user '\n' "$work/user-decline"
  [[ ! -s $MOCK_SUDO_LOG ]]
  setup two; open_state
  as_user 'bijwerken\n' "$work/user-run"
  grep -qE '^-- /bin/bash .*/install.sh --system-update --approved-plan [a-f0-9]{64}$' "$MOCK_SUDO_LOG"
  grep -q 'sudo vraagt nu zo nodig om uw wachtwoord' "$work/user-run"
  grep -q 'Systeemupdate voltooid' "$work/user-run"
  [[ $(apt_actions) == 'simulate simulate update simulate upgrade' ]]
  setup two; open_state
  result=0; as_user 'bijwerken\n' "$work/user-sudo-fail" MOCK_SUDO_FAIL=1 || result=$?
  [[ $result == 1 ]] && grep -q 'sudo geweigerd' "$work/user-sudo-fail" && [[ $(apt_actions) == simulate ]]
  echo 'PASS non-root: no sudo on decline; sudo only after bijwerken with approved digest; sudo failure changes nothing'
else
  echo 'WARN non-root system-update tests skipped: no unprivileged user available'
fi
echo 'PASS system update (apt update + apt upgrade) offline contract'
