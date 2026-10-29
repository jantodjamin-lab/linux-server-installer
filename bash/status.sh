#!/usr/bin/env bash
# Compact read-only installation status (menu 4 / --summary). It never starts
# sudo, never writes files and never refreshes package indexes. Unknown or
# unverifiable facts are WARN, never PASS. Details stay in --status.

STATUS_FAILS=0
status_line() {
  printf '  %s  %-22s %s\n' "$(ui_label "$1")" "$2" "$3"
  [[ $1 != FAIL ]] || STATUS_FAILS=$((STATUS_FAILS+1))
}
status_package_version() { dpkg-query -W -f='${Version}' "$1" 2>/dev/null; }
status_service() {
  # systemctl is-active only reads unit state.
  local state
  state=$(systemctl is-active "$1" 2>/dev/null) || true
  printf '%s' "${state:-onbekend}"
}
status_public_field() { awk -F': ' -v k="$1" '$1==k {sub(/^[^:]*: /,""); print; exit}' "$2"; }

# Reads private state when this user may, else the sanitized public status.
status_collect() {
  local public=$ROOT/var/lib/universal-linux-installer-status/status
  STATUS_SOURCE='' STATUS_KIND=''
  local public_only=0
  [[ ${ULI_TEST_MODE:-0} != 1 || ${ULI_TEST_PUBLIC_ONLY:-0} != 1 ]] || public_only=1
  if (( ! public_only )) && { (( EUID == 0 )) || [[ -r $STATE_FILE ]]; }; then
    [[ -e $STATE_FILE ]] || { STATUS_KIND=none; return; }
    STATUS_SOURCE=privé
    if ! state_load 2>/dev/null; then STATUS_KIND=corrupt; return; fi
  elif [[ -f $public && ! -L $public && $(stat -c %u "$public") == 0 ]]; then
    STATUS_SOURCE=openbaar
    PROFILE=$(status_public_field Profiel "$public")
    STATE_VERSION=$(status_public_field Versie "$public")
    COMPLETED=$(status_public_field 'Voltooide stappen' "$public")
    CURRENT=$(status_public_field 'Actuele stap' "$public"); [[ $CURRENT != geen ]] || CURRENT=''
    UPDATED=$(status_public_field 'Laatste wijziging' "$public")
    LAST_ERROR=$(status_public_field 'Laatste fout' "$public"); [[ $LAST_ERROR != geen ]] || LAST_ERROR=''
    case $(status_public_field Status "$public") in
      COMPLETE) STATUS=complete;; RUNNING) STATUS=running;; FAIL) STATUS=failed;; *) STATUS=unknown;;
    esac
    [[ $PROFILE =~ ^(app|database|combined)$ ]] || { STATUS_KIND=corrupt; return; }
  elif [[ -e $STATE_DIR ]]; then
    STATUS_SOURCE=afgeschermd STATUS_KIND=unreadable; return
  else
    STATUS_KIND=none; return
  fi
  case $STATUS in
    ''|new) STATUS_KIND=none;;
    complete) STATUS_KIND=complete;;
    failed)
      # Ctrl+C / TERM / HUP during a step is recorded as failed with the signal exit code.
      if [[ ${LAST_ERROR:-} =~ _exit_(129|130|143)$ ]]; then STATUS_KIND=interrupted; else STATUS_KIND=failed; fi;;
    running)
      # A held installer lock means a live run; a free lock means an interruption.
      STATUS_KIND=running_unknown
      if [[ -r $STATE_DIR/lock && ! -L $STATE_DIR/lock ]] && command -v flock >/dev/null; then
        if ( exec 8<"$STATE_DIR/lock"; flock -n -s 8 ); then STATUS_KIND=interrupted; else STATUS_KIND=running; fi
      fi;;
    *) STATUS_KIND=corrupt;;
  esac
}

status_summary() {
  local version_note last active codex_json codex_installed value state reboot_file updates
  STATUS_FAILS=0
  status_collect
  printf 'INSTALLATIESTATUS (read-only)\n'
  version_note=$VERSION
  [[ -z ${STATE_VERSION:-} || $STATE_VERSION == "$VERSION" ]] || version_note="$VERSION (installatie gedaan met $STATE_VERSION)"
  status_line PASS 'Installer/release' "$version_note"
  case $STATUS_KIND in
    none) status_line PASS 'Toestand' 'niet geïnstalleerd';;
    complete) status_line PASS 'Toestand' 'voltooid';;
    running) status_line WARN 'Toestand' 'bezig (installatie actief)';;
    interrupted) status_line WARN 'Toestand' "onderbroken${LAST_ERROR:+ ($LAST_ERROR)}";;
    running_unknown) status_line WARN 'Toestand' 'bezig of onderbroken (niet vast te stellen zonder administratorrechten)';;
    failed) status_line FAIL 'Toestand' "fout${LAST_ERROR:+ ($LAST_ERROR)}";;
    unreadable) status_line WARN 'Toestand' 'onbekend; status alleen als administrator leesbaar';;
    corrupt) status_line FAIL 'Toestand' 'statusbestand onleesbaar of beschadigd';;
  esac
  if [[ $STATUS_KIND =~ ^(complete|running|interrupted|running_unknown|failed)$ ]]; then
    status_line PASS 'Profiel' "$(preflight_label "$PROFILE") ($PROFILE)"
    value=WARN; [[ $STATUS_KIND != complete ]] || value=PASS
    status_line "$value" 'Stap' "$(state_progress)${CURRENT:+; actueel: $CURRENT}"
    last=${COMPLETED##* }
    status_line PASS 'Laatste geslaagde stap' "${last:-geen} (statuswijziging ${UPDATED:-onbekend} UTC)"
  fi

  if [[ $STATUS_KIND =~ ^(complete|running|interrupted|running_unknown|failed)$ ]]; then
    if [[ $PROFILE != database ]]; then
      value=$(status_package_version nginx) || value=""
      state=$(status_service nginx)
      if [[ -n $value && $state == active ]]; then status_line PASS 'Nginx' "$value; dienst actief"
      else status_line WARN 'Nginx' "${value:-niet geïnstalleerd}; dienst $state"; fi
      codex_json=$ROOT$CODEX_DIR/node_modules/@openai/codex/package.json
      codex_installed=''
      if [[ -f $codex_json && -r $codex_json ]]; then
        codex_installed=$(awk -F'"' '$2=="version" {print $4; exit}' "$codex_json")
      fi
      if [[ $codex_installed == "$CODEX_VERSION" ]]; then status_line PASS 'Codex' "$codex_installed (vereist $CODEX_VERSION)"
      else status_line WARN 'Codex' "${codex_installed:-onbekend} (vereist $CODEX_VERSION)"; fi
    fi
    if [[ $PROFILE != app ]]; then
      value=$(status_package_version postgresql-18) || value=""
      state=$(status_service postgresql@18-main)
      if [[ -n $value && $state == active ]]; then status_line PASS 'PostgreSQL 18' "$value; dienst actief"
      else status_line WARN 'PostgreSQL 18' "${value:-niet geïnstalleerd}; dienst $state"; fi
    fi
  fi
  active=$(swap_active_bytes 2>/dev/null) || active=''
  if [[ ! $active =~ ^[0-9]+$ ]]; then status_line WARN 'Swap' 'onbekend'
  elif (( active >= 4294967296 )); then status_line PASS 'Swap' "$(preflight_gib "$active") GiB actief (minimaal 4)"
  elif [[ $STATUS_KIND == none ]]; then status_line WARN 'Swap' "$(preflight_gib "$active") GiB actief; installatie maakt aan tot 4 GiB"
  else status_line WARN 'Swap' "$(preflight_gib "$active") GiB actief; minder dan vereist (4 GiB)"; fi

  reboot_file=$ROOT/run/reboot-required
  if [[ -e $reboot_file ]]; then status_line WARN 'Herstart' 'aanbevolen door het systeem; de installer herstart nooit zelf'
  elif [[ -d $ROOT/run ]]; then status_line PASS 'Herstart' 'geen herstart gemeld'
  else status_line WARN 'Herstart' 'onbekend'; fi
  # Simulation on the existing local index only; no refresh and no root.
  if value=$(LC_ALL=C apt-get -s upgrade 2>/dev/null); then
    updates=$(awk '/^Inst / {n++} END {print n+0}' <<< "$value")
    if (( updates == 0 )); then status_line PASS 'Updates' 'geen volgens lokale pakketindex'
    else status_line WARN 'Updates' "$updates beschikbaar volgens lokale pakketindex (kies 5)"; fi
  else
    status_line WARN 'Updates' 'onbekend (pakketindex niet leesbaar)'
  fi
  printf '  Log/rapporten: %s/ (administrator)\n' "$STATE_DIR"
  case $STATUS_KIND in
    none) value='kies 6 (controle) en daarna 1, 2 of 3';;
    complete) value='geen actie nodig; systeemupdates via 5';;
    running) value='wacht tot de installatie klaar is';;
    interrupted|running_unknown) value='kies hetzelfde profiel opnieuw om veilig te hervatten, of bekijk het log';;
    failed) value='bekijk het log als administrator; niet blind herhalen';;
    *) value='handmatige beoordeling door administrator; details: --status';;
  esac
  printf '  Volgende veilige actie: %s\n' "$value"
  (( STATUS_FAILS == 0 ))
}
