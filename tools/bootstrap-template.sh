#!/usr/bin/env bash
# Render these two pins after building the release; never use a remote checksum.
ULI_BOOTSTRAP_VERSION='@@VERSION@@'
ULI_BOOTSTRAP_SHA256='@@SHA256@@'
ULI_BOOTSTRAP_URL='@@URL@@'

uli_bootstrap_fail() { printf 'FAIL %s\n' "$*" >&2; return 1; }

uli_bootstrap_validate() {
  local archive=$1 expected=$2 version=$3 listing=$4 root line permissions owner bytes day hour name extra normalized parent
  local count=0 total=0
  local -A seen=() kinds=()
  [[ $expected =~ ^[a-f0-9]{64}$ && $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]] || { uli_bootstrap_fail 'Ongeldige releasepin'; return 1; }
  [[ -f $archive && ! -L $archive ]] || { uli_bootstrap_fail 'Onveilig downloadbestand'; return 1; }
  [[ $(wc -c < "$archive") -le 33554432 ]] || { uli_bootstrap_fail 'Download te groot'; return 1; }
  [[ $(sha256sum "$archive" | awk '{print $1}') == "$expected" ]] || { uli_bootstrap_fail 'Release SHA256 wijkt af; geen archiefinspectie of uitvoering'; return 1; }
  root=universal-linux-installer-$version
  # GNU tar escape quoting ensures control characters cannot masquerade as rows.
  if ! LC_ALL=C tar --list --verbose --numeric-owner --quoting-style=escape --gzip --file="$archive" > "$listing" 2> "$listing.errors"; then
    uli_bootstrap_fail 'Archief kan niet veilig worden gelezen'; return 1
  fi
  [[ ! -s $listing.errors ]] || { uli_bootstrap_fail 'Archiefwaarschuwing; extractie geweigerd'; return 1; }
  while IFS= read -r line; do
    read -r permissions owner bytes day hour name extra <<< "$line" || return
    [[ $permissions =~ ^[-d][rwx-]{9}$ && $owner == 0/0 && $bytes =~ ^[0-9]+$ && ${#bytes} -le 8 && -z $extra ]] || { uli_bootstrap_fail 'Onveilig archieftype, eigenaar of metadata'; return 1; }
    [[ ${#name} -le 4096 && $name =~ ^[a-zA-Z0-9_./+@-]+$ ]] || { uli_bootstrap_fail 'Onveilig archiefpad'; return 1; }
    normalized=${name%/}
    [[ $normalized == "$root" || $normalized == "$root/"* ]] || { uli_bootstrap_fail 'Bestand buiten releasemap'; return 1; }
    [[ /$normalized/ != *'/../'* && /$normalized/ != *'/./'* && $normalized != *'//'* ]] || { uli_bootstrap_fail 'Padtraversal of ambigu pad'; return 1; }
    [[ -z ${seen[$normalized]:-} ]] || { uli_bootstrap_fail 'Dubbel archiefpad'; return 1; }
    seen[$normalized]=1 kinds[$normalized]=${permissions:0:1}
    if [[ ${permissions:0:1} == d ]]; then
      [[ $bytes == 0 && $name == */ ]] || { uli_bootstrap_fail 'Ongeldige mapmetadata'; return 1; }
    else
      [[ $name != */ && $normalized != "$root" && $bytes -le 67108864 ]] || { uli_bootstrap_fail 'Ongeldig of te groot bestand'; return 1; }
    fi
    count=$((count+1)); total=$((total+10#$bytes))
    (( count <= 10000 && total <= 268435456 )) || { uli_bootstrap_fail 'Archieflimiet overschreden'; return 1; }
  done < "$listing"
  [[ ${kinds[$root]:-} == d ]] || { uli_bootstrap_fail 'Releasemap ontbreekt'; return 1; }
  for normalized in "${!seen[@]}"; do
    parent=$normalized
    while [[ $parent == */* ]]; do
      parent=${parent%/*}
      [[ ${kinds[$parent]:-} == d ]] || { uli_bootstrap_fail 'Ontbrekende of conflicterende bovenmap'; return 1; }
    done
  done
  for name in install.sh VERSION FILES.sha256 bash/common.sh bash/checks.sh bash/progress.sh bash/state.sh bash/swap.sh bash/app.sh bash/database.sh bash/preflight.sh bash/status.sh bash/sysupdate.sh bash/assets/codex/package.json bash/assets/codex/package-lock.json tools/register-install-now.sh; do
    [[ ${kinds[$root/$name]:-} == - ]] || { uli_bootstrap_fail "Releasebestand ontbreekt: $name"; return 1; }
  done
}

uli_bootstrap_main() (
  set -Eeuo pipefail
  umask 077
  export LC_ALL=C
  local tool work archive root
  [[ $ULI_BOOTSTRAP_SHA256 =~ ^[a-f0-9]{64}$ && $ULI_BOOTSTRAP_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]] || { uli_bootstrap_fail 'Bootstrap is niet gerenderd'; exit 1; }
  [[ $ULI_BOOTSTRAP_URL =~ ^https://[a-zA-Z0-9._:/%+@=?\&-]+$ ]] || { uli_bootstrap_fail 'Ongeldige HTTPS-release-URL'; exit 1; }
  for tool in bash curl tar sha256sum awk wc mktemp; do command -v "$tool" >/dev/null || { uli_bootstrap_fail "Hulpmiddel ontbreekt: $tool"; exit 1; }; done
  tar --version | awk 'NR==1 {if ($0 !~ /GNU tar/) exit 1}' || { uli_bootstrap_fail 'GNU tar vereist'; exit 1; }
  [[ -r /dev/tty && -w /dev/tty ]] || { uli_bootstrap_fail 'Start interactief in een terminal'; exit 1; }
  # Open the terminal before downloading; a pipe never supplies menu answers.
  exec 3<>/dev/tty || { uli_bootstrap_fail 'Geen actieve terminal'; exit 1; }
  work=$(mktemp -d "${TMPDIR:-/tmp}/uli-bootstrap.XXXXXXXX") || exit 1
  trap 'rm -rf -- "$work"' EXIT
  archive=$work/release.tar.gz
  root=universal-linux-installer-$ULI_BOOTSTRAP_VERSION
  curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 30 --max-time 300 --max-filesize 33554432 \
    "$ULI_BOOTSTRAP_URL" --output "$archive" || { uli_bootstrap_fail 'Download mislukt'; exit 1; }
  uli_bootstrap_validate "$archive" "$ULI_BOOTSTRAP_SHA256" "$ULI_BOOTSTRAP_VERSION" "$work/listing" || exit 1
  mkdir "$work/payload" || exit 1
  tar --extract --gzip --file="$archive" --directory="$work/payload" --no-same-owner --no-same-permissions --delay-directory-restore || exit 1
  [[ $(cat "$work/payload/$root/VERSION") == "$ULI_BOOTSTRAP_VERSION" ]] || { uli_bootstrap_fail 'Interne versie wijkt af'; exit 1; }
  bash -n "$work/payload/$root/install.sh" || exit 1
  for tool in "$work/payload/$root"/bash/*.sh; do bash -n "$tool" || exit 1; done
  if [[ ${1:-} == --register-install-now ]]; then
    shift
    [[ $# == 0 ]] || { uli_bootstrap_fail 'Onverwachte registratieargumenten'; exit 1; }
    bash -n "$work/payload/$root/tools/register-install-now.sh" || exit 1
    local verified_bootstrap_sha
    verified_bootstrap_sha=$(sha256sum "$0" | awk '{print $1}')
    bash "$work/payload/$root/tools/register-install-now.sh" "$0" "$verified_bootstrap_sha" <&3 >&3 2>&3
    exit $?
  fi
  # Installer obtains sudo only after showing its plan and receiving authorization.
  bash "$work/payload/$root/install.sh" "$@" <&3 >&3 2>&3
)

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then uli_bootstrap_main "$@"; fi
