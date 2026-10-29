#!/usr/bin/env bash
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-release-test.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
version=$(cat "$base/VERSION")
bash "$base/tools/release.sh"
archive=$base/release/universal-linux-installer-$version.tar.gz
cp "$archive" "$work/first.tar.gz"
bash "$base/tools/release.sh"
cmp "$work/first.tar.gz" "$archive"
(cd "$base/release" && sha256sum -c SHA256SUMS)
tar -xzf "$archive" -C "$work"
payload=$work/universal-linux-installer-$version
(cd "$payload" && sha256sum -c FILES.sha256 > "$work/manifest-check.log")
[[ -f $payload/bash/assets/codex/package-lock.json ]]
[[ ! -e $payload/archive ]]
if grep -q 'RELEASE-BOOTSTRAP:BEGIN' "$payload/README.md"; then exit 1; fi
bash "$payload/tests/run.sh"
echo 'PASS release deterministic rebuild, external/internal checksum and extracted offline regression'
