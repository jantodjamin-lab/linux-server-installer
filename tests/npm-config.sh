#!/usr/bin/env bash
# Real npm configuration regression; no package install, network or host changes.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-npm-config-test.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
install -m 600 /dev/null "$work/user.npmrc"
install -m 600 /dev/null "$work/global.npmrc"
# Ensure the installer keeps distinct config paths instead of double-loading /dev/null.
# shellcheck disable=SC2016
grep -Fq -- '--userconfig="$npm_work/user.npmrc" --globalconfig="$npm_work/global.npmrc"' "$base/bash/app.sh"
if command -v npm >/dev/null; then
  env -i PATH=/usr/bin:/bin HOME="$work" npm --version \
    --userconfig="$work/user.npmrc" --globalconfig="$work/global.npmrc" > "$work/npm-version" 2> "$work/private-output"
  grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+' "$work/npm-version"
  echo 'PASS real npm loads distinct empty user/global configurations'
else
  echo 'WARN real npm configuration smoke requires npm (executed in APP VMs)'
fi
