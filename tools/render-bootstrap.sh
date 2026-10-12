#!/usr/bin/env bash
# Render only after tools/release.sh. Generated artifacts stay outside its archive.
set -Eeuo pipefail
umask 077
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ $# -ge 3 && $# -le 5 ]] || { printf 'Usage: bash tools/render-bootstrap.sh VERSION ARCHIVE OUTPUT_DIR [ARCHIVE_HTTPS_URL [BOOTSTRAP_HTTPS_URL]]\n' >&2; exit 1; }
version=$1 archive=$2 output=$3
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ && -f $archive && ! -L $archive && ! -L $output ]] || exit 1
archive_url=${4:-https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v$version/universal-linux-installer-$version.tar.gz}
bootstrap_url=${5:-https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v$version/bootstrap.sh}
for url in "$archive_url" "$bootstrap_url"; do [[ $url =~ ^https://[a-zA-Z0-9._:/%+@=?\&-]+$ ]] || { printf 'FAIL invalid HTTPS URL\n' >&2; exit 1; }; done
archive_sha=$(sha256sum "$archive" | awk '{print $1}')
mkdir -p -- "$output"
while IFS= read -r line || [[ -n $line ]]; do
  line=${line//@@VERSION@@/$version}
  line=${line//@@SHA256@@/$archive_sha}
  line=${line//@@URL@@/$archive_url}
  printf '%s\n' "$line"
done < "$base/tools/bootstrap-template.sh" > "$output/bootstrap.sh"
bash -n "$output/bootstrap.sh"
bootstrap_sha=$(sha256sum "$output/bootstrap.sh" | awk '{print $1}')
printf '%s  bootstrap.sh\n' "$bootstrap_sha" > "$output/BOOTSTRAP.sha256"
# The user-reviewed one-liner pins the bootstrap; that bootstrap pins the archive.
# Avoid sourcing the downloaded script or executing it before SHA and syntax checks.
# This is literal source for the generated Bash loader.
# shellcheck disable=SC2016
loader='set -Eeuo pipefail; trap '\''printf "FAIL bootstrapdownload of validatie\n" >&2'\'' ERR; umask 077; command -v curl >/dev/null; command -v sha256sum >/dev/null; exec 3<>/dev/tty; w=$(mktemp -d "${TMPDIR:-/tmp}/uli-loader.XXXXXXXX"); trap '\''rm -rf -- "$w"'\'' EXIT; curl -q --fail --location --proto =https --proto-redir =https --connect-timeout 30 --max-time 300 --max-filesize 262144 "@@BOOTSTRAP_URL@@" --output "$w/bootstrap.sh"; [[ -f $w/bootstrap.sh && ! -L $w/bootstrap.sh && $(wc -c < "$w/bootstrap.sh") -le 262144 ]]; printf '\''@@BOOTSTRAP_SHA@@  %s\n'\'' "$w/bootstrap.sh" | sha256sum --check --status; bash -n "$w/bootstrap.sh"; bash "$w/bootstrap.sh" "$@" <&3 >&3 2>&3'
loader=${loader//@@BOOTSTRAP_URL@@/$bootstrap_url}
loader=${loader//@@BOOTSTRAP_SHA@@/$bootstrap_sha}
# %q is Bash quoting; JSON serialization is never used for shell source.
printf 'bash -c %q --\n' "$loader" > "$output/ONE-LINER.txt"
printf 'bash -c %q install-now --register-install-now\n' "$loader" > "$output/BOOTSTRAP-INSTALL-NOW.txt"
chmod 600 "$output/BOOTSTRAP-INSTALL-NOW.txt"
printf 'PASS rendered bootstrap for %s\nArchive SHA256: %s\nBootstrap SHA256: %s\n' "$version" "$archive_sha" "$bootstrap_sha"
