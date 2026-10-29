#!/usr/bin/env bash
# Preserve existing data, users and PostgreSQL configuration.
database_query() {
  runuser -u postgres -- psql --cluster 18/main -X -A -t -v ON_ERROR_STOP=1 -d postgres -c "$1"
}

database_prestart_security() {
  local listen encryption hba
  local -a query=(runuser -u postgres -- /usr/lib/postgresql/18/bin/postgres -D /var/lib/postgresql/18/main -c config_file=/etc/postgresql/18/main/postgresql.conf)
  listen=$("${query[@]}" -C listen_addresses) || return
  case "$listen" in localhost|127.0.0.1|::1|'') ;; *) fail 'Onveilige PostgreSQL luisterconfiguratie; service niet gestart'; return 1;; esac
  encryption=$("${query[@]}" -C password_encryption) || return
  [[ $encryption == scram-sha-256 ]] || return 1
  hba=$("${query[@]}" -C hba_file) || return
  [[ $hba == /* && -f $hba ]] || return 1
  # Fail closed on includes and unfamiliar existing syntax before starting service.
  awk '
    /^[[:space:]]*#/ || NF == 0 {next}
    $1 == "local" && ($4 == "peer" || $4 == "scram-sha-256" || $4 == "reject") {next}
    ($1 == "host" || $1 == "hostssl" || $1 == "hostnossl") && ($4 == "127.0.0.1/32" || $4 == "::1/128") && ($5 == "scram-sha-256" || $5 == "reject") {next}
    {exit 1}
  ' "$hba" || { fail 'Onzekere PostgreSQL HBA-configuratie; service niet gestart'; return 1; }
}

database_verify() {
  [[ $(dpkg-query -W -f='${Status}' postgresql-18 2>/dev/null) == 'install ok installed' ]] || return 1
  systemctl is-active --quiet postgresql@18-main || return
  local version listen encryption insecure
  version=$(database_query 'SHOW server_version_num') || return
  [[ $version =~ ^18[0-9]{4}$ ]] || return 1
  listen=$(database_query 'SHOW listen_addresses') || return
  case "$listen" in localhost|127.0.0.1|::1|'') ;; *) fail 'PostgreSQL luistert buiten loopback; handmatige beoordeling vereist'; return 1;; esac
  encryption=$(database_query 'SHOW password_encryption') || return
  [[ $encryption == scram-sha-256 ]] || { fail 'PostgreSQL vereist SCRAM-wachtwoordversleuteling'; return 1; }
  insecure=$(database_query "SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL OR auth_method NOT IN ('peer','scram-sha-256','reject') OR (type <> 'local' AND (address IS NULL OR address NOT IN ('127.0.0.1','::1') OR netmask NOT IN ('255.255.255.255','ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')))") || return
  [[ $insecure == 0 ]] || { fail 'PostgreSQL HBA wijkt af van veilige lokale standaard; geen automatische wijziging'; return 1; }
}

database_packages_install() {
  # Existing package postinst may start a stopped cluster: validate beforehand.
  if [[ -e /etc/postgresql/18/main/postgresql.conf ]]; then
    database_prestart_security || return
  fi
  uli_apt_install postgresql-18 || return
}

database_service_install() {
  # Distribution postinst creates 18/main only when safe. Never recreate clusters.
  [[ -f /etc/postgresql/18/main/postgresql.conf ]] || {
    fail 'PostgreSQL 18/main ontbreekt; geen automatische clustercreatie bij onzekere toestand'; return 1;
  }
  database_prestart_security || return
  systemctl enable --now postgresql@18-main || return
  database_verify || { fail 'DATABASE service- of beveiligingscontrole mislukt'; return 1; }
  pass 'DATABASE-profiel geïnstalleerd; lokale peer/SCRAM-authenticatie gecontroleerd'
}

database_install() {
  database_packages_install || return
  database_service_install
}
