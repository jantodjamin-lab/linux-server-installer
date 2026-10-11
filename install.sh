#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LC_ALL=C
INSTALLER_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
VERSION=$(cat "$INSTALLER_DIR/VERSION")
for module in common checks state swap app database; do source "$INSTALLER_DIR/bash/$module.sh"; done
requested='' yes=0 mode=menu
while (( $# )); do
  case $1 in
    --profile) (( $# >= 2 )) || { fail 'Profiel ontbreekt'; exit 1; }; requested=$2; shift;;
    --yes) yes=1;;
    --resume) mode=resume;;
    --audit) mode=audit;;
    --status) mode=status;;
    --help) printf 'bash install.sh [--profile app|database|combined --yes] [--audit|--status|--resume]\n'; exit 0;;
    *) fail "Onbekend argument: $1"; exit 1;;
  esac
  shift
done
show_status() {
  state_load || return
  printf 'Profiel: %s\nVersie: %s\nStatus: %s\nVoltooid: %s\nOnderbroken stap: %s\nLaatste wijziging: %s\n' "$PROFILE" "$STATE_VERSION" "$STATUS" "$COMPLETED" "$CURRENT" "$UPDATED"
}
if [[ $mode == status ]]; then show_status; exit; fi
if [[ $mode == audit ]]; then
  checks_system
  printf 'Actieve swap bytes: %s\n' "$(swap_active_bytes)"
  show_status
  exit
fi
if [[ $mode == menu && -z $requested ]]; then
  printf '=====================================\n UNIVERSAL LINUX SERVER INSTALLER\n=====================================\n\n1. APP-server installeren\n2. DATABASE-server installeren\n3. APP + DATABASE installeren\n4. Installatiestatus bekijken\n0. Afsluiten\n\nMaak uw keuze: '
  read -r choice || exit 1
  case $choice in 1) requested=app;; 2) requested=database;; 3) requested=combined;; 4) show_status; exit;; 0) exit;; *) fail 'Ongeldige keuze'; exit 1;; esac
fi
case $requested in APP|app) requested=app;; DB|database) requested=database;; APP+DB|combined) requested=combined;; '') ;; *) fail 'Ongeldig profiel'; exit 1;; esac
checks_system
if [[ $mode != resume ]]; then
  printf 'Installatieplan: profiel %s; minimaal 4 GiB swap; veilige pakketinstallatie; automatische hervatting.\n' "$requested"
  [[ $requested == database ]] || printf 'APP: Git, Python 3 ontwikkeltool, .NET 10 SDK, Node.js/npm, Codex CLI %s, Nginx.\n' "$CODEX_VERSION"
  [[ $requested == app ]] || printf 'DATABASE: PostgreSQL 18, lokale toegang, servicecontrole.\n'
  active=$(swap_active_bytes)
  printf 'Actieve swap: %s bytes; noodzakelijk tekort: %s bytes.\n' "$active" "$((active >= 4294967296 ? 0 : 4294967296-active))"
  if (( ! yes )); then printf 'Bevestig installatie [ja/nee]: '; read -r answer; [[ $answer == ja ]] || exit 0; fi
fi
if (( EUID != 0 )); then
  [[ $mode != resume ]] || { fail 'Automatisch hervatten vereist root'; exit 1; }
  command -v sudo >/dev/null || { fail 'sudo ontbreekt; start met sudo bash install.sh'; exit 1; }
  exec sudo -- /bin/bash "$INSTALLER_DIR/install.sh" --profile "$requested" --yes
fi
state_prepare
if [[ $mode == resume ]]; then
  [[ -n $PROFILE ]] || { fail 'Geen geautoriseerd profiel'; exit 1; }
  [[ $STATE_VERSION == "$VERSION" ]] || { fail 'Versieverschil bij hervatting'; exit 1; }
else
  if [[ -n $PROFILE && $PROFILE != "$requested" ]]; then fail 'Bestaand profiel verschilt; handmatige beoordeling vereist'; exit 1; fi
  if [[ -n $STATE_VERSION && $STATE_VERSION != "$VERSION" ]]; then fail 'Bestaande status gebruikt een andere installerversie'; exit 1; fi
  PROFILE=$requested
fi
if [[ $STATUS == complete ]]; then
  swap_ensure verify
  [[ $PROFILE != app ]] && database_verify
  [[ $PROFILE != database ]] && app_verify
  pass 'Installatie reeds afgerond en gecontroleerd'; exit
fi
STATUS=running; state_save
trap 'result=$?; trap - ERR; fail "Stap ${CURRENT:-verification} onderbroken (exit $result)" || true; STATUS=failed; state_save || true; exit "$result"' ERR
[[ ! -L $STATE_DIR/install.log ]] || { fail 'Onveilig logbestand'; exit 1; }
if [[ -e $STATE_DIR/install.log ]]; then
  [[ -f $STATE_DIR/install.log && $(stat -c %u "$STATE_DIR/install.log") == 0 && $(stat -c %a "$STATE_DIR/install.log") == 600 ]] || { fail 'Onveilige logrechten'; exit 1; }
fi
exec > >(tee -a "$STATE_DIR/install.log") 2>&1
resume_service_install
CURRENT=apt_update; state_save
run_apt update
CURRENT=checks_packages; state_save
checks_packages
# Swap is verified on every authorized run, including after reboot.
CURRENT=swap; state_save
swap_ensure
CURRENT=''; state_save
[[ $PROFILE == database ]] || state_step app app_install
[[ $PROFILE == app ]] || state_step database database_install
[[ $PROFILE == database ]] || app_verify
[[ $PROFILE == app ]] || database_verify
CURRENT='' STATUS=complete; state_save
pass 'Installatie voltooid'
