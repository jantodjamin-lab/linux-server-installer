#!/usr/bin/env bash
# shellcheck disable=SC2016 # fixture code is written literally into mock files
# Compact status (menu 4 / --summary): every state, read-only, no sudo, no writes.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-status.XXXXXXXX)
trap '[[ ${ULI_KEEP:-0} == 1 ]] || rm -rf -- "$work"' EXIT
mkdir -p "$work/fixture" "$work/bin"
cp "$base/install.sh" "$base/VERSION" "$work/fixture/"
cp -a "$base/bash" "$work/fixture/"
printf 'checks_system() { pass "Systeemcontroles fixture"; }\n' > "$work/fixture/bash/checks.sh"
printf 'swap_active_bytes() { [[ ${MOCK_SWAP:-} != fail ]] || return 1; echo "${MOCK_SWAP:-0}"; }\n' >> "$work/fixture/bash/swap.sh"
version=$(cat "$base/VERSION")
cat > "$work/bin/dpkg-query" <<'MOCK'
#!/usr/bin/env bash
package=${!#}
for pair in ${MOCK_VERSIONS:-}; do [[ ${pair%%=*} == "$package" ]] && { printf '%s' "${pair#*=}"; exit 0; }; done
exit 1
MOCK
cat > "$work/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
[[ $1 == is-active ]] || { printf 'forbidden systemctl %s\n' "$*" >> "$MOCK_FORBIDDEN"; exit 1; }
[[ " ${MOCK_ACTIVE:-} " == *" $2 "* ]] && { echo active; exit 0; }
echo inactive; exit 3
MOCK
cat > "$work/bin/apt-get" <<'MOCK'
#!/usr/bin/env bash
[[ " $* " == *' -s '* ]] || { printf 'forbidden apt-get %s\n' "$*" >> "$MOCK_FORBIDDEN"; exit 1; }
[[ ${MOCK_APT_FAIL:-0} == 0 ]] || exit 100
for (( i=0; i<${MOCK_UPDATES:-0}; i++ )); do printf 'Inst pkg%s [1] (2 Ubuntu:26.04/resolute-updates [amd64])\n' "$i"; done
MOCK
cat > "$work/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
printf 'forbidden sudo %s\n' "$*" >> "$MOCK_FORBIDDEN"; exit 1
MOCK
cat > "$work/bin/stat" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == -c && $2 == %u ]]; then echo 0; else /usr/bin/stat "$@"; fi
MOCK
chmod 755 "$work/bin/"*
export PATH="$work/bin:$PATH" ULI_TEST_MODE=1 MOCK_FORBIDDEN=$work/forbidden.log
n=0
fresh() { n=$((n+1)); export ULI_ROOT=$work/root-$n; STATE=$ULI_ROOT/var/lib/universal-linux-installer; }
write_state() { # profile status completed current [error]
  mkdir -p "$STATE" "$ULI_ROOT/run"; chmod 700 "$STATE"
  printf 'profile=%s\nversion=%s\ncompleted=%s\ncurrent=%s\nstatus=%s\nupdated=2026-10-28T10:00:00Z\nstarted=2026-10-28T09:00:00Z\nended=\nerror=%s\n' "$1" "$version" "$3" "$4" "$2" "${5:-}" > "$STATE/state"
  chmod 600 "$STATE/state"
}
snapshot() { [[ -e $ULI_ROOT ]] && find "$ULI_ROOT" -printf '%p %s %m %T@\n' | sort | sha256sum || echo absent; }
summary() { # output expected-exit
  local before result=0
  before=$(snapshot)
  bash "$work/fixture/install.sh" --summary > "$1" 2>&1 || result=$?
  [[ $result == "$2" ]] || { cat "$1"; return 1; }
  [[ $(snapshot) == "$before" ]]
  [[ ! -s $MOCK_FORBIDDEN ]]
}

fresh
summary "$work/empty" 0
grep -q "Installer/release *$version" "$work/empty"
grep -q 'Toestand *niet geïnstalleerd' "$work/empty"
grep -q 'Volgende veilige actie: kies 6 (controle) en daarna 1, 2 of 3' "$work/empty"
[[ ! -e $ULI_ROOT ]]
printf '4\n' | bash "$work/fixture/install.sh" > "$work/empty-menu" 2>&1
grep -q 'INSTALLATIESTATUS (read-only)' "$work/empty-menu" && [[ ! -e $ULI_ROOT ]]
echo 'PASS empty host: niet geïnstalleerd, menu 4 equals --summary, nothing created'

fresh; write_state combined complete 'system plan swap app_packages codex nginx postgres database_check resume verification' ''
mkdir -p "$ULI_ROOT/opt/universal-linux-installer/codex/node_modules/@openai/codex"
printf '{\n  "name": "@openai/codex",\n  "version": "0.128.0"\n}\n' > "$ULI_ROOT/opt/universal-linux-installer/codex/node_modules/@openai/codex/package.json"
MOCK_SWAP=4294967296 MOCK_VERSIONS='nginx=1.26.0-1ubuntu2 postgresql-18=18.1-1' MOCK_ACTIVE='nginx postgresql@18-main' summary "$work/complete" 0
for expected in 'Toestand *voltooid' 'Profiel *APP + DB (combined)' 'Stap *10/10 (100%)' 'Laatste geslaagde stap verification (statuswijziging 2026-10-28T10:00:00Z UTC)' \
  'Nginx *1.26.0-1ubuntu2; dienst actief' 'Codex *0.128.0 (vereist 0.128.0)' 'PostgreSQL 18 *18.1-1; dienst actief' 'Swap *4.0 GiB actief' 'Herstart *geen herstart gemeld' 'Updates *geen volgens lokale pakketindex' 'geen actie nodig; systeemupdates via 5'; do
  grep -q "$expected" "$work/complete" || { echo "missing: $expected"; exit 1; }
done
if grep -q 'WARN\|FAIL' "$work/complete"; then exit 1; fi
echo 'PASS completed APP+DB: versions, services, Codex pin, swap, reboot and updates all PASS'

: > "$ULI_ROOT/run/reboot-required"
printf '{"version": "0.127.0"}\n' > "$ULI_ROOT/opt/universal-linux-installer/codex/node_modules/@openai/codex/package.json"
MOCK_SWAP=1073741824 MOCK_UPDATES=3 MOCK_VERSIONS='nginx=1.26.0-1ubuntu2' MOCK_ACTIVE='' summary "$work/drift" 0
for expected in 'WARN  Nginx *1.26.0-1ubuntu2; dienst inactive' 'WARN  Codex *0.127.0 (vereist 0.128.0)' 'WARN  PostgreSQL 18 *niet geïnstalleerd; dienst inactive' \
  'WARN  Swap *1.0 GiB actief; minder dan vereist' 'WARN  Herstart *aanbevolen door het systeem' 'WARN  Updates *3 beschikbaar volgens lokale pakketindex (kies 5)'; do
  grep -q "$expected" "$work/drift" || { echo "missing: $expected"; exit 1; }
done
MOCK_SWAP=fail MOCK_APT_FAIL=1 summary "$work/unknown" 0
grep -q 'WARN  Swap *onbekend' "$work/unknown" && grep -q 'WARN  Updates *onbekend' "$work/unknown"
echo 'PASS drift and unknown facts are WARN, never PASS'

fresh; write_state database running 'system plan swap' postgres
mkdir -p "$ULI_ROOT/run"; : > "$STATE/lock"; chmod 600 "$STATE/lock"
summary "$work/interrupted" 0
grep -q 'WARN  Toestand *onderbroken' "$work/interrupted" && grep -q 'Stap *3/7 (42%); actueel: postgres' "$work/interrupted"
grep -q 'kies hetzelfde profiel opnieuw om veilig te hervatten' "$work/interrupted"
grep -q 'PostgreSQL 18' "$work/interrupted" && ! grep -q 'Nginx' "$work/interrupted"
flock "$STATE/lock" sleep 5 & holder=$!
sleep 0.2
summary "$work/running" 0
kill "$holder" 2>/dev/null || true; wait "$holder" 2>/dev/null || true
grep -q 'WARN  Toestand *bezig (installatie actief)' "$work/running" && grep -q 'wacht tot de installatie klaar is' "$work/running"
echo 'PASS running vs interrupted distinguished by the installer lock'

fresh; write_state app failed 'system plan' app_packages step_app_packages_failed
summary "$work/failed" 1
grep -q 'FAIL  Toestand *fout (step_app_packages_failed)' "$work/failed" && grep -q 'niet blind herhalen' "$work/failed"
fresh; write_state app complete 'system' ''
printf 'profile=$(touch %s/injected)\n' "$work" > "$STATE/state"
summary "$work/corrupt" 1
grep -q 'FAIL  Toestand *statusbestand onleesbaar of beschadigd' "$work/corrupt" && [[ ! -e $work/injected ]]
fresh; write_state database failed 'system plan swap' postgres step_postgres_exit_130
summary "$work/signal" 0
grep -q 'WARN  Toestand *onderbroken (step_postgres_exit_130)' "$work/signal" && grep -q 'veilig te hervatten' "$work/signal"
echo 'PASS failed and corrupt state are FAIL; signal interruption is WARN onderbroken; state data is never executed'

fresh; mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer-status" "$STATE"
printf 'UNIVERSAL LINUX INSTALLER\nVersie: %s\nProfiel: app\nStatus: COMPLETE\nVoortgang: 8/8 (100%%)\nVoltooide stappen: system plan swap app_packages codex nginx resume verification\nActuele stap: geen\nStart: x\nEinde: y\nLaatste wijziging: 2026-10-28T11:00:00Z\nLaatste fout: geen\n' "$version" > "$ULI_ROOT/var/lib/universal-linux-installer-status/status"
ULI_TEST_PUBLIC_ONLY=1 summary "$work/public" 0
grep -q 'Toestand *voltooid' "$work/public" && grep -q 'Stap *8/8 (100%)' "$work/public"
rm "$ULI_ROOT/var/lib/universal-linux-installer-status/status"
ULI_TEST_PUBLIC_ONLY=1 summary "$work/protected" 0
grep -q 'WARN  Toestand *onbekend; status alleen als administrator leesbaar' "$work/protected"
if (( EUID == 0 )) && command -v runuser >/dev/null && id nobody >/dev/null 2>&1; then
  fresh; write_state app complete 'system plan swap app_packages codex nginx resume verification' ''
  mkdir -p "$ULI_ROOT/var/lib/universal-linux-installer-status"; chmod 755 "$ULI_ROOT" "$ULI_ROOT/var" "$ULI_ROOT/var/lib" "$ULI_ROOT/var/lib/universal-linux-installer-status"
  printf 'UNIVERSAL LINUX INSTALLER\nVersie: %s\nProfiel: app\nStatus: RUNNING\nVoortgang: 3/8 (37%%)\nVoltooide stappen: system plan swap\nActuele stap: app_packages\nStart: x\nEinde: \nLaatste wijziging: 2026-10-28T12:00:00Z\nLaatste fout: geen\n' "$version" > "$ULI_ROOT/var/lib/universal-linux-installer-status/status"
  chmod 644 "$ULI_ROOT/var/lib/universal-linux-installer-status/status"
  chmod 755 "$work" "$work/fixture" "$work/bin"; : > "$MOCK_FORBIDDEN"; chmod 666 "$MOCK_FORBIDDEN"
  before=$(snapshot)
  runuser -u nobody -- env PATH="$PATH" ULI_TEST_MODE=1 ULI_ROOT="$ULI_ROOT" MOCK_FORBIDDEN="$MOCK_FORBIDDEN" bash "$work/fixture/install.sh" --summary > "$work/nobody" 2>&1
  [[ $(snapshot) == "$before" && ! -s $MOCK_FORBIDDEN ]]
  grep -q 'Toestand *bezig of onderbroken (niet vast te stellen zonder administratorrechten)' "$work/nobody"
  grep -q 'Stap *3/8 (37%); actueel: app_packages' "$work/nobody"
  if grep -q 'started=\|profile=' "$work/nobody"; then exit 1; fi
fi
echo 'PASS non-administrator view uses only the sanitized public status; protected state is WARN'

fresh; write_state app complete 'system plan swap app_packages codex nginx resume verification' ''
bash "$work/fixture/install.sh" --status > "$work/details"
grep -q 'Installerversie:' "$work/details" && grep -q 'Voltooide stappen:' "$work/details"
echo 'PASS --status keeps the detailed view'
