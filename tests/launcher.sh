#!/usr/bin/env bash
# Isolated launcher/bootstrap tests. No sudo, network, services or system paths.
set -Eeuo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
work=$(mktemp -d "${TMPDIR:-/tmp}/uli-launcher-tests.XXXXXXXX")
if [[ ${ULI_KEEP_TEST_FILES:-0} != 1 ]]; then trap 'rm -rf -- "$work"' EXIT; fi
for tool in bash script sha256sum tar; do command -v "$tool" >/dev/null || { printf 'WARN launcher test skipped: %s missing\n' "$tool"; exit 77; }; done
mkdir -p "$work/mockbin"
cat > "$work/mockbin/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
url='' target='' previous=''
for argument in "$@"; do
  [[ $previous != --output ]] || target=$argument
  [[ $argument != https://* ]] || url=$argument
  previous=$argument
done
[[ -n $target && -n $url ]]
case "${ULI_MOCK_CURL_MODE:-}" in
  fail_bootstrap) [[ $url != */bootstrap.sh ]] || exit 28;;
  fail_archive) [[ $url != */universal-linux-installer-*.tar.gz ]] || exit 28;;
esac
if [[ $url == */bootstrap.sh ]]; then cp -- "$ULI_FIXTURE_BOOTSTRAP" "$target"; else cp -- "$ULI_FIXTURE_ARCHIVE" "$target"; fi
if [[ ${ULI_MOCK_CURL_MODE:-} == bad_archive && $url != */bootstrap.sh ]]; then printf tamper >> "$target"; fi
if [[ ${ULI_MOCK_CURL_MODE:-} == bad_bootstrap && $url == */bootstrap.sh ]]; then printf tamper >> "$target"; fi
MOCK_CURL
chmod 755 "$work/mockbin/curl"

# Exercise the actual packaged installer through a local HTTPS-download fixture.
TMPDIR="${TMPDIR:-/tmp}" bash "$base/tools/release.sh" > "$work/release-build.log"
version=$(cat "$base/VERSION")
archive=$base/release/universal-linux-installer-$version.tar.gz
bash "$base/tools/render-bootstrap.sh" "$version" "$archive" "$work/rendered" \
  "https://launcher.test/universal-linux-installer-$version.tar.gz" https://launcher.test/bootstrap.sh > "$work/render.log"
cp "$work/rendered/bootstrap.sh" "$work/fixture-bootstrap.sh"
cp "$archive" "$work/fixture-release.tar.gz"
export ULI_FIXTURE_BOOTSTRAP=$work/fixture-bootstrap.sh ULI_FIXTURE_ARCHIVE=$work/fixture-release.tar.gz
export ULI_TEST_MODE=1 ULI_INSTALL_NOW_ROOT=$work/system-root ULI_ROOT=$work/installer-root
export PATH="$work/mockbin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

run_pty() {
  local response=$1 command_line=$2 output=$3 result=0
  printf '%s' "$response" | TMPDIR="${TMPDIR:-/tmp}" SHELL=/bin/bash TERM=xterm timeout 30s script --quiet --return --command "$command_line" /dev/null > "$output" 2>&1 || result=$?
  return "$result"
}

setup_command=$(cat "$work/rendered/BOOTSTRAP-INSTALL-NOW.txt")
launcher="$ULI_INSTALL_NOW_ROOT/usr/local/bin/install-now"
bootstrap="$ULI_INSTALL_NOW_ROOT/usr/local/lib/universal-linux-installer/bootstrap.sh"

# Missing confirmation, download failure and checksum mismatch make no changes.
run_pty $'nee\n' "$setup_command" "$work/no-confirmation.log"
[[ ! -e $ULI_INSTALL_NOW_ROOT ]]
grep -q 'Registratie geannuleerd' "$work/no-confirmation.log"
[[ ! -e $ULI_ROOT ]]
if grep -q 'persistent geregistreerd' "$work/no-confirmation.log"; then exit 1; fi
printf 'PASS nee reaches confirmation and leaves no registration or installer state\n'
if ULI_MOCK_CURL_MODE=bad_bootstrap run_pty '' "$setup_command" "$work/bootstrap-checksum-fail.log"; then exit 1; fi
[[ ! -e $ULI_INSTALL_NOW_ROOT ]]
grep -q 'FAIL bootstrapdownload of validatie' "$work/bootstrap-checksum-fail.log"
if ULI_MOCK_CURL_MODE=fail_bootstrap run_pty '' "$setup_command" "$work/bootstrap-download-fail.log"; then exit 1; fi
[[ ! -e $ULI_INSTALL_NOW_ROOT ]]
if ULI_MOCK_CURL_MODE=fail_archive run_pty $'ja\n' "$setup_command" "$work/archive-download-fail.log"; then exit 1; fi
[[ ! -e $ULI_INSTALL_NOW_ROOT ]]
if ULI_MOCK_CURL_MODE=bad_archive run_pty $'ja\n' "$setup_command" "$work/archive-checksum-fail.log"; then exit 1; fi
[[ ! -e $ULI_INSTALL_NOW_ROOT ]]
grep -q 'SHA256 wijkt af' "$work/archive-checksum-fail.log"
printf 'PASS bootstrap/archive download, authorization and checksum failures stop before registration\n'

# The authorized bootstrap installs only into an isolated root.
run_pty $'ja\n' "$setup_command" "$work/register.log"
[[ -x $launcher && -f $bootstrap && ! -L $launcher && ! -L $bootstrap ]]
[[ $(stat -c %a "$launcher") == 755 && $(stat -c %a "$bootstrap") == 644 ]]
[[ $(/usr/bin/stat -c %u "$launcher") == "$EUID" && $(/usr/bin/stat -c %u "$bootstrap") == "$EUID" ]]
[[ $(sha256sum "$bootstrap" | awk '{print $1}') == "$(awk '{print $1}' "$work/rendered/BOOTSTRAP.sha256")" ]]
grep -q 'PASS install-now veilig en persistent geregistreerd' "$work/register.log"
sha_before=$(sha256sum "$launcher" "$bootstrap")
mtime_before=$(stat -c '%Y' "$launcher" "$bootstrap")
run_pty $'ja\n' "$setup_command" "$work/register-repeat.log"
[[ $(sha256sum "$launcher" "$bootstrap") == "$sha_before" ]]
[[ $(stat -c '%Y' "$launcher" "$bootstrap") == "$mtime_before" ]]
grep -q 'al geregistreerd; bestanden zijn ongewijzigd' "$work/register-repeat.log"
printf 'PASS one-time bootstrap, pinned registration, protected modes and idempotent repeat\n'

# The existing menu's exit option performs no installation or system-state write.
run_pty $'0\n' "$launcher" "$work/menu-exit.log"
for expected in '1. APP SERVER INSTALLEREN' '2. DATABASE SERVER INSTALLEREN' '3. APP + DATABASE SERVER INSTALLEREN' '4. INSTALLATIESTATUS' '5. SYSTEEM BIJWERKEN (APT UPDATE + APT UPGRADE)' '6. ALLEEN CONTROLE (READ-ONLY)' '0. AFSLUITEN'; do
  grep -q "$expected" "$work/menu-exit.log"
done
[[ ! -e $ULI_ROOT ]]
grep -q 'UNIVERSAL LINUX INSTALLER' "$work/menu-exit.log"
printf 'PASS install-now opens existing menu and exits without installer state\n'
run_pty $'0\n' "$launcher" "$work/menu-exit-repeat.log"
grep -q '0. AFSLUITEN' "$work/menu-exit-repeat.log"
grep -q 'Afgesloten; er is niets gewijzigd' "$work/menu-exit-repeat.log"
[[ ! -e $ULI_ROOT ]]
[[ $(sha256sum "$launcher" "$bootstrap") == "$sha_before" ]]
[[ $(stat -c '%Y' "$launcher" "$bootstrap") == "$mtime_before" ]]
printf 'PASS repeated standalone launch opens menu and safely exits without changes\n'

# An existing symlink is rejected without following or replacing its target.
conflict_root=$work/conflict-root
mkdir -p "$conflict_root/usr/local/bin" "$conflict_root/usr/local/lib/universal-linux-installer"
chmod 755 "$conflict_root" "$conflict_root/usr" "$conflict_root/usr/local" "$conflict_root/usr/local/bin" "$conflict_root/usr/local/lib" "$conflict_root/usr/local/lib/universal-linux-installer"
ln -s "$work/untouched" "$conflict_root/usr/local/bin/install-now"
if ULI_INSTALL_NOW_ROOT=$conflict_root bash "$base/tools/register-install-now.sh" "$bootstrap" "$(sha256sum "$bootstrap" | awk '{print $1}')" <<< ja > "$work/conflict.log" 2>&1; then exit 1; fi
[[ -L $conflict_root/usr/local/bin/install-now && ! -e $work/untouched ]]
grep -q 'symlink' "$work/conflict.log"
printf 'PASS existing symlink conflict is rejected\n'
