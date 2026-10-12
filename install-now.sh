#!/usr/bin/env bash
# Registration wrapper v1.0.0-install-now.1; the installer remains Bash.4.
set -Eeuo pipefail
umask 077

fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
[[ $# == 0 ]] || fail 'Deze opdracht registreert alleen install-now; argumenten zijn niet toegestaan'
(( BASH_VERSINFO[0] >= 4 )) || fail 'Bash 4 of nieuwer vereist'
for tool in bash curl sha256sum mktemp wc rm; do
  command -v "$tool" >/dev/null || fail "Hulpmiddel ontbreekt: $tool"
done

readonly bootstrap_url='https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh'
readonly bootstrap_sha='51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d'
# The terminal supplies registration confirmation; script stdin cannot authorize it.
if ! exec 3<>/dev/tty; then fail 'Start zelf vanuit een interactieve terminal'; fi
printf 'Dit eerste script is via HTTPS gedownload, maar niet onafhankelijk geverifieerd.\n'
printf 'De volgende bootstrap wordt wel vóór uitvoering tegen de vastgepinde SHA256 gecontroleerd.\n'
printf 'Deze opdracht registreert alleen install-now; start daarna zelf install-now.\n'

work=$(mktemp -d "${TMPDIR:-/tmp}/uli-install-now-download.XXXXXXXX") || fail 'Veilige tijdelijke map kan niet worden gemaakt'
readonly work
trap 'rm -rf -- "$work"' EXIT
bootstrap=$work/bootstrap.sh
curl -q --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 30 --max-time 300 --max-filesize 262144 \
  "$bootstrap_url" --output "$bootstrap" || fail 'Bootstrapdownload mislukt'
[[ -f $bootstrap && ! -L $bootstrap && $(wc -c < "$bootstrap") -le 262144 ]] || fail 'Onveilig of te groot bootstrapbestand'
printf '%s  %s\n' "$bootstrap_sha" "$bootstrap" | sha256sum --check --status || fail 'Bootstrap SHA256 wijkt af; geen uitvoering'
bash -n "$bootstrap" || fail 'Bootstrap bevat ongeldige Bash-syntax'
bash "$bootstrap" --register-install-now <&3 >&3 2>&3 || fail 'Bootstrapregistratie mislukt'
printf 'Registratieopdracht afgerond. Start bij succesvolle registratie zelf: install-now\n'
