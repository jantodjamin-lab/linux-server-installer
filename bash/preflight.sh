#!/usr/bin/env bash
# Read-only preflight shown before any authorization. It never starts sudo,
# never writes state and never changes packages, services, swap or firewall.
# Disk minima follow the private O/TEST policy (APP 10, DB 20, APP+DB 30 GiB);
# the hard stop mirrors swap_ensure: missing swap plus a 1 GiB reserve.

PREFLIGHT_FAILS=0 PREFLIGHT_WARNS=0
preflight_line() {
  case $1 in
    PASS) printf '  PASS  %s\n' "$2";;
    WARN) printf '  WARN  %s\n' "$2"; PREFLIGHT_WARNS=$((PREFLIGHT_WARNS+1));;
    FAIL) printf '  FAIL  %s\n' "$2"; PREFLIGHT_FAILS=$((PREFLIGHT_FAILS+1));;
    INFO) printf '  INFO  %s\n' "$2";;
  esac
}
preflight_gib() { awk -v b="$1" 'BEGIN {printf "%.1f", b/1073741824}'; }
preflight_installed() { [[ $(dpkg-query -W -f='${Status}' "$1" 2>/dev/null) == 'install ok installed' ]]; }
preflight_port_in_use() {
  # ss output is only parsed; unknown means "not proven free" and is reported.
  local port=$1 listeners
  listeners=$(ss -H -lnt 2>/dev/null) || return 2
  awk -v p=":$port" '{n=split($4,a,":"); if (":" a[n] == p) found=1} END {exit found?0:1}' <<< "$listeners"
}
preflight_minimum_gib() {
  case $1 in app) echo 10;; database) echo 20;; combined) echo 30;; esac
}
preflight_label() {
  case $1 in app) echo 'APP';; database) echo 'DB';; combined) echo 'APP + DB';; esac
}

# preflight_profile PROFILE [all]: "all" adds disk advice for every profile.
preflight_profile() {
  local profile=$1 scope=${2:-one} active shortage available target minimum each
  PREFLIGHT_FAILS=0 PREFLIGHT_WARNS=0
  local title='alle profielen'
  [[ $scope == all ]] || title=$(preflight_label "$profile")
  printf 'Controle (read-only) voor %s:\n' "$title"
  preflight_line INFO 'Doel: TEST-/ontwikkelserver. Deze release is niet voor productie gevalideerd.'
  if (( EUID == 0 )); then
    preflight_line PASS 'Rechten: gestart als root'
  elif command -v sudo >/dev/null; then
    preflight_line PASS 'Rechten: sudo aanwezig; sudo wordt pas na uw bevestiging gevraagd'
  else
    preflight_line FAIL 'Rechten: sudo ontbreekt; vraag een beheerder of start als root'
  fi

  active=$(swap_active_bytes 2>/dev/null) || active=''
  if [[ $active =~ ^[0-9]+$ ]]; then
    shortage=$(( active >= 4294967296 ? 0 : 4294967296-active ))
    preflight_line INFO "Swap: actief $(preflight_gib "$active") GiB; aan te maken $(preflight_gib "$shortage") GiB (minimaal 4 GiB totaal)"
  else
    shortage=4294967296
    preflight_line WARN 'Swap: actieve swap onbekend; rekening gehouden met 4 GiB aanmaak'
  fi
  if [[ -e $STATE_DIR && ! -x $STATE_DIR ]]; then
    preflight_line WARN 'Bestaande installerstatus is afgeschermd; volledige controle alleen als administrator'
  elif [[ -e $ROOT/var/lib/universal-linux-installer/swapfile && ! -e $STATE_DIR/swap-owner ]]; then
    preflight_line FAIL 'Swap: onbekend bestaand installer-swapbestand; wordt niet overschreven'
  fi

  target=$STATE_DIR
  while [[ ! -e $target && $target == */* ]]; do target=${target%/*}; done
  [[ -n $target ]] || target=/
  available=$(df -B1 --output=avail -- "$target" 2>/dev/null | tail -1 | tr -d ' ') || available=''
  if [[ ! $available =~ ^[0-9]+$ ]]; then
    preflight_line WARN 'Schijf: vrije ruimte onbekend'
  else
    if (( shortage > 0 && available < shortage + 1073741824 )); then
      preflight_line FAIL "Schijf: $(preflight_gib "$available") GiB vrij; nodig voor swap plus 1 GiB reserve: $(preflight_gib $((shortage + 1073741824))) GiB"
    fi
    for each in app database combined; do
      [[ $scope == all || $each == "$profile" ]] || continue
      minimum=$(preflight_minimum_gib "$each")
      if (( available >= minimum * 1073741824 )); then
        preflight_line PASS "Schijf $(preflight_label "$each"): $(preflight_gib "$available") GiB vrij (advies minimaal $minimum GiB)"
      else
        preflight_line WARN "Schijf $(preflight_label "$each"): $(preflight_gib "$available") GiB vrij; advies minimaal $minimum GiB"
      fi
    done
  fi

  if [[ $profile != database || $scope == all ]]; then
    if preflight_installed nginx; then
      preflight_line WARN 'APP: Nginx is al geïnstalleerd; bestaande configuratie wordt niet vervangen'
    else
      for each in 80 443; do
        preflight_port_in_use "$each" && preflight_line FAIL "APP: TCP $each is in gebruik door een andere dienst; installatie zou conflicteren"
        [[ $? != 2 ]] || { preflight_line WARN 'APP: poortgebruik onbekend (ss ontbreekt)'; break; }
      done
    fi
  fi
  if [[ $profile != app || $scope == all ]]; then
    if preflight_installed postgresql-18; then
      preflight_line WARN 'DB: PostgreSQL 18 is al aanwezig; data en configuratie worden nooit overschreven (onbekende configuratie = STOP)'
    else
      if compgen -G "$ROOT/var/lib/postgresql/*" >/dev/null 2>&1; then
        preflight_line WARN 'DB: bestaande PostgreSQL-data van een andere versie gevonden; wordt niet aangeraakt'
      fi
      preflight_port_in_use 5432 && preflight_line FAIL 'DB: TCP 5432 is in gebruik door een andere dienst; nieuwe cluster zou een afwijkende poort krijgen'
      [[ $? != 2 ]] || preflight_line WARN 'DB: poortgebruik onbekend (ss ontbreekt)'
    fi
  fi
  preflight_line INFO 'Geen apt upgrade, geen SSH-, firewall- of rebootwijziging; alleen de getoonde pakketten.'
  preflight_line INFO 'Er is geen herstart nodig; de installer herstart de server nooit zelf.'
  if (( PREFLIGHT_FAILS )); then
    printf 'Controle-uitslag: FAIL (%s FAIL, %s WARN)\n' "$PREFLIGHT_FAILS" "$PREFLIGHT_WARNS"
    return 1
  fi
  printf 'Controle-uitslag: %s (%s WARN)\n' "$( (( PREFLIGHT_WARNS )) && echo WARN || echo PASS)" "$PREFLIGHT_WARNS"
}
