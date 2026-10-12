#!/usr/bin/env bash
# Reproducible Bash-only release, with a controlled payload and internal manifest.
set -Eeuo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
version=$(cat "$base/VERSION")
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]
work=$(mktemp -d "${TMPDIR:-/tmp}/uli-release.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
name=universal-linux-installer-$version
mkdir "$work/$name"
for path in install.sh README.md VERSION CHANGELOG.md SECURITY.md bash docs tests tools .github; do
 [[ -e $base/$path && ! -L $base/$path ]]
 cp -a -- "$base/$path" "$work/$name/"
done
# The exact trusted launch command is published after the archive hash exists.
# Removing this external publication block avoids a circular archive checksum
# and makes rebuilds identical before and after README publication.
sed '/^<!-- RELEASE-BOOTSTRAP:BEGIN -->$/,/^<!-- RELEASE-BOOTSTRAP:END -->$/d' "$work/$name/README.md" > "$work/readme"
mv "$work/readme" "$work/$name/README.md"
# Archives are inert; active scripts must not depend on Python or source archive code.
if grep -nE 'archive/|python3?[[:space:]]+-|curl[^#]*\|[[:space:]]*(sudo[[:space:]]+)?(ba)?sh' "$work/$name/install.sh" "$work/$name"/bash/*.sh; then exit 1; fi
if find "$work/$name" -type l -print -quit | grep -q .; then echo 'FAIL symlink in payload' >&2; exit 1; fi
find "$work/$name" -type d -exec chmod 755 {} +
find "$work/$name" -type f -exec chmod 644 {} +
(cd "$work/$name" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "$work/FILES.sha256")
mv "$work/FILES.sha256" "$work/$name/FILES.sha256"
mkdir -p "$base/release"
LC_ALL=C tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner --format=gnu -C "$work" -cf - "$name" | gzip -n > "$base/release/$name.tar.gz"
(cd "$base/release" && sha256sum "$name.tar.gz" > SHA256SUMS)
printf 'PASS reproducible release: %s/release/%s.tar.gz\n' "$base" "$name"
