#!/usr/bin/env bash
# No privileged host writes: a realistic package fixture and mocked UID/runuser.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-codex-permissions.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
source "$base/bash/common.sh"
source "$base/bash/app.sh"
CODEX_PARENT=$work/managed CODEX_DIR=$work/managed/codex CODEX_LINK=$work/codex
stat() {
    if [[ $1 == -c && $2 == %u ]]; then echo 0
    elif [[ $1 == -c && $2 == %a && ( $3 == /opt || $3 == /usr || $3 == /usr/local || $3 == /usr/local/bin ) ]]; then echo 755
    else /usr/bin/stat "$@"; fi
}
runuser() { printf '%s\n' "$*" > "$work/user-probe"; [[ ${DENY_USER:-0} == 0 ]] || return 1; echo 'codex-cli 0.128.0'; }
app_codex_runtime_paths
for directory in "${CODEX_RUNTIME_DIRS[@]}"; do mkdir -p "$directory"; chmod 700 "$directory"; done
for file in "${CODEX_RUNTIME_DATA[@]}"; do printf '{}\n' > "$file"; chmod 600 "$file"; done
for file in "${CODEX_RUNTIME_EXEC[@]}"; do printf '#!/bin/sh\necho codex-cli 0.128.0\n' > "$file"; chmod 700 "$file"; done
printf '0.128.0\n' > "$CODEX_DIR/.uli-managed"; chmod 600 "$CODEX_DIR/.uli-managed"
ln -s ../@openai/codex/bin/codex.js "$CODEX_DIR/node_modules/.bin/codex"
ln -s "$CODEX_DIR/node_modules/.bin/codex" "$CODEX_LINK"
mkdir "$CODEX_DIR/.npm"; chmod 700 "$CODEX_DIR/.npm"
printf 'private fixture\n' > "$CODEX_DIR/.npmrc"; chmod 600 "$CODEX_DIR/.npmrc"
if app_codex_verify; then exit 1; fi
app_codex_permissions_repair
app_codex_verify
[[ $(cat "$work/user-probe") == *'-u nobody -- env -i'* && $(cat "$work/user-probe") == *'HOME=/nonexistent'* ]]
[[ $(stat -c %a "$CODEX_DIR/.uli-managed") == 600 && $(stat -c %a "$CODEX_DIR/.npmrc") == 600 && $(stat -c %a "$CODEX_DIR/.npm") == 700 ]]
app_codex_permissions_repair; app_codex_verify
echo 'PASS Codex 0700 repair, exact public runtime modes, protected marker/cache/config and idempotence'
DENY_USER=1
if app_codex_verify; then exit 1; fi
unset DENY_USER
echo 'PASS Codex verification rejects root-only execution'
chmod 777 "${CODEX_RUNTIME_EXEC[0]}"
if app_codex_permissions_repair; then exit 1; fi
[[ $(stat -c %a "${CODEX_RUNTIME_EXEC[0]}") == 777 ]]
chmod 700 "${CODEX_RUNTIME_EXEC[0]}"
mv "${CODEX_RUNTIME_EXEC[0]}" "$work/original"
ln -s "$work/original" "${CODEX_RUNTIME_EXEC[0]}"
if app_codex_permissions_repair; then exit 1; fi
[[ $(stat -c %a "$work/original") == 700 ]]
echo 'PASS writable or symlinked runtime rejected without chmod of external targets'
