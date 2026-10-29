#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LC_ALL=C
INSTALLER_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
VERSION=$(cat "$INSTALLER_DIR/VERSION")
for module in common checks state swap app database progress preflight; do source "$INSTALLER_DIR/bash/$module.sh"; done
requested='' yes=0 mode=menu completed_patch_upgrade=0 migration_preparing=0
while (( $# )); do
  case $1 in
    --profile) (( $# >= 2 )) || { fail 'Profiel ontbreekt'; exit 1; }; requested=$2; shift;;
    --yes) yes=1;;
    --resume) mode=resume;;
    --audit) mode=audit;;
    --status) mode=status;;
    --help) printf 'bash install.sh [--profile app|database|combined --yes] [--audit|--status|--resume]\n--audit is de read-only Controle (menukeuze 4).\n'; exit 0;;
    *) fail "Onbekend argument: $1"; exit 1;;
  esac
  shift
done
show_status() {
  local public=$ROOT/var/lib/universal-linux-installer-status/status
  if (( EUID != 0 )) && [[ ${ULI_TEST_MODE:-0} != 1 ]]; then
    if [[ -f $public && ! -L $public && $(stat -c %u "$public") == 0 && $(stat -c %a "$public") == 644 ]]; then
      cat "$public"; return
    fi
    if [[ -e $STATE_DIR ]]; then
      printf 'WARN Bestaande private status: bekijk als administrator met bash install.sh --status.\n'; return
    fi
  fi
  state_load || return
  printf 'Voortgang: %s\n' "$(state_progress)"
  printf 'Installerversie: %s\nGeregistreerde versie: %s\nProfiel: %s\nStatus: %s\nVoltooide stappen: %s\nActuele stap: %s\nStart: %s\nEinde: %s\nLaatste wijziging: %s\nLaatste fout: %s\nLog: %s/install.log\n' "$VERSION" "${STATE_VERSION:-geen}" "${PROFILE:-geen}" "${STATUS^^}" "${COMPLETED:-geen}" "${CURRENT:-geen}" "${STARTED:-geen}" "${ENDED:-geen}" "${UPDATED:-geen}" "${LAST_ERROR:-geen}" "$STATE_DIR"
}
if [[ $mode == status ]]; then show_status; exit; fi
run_control() {
  # Read-only: no sudo, no state or package writes. Exit 1 when a FAIL is found.
  local result=0
  checks_system || result=1
  preflight_profile combined all || result=1
  show_status || result=1
  return "$result"
}
if [[ $mode == audit ]]; then run_control; exit; fi
if [[ $mode == menu && -z $requested ]]; then
  while :; do
    printf 'Universal Linux Installer %s\n1) APP       — applicatieserver\n2) DB        — databaseserver\n3) APP + DB  — gecombineerde server\n4) Controle  — read-only preflight\n0) Stoppen\nMaak uw keuze [0-4]: ' "$VERSION"
    read -r choice || { fail 'Geen menukeuze ontvangen; er is niets gewijzigd'; exit 1; }
    case $choice in
      1) requested=app; break;; 2) requested=database; break;; 3) requested=combined; break;;
      4) run_control; exit;;
      # 5 was "Afsluiten" in 1.0.0-bash.3/.4; kept as a silent alias for muscle memory.
      0|5) pass 'Gestopt; er is niets gewijzigd'; exit 0;;
      *) warn 'Ongeldige keuze; kies 0, 1, 2, 3 of 4.';;
    esac
  done
fi
case $requested in APP|app) requested=app;; DB|database) requested=database;; APP+DB|combined) requested=combined;; '') ;; *) fail 'Ongeldig profiel'; exit 1;; esac
checks_system
if [[ $mode != resume ]]; then
  printf 'Installatieplan: profiel %s; minimaal 4 GiB swap; getekende pakketten; automatische hervatting en eindvalidatie.\n' "$requested"
  [[ $requested == database ]] || printf 'APP: Git, Python 3 ontwikkeltool, .NET 10 SDK, Node.js/npm, Codex CLI %s, Nginx.\n' "$CODEX_VERSION"
  [[ $requested == app ]] || printf 'DATABASE: PostgreSQL 18, lokale toegang, servicecontrole.\n'
  active=$(swap_active_bytes)
  printf 'Actieve swap: %s bytes; noodzakelijk tekort: %s bytes.\n' "$active" "$((active >= 4294967296 ? 0 : 4294967296-active))"
  if ! preflight_profile "$requested"; then
    fail 'Installatieplan geblokkeerd door FAIL in de controle; er is niets gewijzigd'
    exit 1
  fi
  if (( ! yes )); then
    printf 'Bevestig installatie met ja [ja/nee]: '
    read -r answer || { fail 'Geen bevestiging ontvangen'; exit 1; }
    if [[ $answer != ja ]]; then pass 'Installatie geannuleerd; geen systeemwijzigingen'; exit 0; fi
  fi
fi
if (( EUID != 0 )); then
  [[ $mode != resume ]] || { fail 'Automatisch hervatten vereist root'; exit 1; }
  command -v sudo >/dev/null || { fail 'sudo ontbreekt; start met sudo bash install.sh'; exit 1; }
  exec sudo -- /bin/bash "$INSTALLER_DIR/install.sh" --profile "$requested" --yes
fi
state_prepare
if [[ $mode == resume ]]; then
  [[ -n $PROFILE ]] || { fail 'Geen geautoriseerd profiel'; exit 1; }
  if [[ $STATE_VERSION != "$VERSION" ]]; then
    if state_codex_patch_eligible && state_codex_patch_authorized; then completed_patch_upgrade=1
    else fail 'Versieverschil bij hervatting'; exit 1; fi
  fi
else
  if [[ -n $PROFILE && $PROFILE != "$requested" ]]; then fail 'Bestaand profiel verschilt; handmatige beoordeling vereist'; exit 1; fi
  if [[ -n $STATE_VERSION && $STATE_VERSION != "$VERSION" ]]; then
    if state_codex_patch_eligible; then completed_patch_upgrade=1
    else fail 'Bestaande status gebruikt een andere installerversie'; exit 1; fi
  fi
  PROFILE=$requested
fi
migration_preparing=$completed_patch_upgrade
trap progress_stop EXIT
if [[ ${TERM:-dumb} != dumb && -t 1 ]]; then
  { exec {PROGRESS_FD}>/dev/tty; } 2>/dev/null || true
fi
[[ ! -L $STATE_DIR/install.log ]] || { fail 'Onveilig logbestand'; exit 1; }
if [[ -e $STATE_DIR/install.log ]]; then
  [[ -f $STATE_DIR/install.log && $(stat -c %u "$STATE_DIR/install.log") == 0 && $(stat -c %a "$STATE_DIR/install.log") == 600 ]] || { fail 'Onveilige logrechten'; exit 1; }
fi
exec > >(exec 9>&-; tee -a "$STATE_DIR/install.log") 2>&1
readonly INSTALLER_OWNER_PID=$BASHPID
installer_error() {
  local result=$1
  # ERR is inherited by command substitutions under set -E. Only the process
  # holding the installation lock may persist failure; synchronous child errors
  # still propagate to that owner through their exit status.
  if [[ $BASHPID != "$INSTALLER_OWNER_PID" ]]; then exit "$result"; fi
  trap - ERR INT TERM HUP
  if (( migration_preparing )); then
    fail "Migratievoorbereiding onderbroken; oorspronkelijke status behouden. Log: $STATE_DIR/install.log" || true
    exit "$result"
  fi
  STATUS=failed LAST_ERROR=step_${CURRENT:-verification}_exit_${result}
  ENDED=$(date -u +%FT%TZ)
  fail "Stap ${CURRENT:-verification} onderbroken (exit $result); log: $STATE_DIR/install.log" || true
  state_save || true
  exit "$result"
}
trap 'installer_error "$?"' ERR
trap 'installer_error 130' INT
trap 'installer_error 143' TERM
trap 'installer_error 129' HUP
STARTED=${STARTED:-$(date -u +%FT%TZ)}
progress_init "$PROFILE"
PROGRESS_INSTALL_STARTED=$(date -u -d "$STARTED" +%s)
progress_snapshot
for recorded_phase in $COMPLETED; do
  if progress_known "$recorded_phase"; then progress_done "$recorded_phase"; fi
done
log "RUNNING Installer $VERSION; profiel $PROFILE; modus $mode"
declare -A STEP_LABELS=([system]='Systeem- en compatibiliteitscontrole' [plan]='APT-bronnen en pakketbeschikbaarheid' [swap]='Swap controleren en minimaal 4 GiB realiseren' [app_packages]='APP-software installeren' [codex]='Codex installeren en als gewone gebruiker valideren' [nginx]='Nginx installeren en controleren' [postgres]='PostgreSQL 18 installeren' [database_check]='Databaseconfiguratie en service controleren' [resume]='Persistente configuratie en automatische resume controleren' [verification]='Eindvalidatie en installatierapport')
if [[ $STATUS == complete || $CURRENT == verification || " $COMPLETED " == *' verification '* ]]; then
  CURRENT=verification
  pending_completed=''
  for recorded_phase in $COMPLETED; do
    [[ $recorded_phase == verification ]] || pending_completed="${pending_completed:+$pending_completed }$recorded_phase"
  done
  COMPLETED=$pending_completed
  progress_invalidate verification
  progress_begin verification "${STEP_LABELS[verification]}"
  if (( completed_patch_upgrade )); then
    migration_preparing=1
    if ! state_authorize_codex_patch || ! resume_service_install; then
      fail 'Versiemigratie niet voorbereid; oorspronkelijke status behouden, geautoriseerd herhalen vereist' || true
      exit 1
    fi
    migration_preparing=0
  else
    STATUS=running CURRENT=verification
    state_save
  fi
  CURRENT=verification
  if ! swap_ensure verify; then installer_error 1; fi
  if [[ $PROFILE != app ]] && ! database_verify; then installer_error 1; fi
  if [[ $PROFILE != database ]]; then
    if ! app_codex_permissions_repair || ! app_verify; then installer_error 1; fi
  fi
  resume_service_install
  state_login_status_install
  COMPLETED=''
  # shellcheck disable=SC2153 # Array populated by sourced progress_init.
  for phase in "${PROGRESS_IDS[@]}"; do
    COMPLETED="${COMPLETED:+$COMPLETED }$phase"
    progress_done "$phase"
  done
  CURRENT='' STATUS=complete ENDED=$(date -u +%FT%TZ)
  state_save
  if (( completed_patch_upgrade )); then rm -f -- "$STATE_DIR/codex-permissions-patch" || warn 'Patchmarker blijft afgeschermd bewaard'; fi
  pass 'COMPLETE Installatie reeds afgerond en gecontroleerd'; exit
fi
STATUS=running ENDED=''; state_save
# A reboot must not turn an uncertain interrupted dpkg transaction into an
# automatic repair merely because the earlier package-plan phase completed.
case $CURRENT in
  app_packages|nginx|postgres)
    dpkg_audit=$(dpkg --audit)
    [[ -z $dpkg_audit ]] || { fail 'Onvoltooide dpkg-transactie; handmatig onderzoek vereist'; exit 1; }
  ;;
esac
# Stage safe reboot code before the first package/swap mutation. Count resume
# only when the final persistent configuration has also been verified.
resume_service_install
state_login_status_install
state_step system checks_system
plan_install() { run_apt update && checks_packages; }
state_step plan plan_install
CURRENT=swap; state_save
progress_begin swap "${STEP_LABELS[swap]}"
swap_ensure
if [[ " $COMPLETED " != *' swap '* ]]; then COMPLETED="${COMPLETED:+$COMPLETED }swap"; fi
CURRENT=''; state_save; progress_done swap
if [[ $PROFILE != database ]]; then
  state_step app_packages app_packages_install
  state_step codex app_codex_install
  state_step nginx app_nginx_install
fi
if [[ $PROFILE != app ]]; then
  state_step postgres database_packages_install
  state_step database_check database_service_install
fi
resume_configuration() { resume_service_install && state_login_status_install; }
state_step resume resume_configuration
final_verification() {
  swap_ensure verify || return
  if [[ $PROFILE != database ]]; then app_codex_permissions_repair && app_verify || return; fi
  [[ $PROFILE == app ]] || database_verify
}
state_step verification final_verification
CURRENT='' STATUS=complete ENDED=$(date -u +%FT%TZ); state_save
pass "COMPLETE Installatie voltooid; log: $STATE_DIR/install.log"
