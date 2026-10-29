#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS %s\n' "$*"; }

[[ $# == 2 ]] || fail 'Bootstrapregistratie verwacht een gecontroleerd script en SHA256'
bootstrap=$1 expected_sha=$2
[[ $expected_sha =~ ^[a-f0-9]{64}$ && -f $bootstrap && ! -L $bootstrap ]] || fail 'Onveilig bootstrapbestand'
actual_bootstrap_sha=$(sha256sum "$bootstrap" | awk '{print $1}')
[[ $actual_bootstrap_sha == "$expected_sha" ]] || fail "Bootstrap-SHA256 wijkt af ($actual_bootstrap_sha)"
bash -n "$bootstrap" || fail 'Bootstrap bevat ongeldige Bash-syntax'
for tool in install stat cmp mktemp; do command -v "$tool" >/dev/null || fail "Hulpmiddel ontbreekt: $tool"; done

test_mode=0 root_prefix='' owner=0 group=0
if [[ ${ULI_TEST_MODE:-0} == 1 ]]; then
  test_mode=1
  root_prefix=${ULI_INSTALL_NOW_ROOT:?Testmodus vereist een geïsoleerde installatieroot}
  [[ $root_prefix == /* && ! -L $root_prefix ]] || fail 'Onveilige testinstallatieroot'
  owner=$EUID group=$(id -g)
elif (( EUID != 0 )); then
  command -v sudo >/dev/null || fail 'sudo ontbreekt; start de registratie opnieuw als administrator'
fi

root_run() {
  if (( test_mode )) || (( EUID == 0 )); then "$@"; else sudo -- "$@"; fi
}
target_path() { printf '%s%s' "$root_prefix" "$1"; }

lib_dir=$(target_path /usr/local/lib/universal-linux-installer)
bin_dir=$(target_path /usr/local/bin)
installed_bootstrap=$lib_dir/bootstrap.sh
installed_launcher=$bin_dir/install-now
work=$(mktemp -d "${TMPDIR:-/tmp}/uli-install-now.XXXXXXXX") || fail 'Tijdelijke map kan niet worden gemaakt'
trap 'rm -rf -- "$work"' EXIT

launcher=$work/install-now
cat > "$launcher" <<'LAUNCHER'
#!/usr/bin/env bash
# Managed by Universal Linux Installer; generated from a SHA256-verified release.
set -Eeuo pipefail
LAUNCHER
printf 'exec /usr/bin/bash %q "$@"\n' "$installed_bootstrap" >> "$launcher"
chmod 700 "$launcher"

printf 'Registratieplan: root-beveiligde bootstrap in /usr/local/lib/universal-linux-installer/ en install-now in /usr/local/bin/.\n'
printf 'Er worden geen serverprofielen geïnstalleerd. Bevestig registratie met ja [ja/nee]: '
answer=''
IFS= read -r answer || fail 'Geen bevestiging ontvangen'
[[ $answer == ja ]] || { pass 'Registratie geannuleerd; geen wijzigingen'; exit 0; }

safe_dir() {
  local directory=$1
  if root_run test -L "$directory"; then fail "Directory is een onveilige symlink: $directory"; fi
  if root_run test -e "$directory"; then
    root_run test -d "$directory" || fail "Geen directory: $directory"
    [[ $(root_run stat -c %u "$directory") == "$owner" ]] || fail "Onveilige directory-eigenaar: $directory"
    [[ $(root_run stat -c %a "$directory") == 755 ]] || fail "Onveilige directoryrechten: $directory"
  else
    root_run install -d -o "$owner" -g "$group" -m 0755 -- "$directory"
  fi
}

safe_existing_file() {
  local target=$1 mode=$2 source=$3 label=$4
  if root_run test -L "$target"; then fail "Bestaand $label is een symlink; niets overschreven"; fi
  if root_run test -e "$target"; then
    root_run test -f "$target" || fail "Bestaand $label is geen normaal bestand"
    [[ $(root_run stat -c %u "$target") == "$owner" && $(root_run stat -c %a "$target") == "$mode" ]] || fail "Bestaand $label heeft onveilige eigenaar of rechten"
    root_run cmp -s -- "$source" "$target" || fail "Bestaand $label verschilt; niets overschreven"
    return 0
  fi
  return 1
}

safe_dir "$(target_path /usr/local/lib)"
safe_dir "$lib_dir"
safe_dir "$bin_dir"

bootstrap_present=0 launcher_present=0
if safe_existing_file "$installed_bootstrap" 644 "$bootstrap" bootstrap; then bootstrap_present=1; fi
if safe_existing_file "$installed_launcher" 755 "$launcher" launcher; then launcher_present=1; fi
if (( bootstrap_present && launcher_present )); then
  pass 'install-now is al geregistreerd; bestanden zijn ongewijzigd'
  exit 0
fi

# Install the verified bootstrap first. A rerun safely completes registration if
# the process stops between this file and the atomic launcher replacement.
if (( ! bootstrap_present )); then
  staged_bootstrap=$installed_bootstrap.tmp.$BASHPID
  root_run install -o "$owner" -g "$group" -m 0644 -- "$bootstrap" "$staged_bootstrap"
  root_run mv -fT -- "$staged_bootstrap" "$installed_bootstrap"
fi
if (( ! launcher_present )); then
  staged_launcher=$installed_launcher.tmp.$BASHPID
  root_run install -o "$owner" -g "$group" -m 0755 -- "$launcher" "$staged_launcher"
  root_run mv -fT -- "$staged_launcher" "$installed_launcher"
fi

safe_existing_file "$installed_bootstrap" 644 "$bootstrap" bootstrap || fail 'Geregistreerde bootstrap wijkt af'
safe_existing_file "$installed_launcher" 755 "$launcher" launcher || fail 'Geregistreerde launcher wijkt af'
pass 'install-now veilig en persistent geregistreerd'
printf 'Start daarna: install-now\n'
