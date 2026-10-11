#!/usr/bin/env bash
# Installation order and errors with all system-facing commands mocked.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-profile-tests.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
source "$base/bash/common.sh"
source "$base/bash/app.sh"
source "$base/bash/database.sh"
uli_apt_install() { printf '%s\n' "$*" >> "$work/packages"; return "${APT_RESULT:-0}"; }
app_codex_install() { echo codex >> "$work/events"; }
app_verify() { echo verify-app >> "$work/events"; }
nginx() { [[ $1 == -t ]]; }
systemctl() { printf 'service %s\n' "$*" >> "$work/events"; }
app_install
[[ $(cat "$work/packages") == 'git python3 dotnet-sdk-10.0 nodejs npm nginx ca-certificates' ]]
[[ $(head -1 "$work/events") == codex && $(tail -1 "$work/events") == verify-app ]]
echo 'PASS APP package set and component ordering'
APT_RESULT=100
if app_install; then exit 1; fi
if database_install; then exit 1; fi
[[ $(tail -1 "$work/packages") == postgresql-18 ]]
echo 'PASS missing package/APT failure stops both profiles'
# Command-line/menu tests deliberately refuse host checks before touching state.
for selection in 1 2 3; do
 if printf '%s\nnee\n' "$selection" | bash "$base/install.sh" > "$work/menu-$selection" 2>&1; then :; fi
 grep -q 'Maak uw keuze' "$work/menu-$selection"
done
echo 'PASS all three menu selections reach guarded installation route'
if ((EUID != 0)); then
 if require_root; then exit 1; fi
 echo 'PASS nonroot requires sudo before installation'
else
 echo 'WARN sudo refusal requires nonroot runner; CI workflow tests sudo explicitly'
fi
source "$base/bash/checks.sh"
dpkg() { [[ $1 == --audit ]]; }
apt-cache() { if (( $# == 1 )); then printf "  release o=Ubuntu,a=resolute\n"; else printf "%s\n" "  Candidate: ${CANDIDATE:-1.0}"; for ((line=0;line<5000;line++)); do printf "      Package table trailing metadata line %s\n" "$line" || return 100; done; fi; }
run_apt() { [[ $* == *--simulate* && $* == *--no-remove* ]]; }
for PROFILE in app database combined; do checks_packages; done
echo 'PASS APP, DB and combined candidate validation'
CANDIDATE='(none)'
if checks_packages; then exit 1; fi
echo 'PASS unavailable candidate fails preflight'
