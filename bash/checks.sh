#!/usr/bin/env bash
checks_system() {
  [[ -r /etc/os-release ]] || { fail 'OS-identificatie ontbreekt'; return 1; }
  local ID VERSION_ID
  . /etc/os-release
  [[ $ID == ubuntu && $VERSION_ID == 26.04 ]] || { fail 'Alleen Ubuntu 26.04 LTS wordt ondersteund'; return 1; }
  local tool
  for tool in flock systemctl apt-get dpkg-query findmnt swapon mkswap sha256sum stat install; do
    command -v "$tool" >/dev/null || { fail "Vereist hulpmiddel ontbreekt: $tool"; return 1; }
  done
  [[ $(ps -p 1 -o comm=) == systemd ]] || { fail 'Systemd als PID 1 is vereist'; return 1; }
  if grep -RiqE 'trusted[[:space:]]*=[[:space:]]*(yes|true|1)|allow-(insecure|weak|downgrade-to-insecure)[[:space:]]*=[[:space:]]*(yes|true|1)|Trusted:[[:space:]]*(yes|true|1)|Allow-(Insecure|Weak|Downgrade-To-Insecure):[[:space:]]*(yes|true|1)' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
    fail 'Onveilige APT-bronconfiguratie'; return 1
  fi
  if apt-config dump | grep -iE '(AllowUnauthenticated|AllowInsecureRepositories|AllowDowngradeToInsecureRepositories|AllowWeakRepositories).*"true"' >/dev/null; then
    fail 'APT-beveiligingscontrole is uitgeschakeld'; return 1
  fi
  local ram
  ram=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
  (( ram >= 4194304 )) || warn 'Minder dan 4 GiB fysiek RAM; swap vervangt voldoende RAM niet.'
  pass 'Systeemcontroles'
}

checks_packages() {
  local package candidate audit origins
  local -a packages=()
  [[ $PROFILE == database ]] || packages=(git python3 dotnet-sdk-10.0 nodejs npm nginx ca-certificates)
  [[ $PROFILE == app ]] || packages+=(postgresql-18 postgresql-client-18)
  audit=$(dpkg --audit) || { fail 'dpkg-statuscontrole mislukt'; return 1; }
  [[ -z $audit ]] || { fail 'Onvoltooide dpkg-transactie: handmatig onderzoek vereist'; return 1; }
  origins=$(apt-cache policy | awk '/release / && /o=/ {n=split($0,a,","); for(i=1;i<=n;i++) if(a[i] ~ /(^|[[:space:]])o=/) {sub(/^.*o=/,"",a[i]); print a[i]}}')
  [[ -n $origins ]] || { fail 'APT-repositoryherkomst ontbreekt'; return 1; }
  while IFS= read -r candidate; do
    [[ $candidate == Ubuntu ]] || { fail 'Niet-Ubuntu APT-repository vereist handmatige beoordeling'; return 1; }
  done <<< "$origins"
  for package in "${packages[@]}"; do
    candidate=$(apt-cache policy "$package" | awk '/Candidate:/ {print $2; exit}')
    [[ -n $candidate && $candidate != '(none)' ]] || { fail "Pakket niet beschikbaar: $package"; return 1; }
  done
  run_apt --simulate --no-remove install --no-install-recommends "${packages[@]}" || { fail 'APT-installatieplan onveilig of onoplosbaar'; return 1; }
  pass 'Alle vereiste pakketten beschikbaar'

}
