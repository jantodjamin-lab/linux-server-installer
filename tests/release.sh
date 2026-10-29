#!/usr/bin/env bash
# Deterministic distribution build: exact payload layout, internal manifest,
# no development files, syntax and an offline menu smoke run from the archive.
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
(cd "$payload" && find . -type f | LC_ALL=C sort) > "$work/layout"
cat > "$work/expected" <<'LAYOUT'
./FILES.sha256
./VERSION
./bash/app.sh
./bash/assets/codex/package-lock.json
./bash/assets/codex/package.json
./bash/checks.sh
./bash/common.sh
./bash/database.sh
./bash/preflight.sh
./bash/progress.sh
./bash/state.sh
./bash/status.sh
./bash/swap.sh
./bash/sysupdate.sh
./install.sh
./tools/register-install-now.sh
LAYOUT
diff -u "$work/expected" "$work/layout"
[[ $(cat "$payload/VERSION") == "$version" ]]
for script in "$payload/install.sh" "$payload"/bash/*.sh "$payload/tools/register-install-now.sh"; do bash -n "$script"; done
tar -tvzf "$archive" --numeric-owner | awk '$2 != "0/0" {bad=1} END {exit bad}'
printf '0\n' | ULI_TEST_MODE=1 ULI_ROOT=$work/root bash "$payload/install.sh" > "$work/menu.txt"
grep -q '5. SYSTEEM BIJWERKEN (APT UPDATE + APT UPGRADE)' "$work/menu.txt"
[[ ! -e $work/root ]]
echo 'PASS release deterministic rebuild, exact payload, external/internal checksum and extracted menu smoke'
