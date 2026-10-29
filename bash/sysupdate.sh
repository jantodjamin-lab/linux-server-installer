#!/usr/bin/env bash
# Menu 5 / --system-update: explicit "apt update" followed by "apt upgrade".
# Never started implicitly. Sequence:
#   1. read-only checks + `apt-get -s upgrade` plan on the existing index (no root)
#   2. human confirmation (type "bijwerken"), interactive terminal required
#   3. sudo (password only on the terminal) -> installer lock -> re-check plan
#   4. `apt-get update`, new simulation; any change is shown and must be re-confirmed
#   5. `apt-get upgrade` on the terminal: no -y, no dist/full-upgrade, no autoremove,
#      no removals (--no-remove), never a reboot
#   6. dpkg audit, version verification, reboot advice, sanitized audit report
# Raw APT output is never logged: source URLs can contain credentials.

SYSUPDATE_CONFIRM=bijwerken
SYSUPDATE_APT=(apt-get -o DPkg::Lock::Timeout=30 -o APT::Update::Error-Mode=any
  -o Acquire::AllowInsecureRepositories=false -o Acquire::AllowWeakRepositories=false
  -o Acquire::AllowDowngradeToInsecureRepositories=false -o APT::Get::AllowUnauthenticated=false)
SYSUPDATE_PLAN='' SYSUPDATE_DIGEST='' SYSUPDATE_KEPT='' SYSUPDATE_SUMMARY=''

sysupdate_interactive() {
  if [[ ${ULI_TEST_MODE:-0} == 1 && -n ${ULI_TEST_TTY:-} ]]; then [[ $ULI_TEST_TTY == 1 ]]; else [[ -t 0 ]]; fi
}
sysupdate_privileged() {
  (( EUID == 0 )) || [[ ${ULI_TEST_MODE:-0} == 1 && ${ULI_TEST_PRIVILEGED:-0} == 1 ]]
}

# Read-only safety checks; every failure is a STOP before any change.
sysupdate_checks() {
  local audit origins origin
  checks_system || { fail 'Systeemcontrole mislukt; geen update'; return 1; }
  audit=$(dpkg --audit 2>/dev/null) || { fail 'dpkg-status onbekend; geen update'; return 1; }
  [[ -z $audit ]] || { fail 'Onvoltooide dpkg-transactie; eerst handmatig herstellen'; return 1; }
  origins=$(apt-cache policy 2>/dev/null | awk '/release / && /o=/ {n=split($0,a,","); for(i=1;i<=n;i++) if(a[i] ~ /(^|[[:space:]])o=/) {sub(/^.*o=/,"",a[i]); print a[i]}}') || true
  [[ -n $origins ]] || { fail 'APT-repositoryherkomst onbekend; geen update'; return 1; }
  while IFS= read -r origin; do
    [[ $origin == Ubuntu ]] || { fail "Niet-Ubuntu APT-repository ($origin) vereist handmatige beoordeling; geen update"; return 1; }
  done <<< "$origins"
}

# Simulation only. Normalized plan lines: "U name old new" or "N name - new".
sysupdate_simulate() {
  local output line name old new
  local re_upgrade='^Inst ([a-z0-9][a-z0-9+.:~-]*) \[([^]]+)\] \(([^ ]+)' re_new='^Inst ([a-z0-9][a-z0-9+.:~-]*) \(([^ ]+)'
  output=$(LC_ALL=C "${SYSUPDATE_APT[@]}" -s --no-remove --with-new-pkgs upgrade 2>/dev/null) || { fail 'APT-simulatie mislukt; geen update'; return 1; }
  SYSUPDATE_PLAN=''
  while IFS= read -r line; do
    case $line in
      Remv\ *) fail 'Plan verwijdert pakketten; geweigerd (geen removals)'; return 1;;
      Inst\ *)
        if [[ $line =~ $re_upgrade ]]; then
          name=${BASH_REMATCH[1]} old=${BASH_REMATCH[2]} new=${BASH_REMATCH[3]}
          SYSUPDATE_PLAN+="U $name $old $new"$'\n'
        elif [[ $line =~ $re_new ]]; then
          name=${BASH_REMATCH[1]} new=${BASH_REMATCH[2]}
          SYSUPDATE_PLAN+="N $name - $new"$'\n'
        else
          fail 'Onbekende APT-planregel; geweigerd'; return 1
        fi;;
    esac
  done <<< "$output"
  SYSUPDATE_PLAN=$(LC_ALL=C sort <<< "$SYSUPDATE_PLAN" | sed '/^$/d')
  if LC_ALL=C grep -q '[^a-zA-Z0-9.+:~_ -]' <<< "$SYSUPDATE_PLAN"; then fail 'Onveilige tekens in APT-plan; geweigerd'; return 1; fi
  SYSUPDATE_KEPT=$(awk '/^The following packages have been kept back:/ {k=1; next} k && /^  / {print; next} {k=0}' <<< "$output" | xargs) || true
  SYSUPDATE_SUMMARY=$(grep -E '^[0-9]+ upgraded' <<< "$output" | head -1) || true
  SYSUPDATE_DIGEST=$(printf '%s\n' "$SYSUPDATE_PLAN" | sha256sum | awk '{print $1}')
}

sysupdate_render() {
  local count new_count holds free_root free_var services reboot pretty
  count=$(grep -c '^U ' <<< "$SYSUPDATE_PLAN") || true
  new_count=$(grep -c '^N ' <<< "$SYSUPDATE_PLAN") || true
  pretty=$(. "${ULI_OS_RELEASE:-/etc/os-release}" 2>/dev/null && printf '%s' "${PRETTY_NAME:-onbekend}") || pretty=onbekend
  printf 'Systeem bijwerken — plan (read-only, %s)\n' "$1"
  printf '  OS: %s\n' "$pretty"
  printf '  Upgrades: %s pakket(ten); nieuw te installeren: %s; te verwijderen: 0\n' "${count:-0}" "${new_count:-0}"
  [[ -z $SYSUPDATE_SUMMARY ]] || printf '  APT: %s\n' "$SYSUPDATE_SUMMARY"
  if [[ -n $SYSUPDATE_PLAN ]]; then
    awk '{ if ($1=="U") printf "    %s %s -> %s\n",$2,$3,$4; else printf "    %s (nieuw) %s\n",$2,$4 }' <<< "$SYSUPDATE_PLAN" | head -40
    (( count + new_count <= 40 )) || printf '    ... en %s meer\n' "$((count + new_count - 40))"
  fi
  holds=$(apt-mark showhold 2>/dev/null | xargs) || holds=''
  [[ -z $holds ]] || printf '  %s  Vastgehouden (hold), blijven ongewijzigd: %s\n' "$(ui_label WARN)" "$holds"
  [[ -z $SYSUPDATE_KEPT ]] || printf '  %s  Tegengehouden door APT (kept back): %s\n' "$(ui_label WARN)" "$SYSUPDATE_KEPT"
  free_root=$(df -B1 --output=avail / 2>/dev/null | tail -1 | tr -d ' ') || free_root=''
  free_var=$(df -B1 --output=avail /var 2>/dev/null | tail -1 | tr -d ' ') || free_var=''
  if [[ $free_root =~ ^[0-9]+$ && $free_var =~ ^[0-9]+$ ]]; then
    if (( free_var < 1073741824 || free_root < 1073741824 )); then
      printf '  %s  Schijf: / %s GiB, /var %s GiB vrij (minder dan 1 GiB)\n' "$(ui_label WARN)" "$(preflight_gib "$free_root")" "$(preflight_gib "$free_var")"
    else
      printf '  %s  Schijf: / %s GiB, /var %s GiB vrij\n' "$(ui_label PASS)" "$(preflight_gib "$free_root")" "$(preflight_gib "$free_var")"
    fi
  else
    printf '  %s  Schijf: vrije ruimte onbekend\n' "$(ui_label WARN)"
  fi
  services=$(awk '$2 ~ /^(nginx|nginx-.*|postgresql-[0-9]+|openssh-server|systemd|dbus|libc6|libssl3.*|containerd|docker.*|apache2|mysql-server.*|mariadb-server.*|cron|rsyslog|snapd)$/ {print $2}' <<< "$SYSUPDATE_PLAN" | xargs) || services=''
  [[ -z $services ]] || printf '  %s  Mogelijke korte dienstonderbreking (herstart door pakket): %s\n' "$(ui_label WARN)" "$services"
  reboot=$(awk '$2 ~ /^(linux-image-.*|linux-modules-.*|linux-generic.*|linux-firmware|libc6|systemd)$/ {print $2}' <<< "$SYSUPDATE_PLAN" | xargs) || reboot=''
  if [[ -e ${ROOT}/run/reboot-required ]]; then printf '  %s  Herstart is nu al aanbevolen door het systeem\n' "$(ui_label WARN)"; fi
  [[ -z $reboot ]] || printf '  %s  Herstart waarschijnlijk nodig na deze upgrade (%s); de installer herstart nooit zelf\n' "$(ui_label WARN)" "$reboot"
  printf '  Geen dist-upgrade/full-upgrade, geen autoremove, geen verwijderingen, geen -y, geen automatische herstart.\n'
}

sysupdate_confirm() {
  local answer
  sysupdate_interactive || { fail 'Bevestiging vereist een interactieve terminal; er is niets gewijzigd'; return 2; }
  printf '%s' "$1"
  IFS= read -r answer || { printf '\n'; fail 'Geen bevestiging ontvangen; er is niets gewijzigd'; return 2; }
  [[ $answer == "$SYSUPDATE_CONFIRM" ]]
}

sysupdate_report() {
  # Sanitized audit trail: only plan identifiers, exit codes and verdicts.
  local file=$STATE_DIR/system-update-$SYSUPDATE_STARTED.txt
  [[ -n ${SYSUPDATE_STARTED:-} && -d $STATE_DIR && ! -L $STATE_DIR ]] || return 0
  (umask 077
   { printf 'UNIVERSAL LINUX INSTALLER — SYSTEEMUPDATE\nInstaller: %s\nStart (UTC): %s\nEinde (UTC): %s\n' "$VERSION" "$SYSUPDATE_STARTED" "$(date -u +%FT%TZ)"
     printf 'Goedgekeurd plan: %s\nUitgevoerd plan: %s\nResultaat: %s\nAPT update exit: %s\nAPT upgrade exit: %s\nHerstart aanbevolen: %s\nPakketten (naam oud nieuw):\n' \
       "${SYSUPDATE_APPROVED:-geen}" "${SYSUPDATE_DIGEST:-geen}" "$1" "${SYSUPDATE_UPDATE_EXIT:-niet uitgevoerd}" "${SYSUPDATE_UPGRADE_EXIT:-niet uitgevoerd}" "${SYSUPDATE_REBOOT:-onbekend}"
     printf '%s\n' "${SYSUPDATE_PLAN:-geen}"
   } > "$file") || return 0
  chmod 600 "$file" 2>/dev/null || true
  printf 'Auditrapport: %s (administrator)\n' "$file"
}

sysupdate_finish() {
  sysupdate_report "$1"
  [[ $1 == FAIL ]] && return 1
  return 0
}

# Unprivileged entry: plan, confirm, then sudo for the privileged phase.
sysupdate_main() {
  local approved=${1:-} result
  printf 'SYSTEEM BIJWERKEN (APT UPDATE + APT UPGRADE)\n'
  sysupdate_interactive || { fail 'Systeem bijwerken vereist een interactieve terminal; er is niets gewijzigd'; return 1; }
  if [[ -n $approved ]]; then
    sysupdate_privileged || { fail 'Goedgekeurd plan vereist administratorrechten'; return 1; }
    sysupdate_apply "$approved"; return
  fi
  sysupdate_checks || return 1
  sysupdate_simulate || return 1
  sysupdate_render 'lokale pakketindex; na bevestiging eerst apt-get update en een nieuw plan'
  sysupdate_confirm "Typ $SYSUPDATE_CONFIRM om apt-get update en daarna apt-get upgrade uit te voeren (Enter = annuleren): " || {
    result=$?; (( result == 2 )) && return 1
    pass 'Systeemupdate geannuleerd; er is niets gewijzigd'; return 0; }
  if sysupdate_privileged; then sysupdate_apply "$SYSUPDATE_DIGEST"; return; fi
  command -v sudo >/dev/null || { fail 'sudo ontbreekt; er is niets gewijzigd'; return 1; }
  printf 'sudo vraagt nu zo nodig om uw wachtwoord (alleen via de terminal).\n'
  result=0
  sudo -- /bin/bash "$INSTALLER_DIR/install.sh" --system-update --approved-plan "$SYSUPDATE_DIGEST" || result=$?
  (( result == 0 )) || fail "Systeemupdate niet voltooid of sudo geweigerd (exit $result)"
  return "$result"
}

# Privileged phase; holds the installer lock so installation and update never overlap.
sysupdate_apply() {
  SYSUPDATE_APPROVED=$1 SYSUPDATE_STARTED=$(date -u +%Y%m%dT%H%M%SZ)
  local result package old new installed mismatched=0
  [[ $SYSUPDATE_APPROVED =~ ^[a-f0-9]{64}$ ]] || { fail 'Ongeldige plangoedkeuring'; return 1; }
  state_prepare || { fail 'Installatielock bezet of status onveilig; geen update'; SYSUPDATE_STARTED=''; return 1; }
  if [[ $STATUS == running || ( $STATUS == failed && -n $CURRENT ) ]]; then
    fail 'Onderbroken of mislukte installatie; eerst installatie afronden of beoordelen'; sysupdate_finish FAIL; return 1
  fi
  sysupdate_checks || { sysupdate_finish FAIL; return 1; }
  sysupdate_simulate || { sysupdate_finish FAIL; return 1; }
  if [[ $SYSUPDATE_DIGEST != "$SYSUPDATE_APPROVED" ]]; then
    warn 'Het plan is gewijzigd sinds uw bevestiging'
    sysupdate_render 'gewijzigd sinds bevestiging'
    sysupdate_confirm "Typ $SYSUPDATE_CONFIRM om met dit gewijzigde plan door te gaan (Enter = stoppen): " || { fail 'Gewijzigd plan niet bevestigd; geen update'; sysupdate_finish FAIL; return 1; }
    SYSUPDATE_APPROVED=$SYSUPDATE_DIGEST
  fi
  # Step 1: apt update (refresh signed metadata).
  SYSUPDATE_UPDATE_EXIT=0
  ULI_APT_LOCK_TIMEOUT=30 run_apt update || SYSUPDATE_UPDATE_EXIT=$?
  (( SYSUPDATE_UPDATE_EXIT == 0 )) || { fail 'apt-get update mislukt; geen upgrade'; sysupdate_finish FAIL; return 1; }
  sysupdate_checks || { sysupdate_finish FAIL; return 1; }
  sysupdate_simulate || { sysupdate_finish FAIL; return 1; }
  if [[ $SYSUPDATE_DIGEST != "$SYSUPDATE_APPROVED" ]]; then
    sysupdate_render 'na apt-get update'
    sysupdate_confirm "Na het verversen is het plan anders. Typ $SYSUPDATE_CONFIRM om dit plan uit te voeren (Enter = stoppen): " || {
      pass 'Upgrade gestopt na apt-get update; alleen de pakketindex is ververst'; sysupdate_finish CANCELLED; return 0; }
    SYSUPDATE_APPROVED=$SYSUPDATE_DIGEST
  fi
  if [[ -z $SYSUPDATE_PLAN ]]; then
    SYSUPDATE_REBOOT=nee; [[ ! -e $ROOT/run/reboot-required ]] || SYSUPDATE_REBOOT=ja
    pass 'Systeem is up-to-date; geen upgrade nodig'; sysupdate_finish PASS; return 0
  fi
  # Step 2: apt upgrade on the operator's terminal; APT asks its own Y/n.
  printf 'apt-get upgrade start; APT vraagt zelf nog om bevestiging. Uitvoer wordt niet gelogd.\n'
  SYSUPDATE_UPGRADE_EXIT=0
  LC_ALL=C "${SYSUPDATE_APT[@]}" --no-remove --with-new-pkgs upgrade || SYSUPDATE_UPGRADE_EXIT=$?
  result=$(dpkg --audit 2>/dev/null) || result='onbekend'
  if [[ -n $result ]]; then
    fail 'dpkg meldt een onvoltooide transactie; handmatig herstel na beoordeling (geen automatische reparatie)'
    sysupdate_finish FAIL; return 1
  fi
  while read -r _ package old new; do
    [[ -n ${package:-} ]] || continue
    installed=$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null) || installed=''
    [[ $installed == "$new" ]] || mismatched=$((mismatched+1))
  done <<< "$SYSUPDATE_PLAN"
  SYSUPDATE_REBOOT=nee; [[ ! -e $ROOT/run/reboot-required ]] || SYSUPDATE_REBOOT=ja
  if (( SYSUPDATE_UPGRADE_EXIT != 0 )); then
    fail "apt-get upgrade niet voltooid (exit $SYSUPDATE_UPGRADE_EXIT); $mismatched pakket(ten) niet op de geplande versie"
    sysupdate_finish FAIL; return 1
  fi
  if (( mismatched )); then
    fail "$mismatched pakket(ten) wijken af van het plan; handmatige beoordeling"; sysupdate_finish FAIL; return 1
  fi
  pass "Systeemupdate voltooid: $(grep -c . <<< "$SYSUPDATE_PLAN") pakket(ten) op de geplande versie"
  if [[ $SYSUPDATE_REBOOT == ja ]]; then warn 'Herstart aanbevolen; plan die zelf in (de installer herstart niet)'
  else pass 'Geen herstart gemeld'; fi
  if [[ ${PROFILE:-} =~ ^(app|database|combined)$ && $STATUS == complete ]]; then
    printf 'Controleer daarna de installatie via menukeuze 4 (status).\n'
  fi
  sysupdate_finish PASS
}
