#!/usr/bin/env bash
# Local archive fixtures only: no downloads, sudo or installation.
set -Eeuo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$base/tools/bootstrap-template.sh"
work=$(mktemp -d "${TMPDIR:-/tmp}/uli-bootstrap-tests.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
version=1.0.0-test root=universal-linux-installer-1.0.0-test
mkdir -p "$work/fixture/$root/bash/assets/codex" "$work/fixture/$root/tools" "$work/bin"
for file in install.sh bash/common.sh bash/checks.sh bash/progress.sh bash/state.sh bash/swap.sh bash/app.sh bash/database.sh bash/preflight.sh bash/status.sh bash/sysupdate.sh; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$work/fixture/$root/$file"
done
printf '%s\n' "$version" > "$work/fixture/$root/VERSION"
: > "$work/fixture/$root/FILES.sha256"
printf '{}\n' > "$work/fixture/$root/bash/assets/codex/package.json"
printf '{}\n' > "$work/fixture/$root/bash/assets/codex/package-lock.json"
cp "$base/tools/register-install-now.sh" "$work/fixture/$root/tools/register-install-now.sh"
find "$work/fixture" -type d -exec chmod 755 {} +
find "$work/fixture" -type f -exec chmod 644 {} +
pack() { tar --format=gnu --owner=0 --group=0 --numeric-owner -czf "$1" -C "$work/fixture" "$root"; }
validate() { uli_bootstrap_validate "$1" "$(sha256sum "$1" | awk '{print $1}')" "$version" "$work/listing"; }
pack "$work/valid.tar.gz"
validate "$work/valid.tar.gz"
printf 'PASS bootstrap accepts complete safe release fixture\n'
# A failed pin must stop before even listing untrusted archive bytes.
cat > "$work/bin/tar" <<'MOCK'
#!/usr/bin/env bash
printf invoked > "$BOOTSTRAP_TAR_SENTINEL"
exit 99
MOCK
chmod 755 "$work/bin/tar"
export BOOTSTRAP_TAR_SENTINEL=$work/tar-invoked
if PATH="$work/bin:$PATH" uli_bootstrap_validate "$work/valid.tar.gz" "$(printf '%064d' 0)" "$version" "$work/listing"; then exit 1; fi
[[ ! -e $BOOTSTRAP_TAR_SENTINEL ]]
printf 'PASS tampered SHA rejected before tar inspection\n'
rm -- "$work/bin/tar"
ln -s /etc/passwd "$work/fixture/$root/symlink"
pack "$work/symlink.tar.gz"
if validate "$work/symlink.tar.gz"; then exit 1; fi
rm "$work/fixture/$root/symlink"
printf 'PASS bootstrap rejects symlinks\n'
ln "$work/fixture/$root/install.sh" "$work/fixture/$root/hardlink"
pack "$work/hardlink.tar.gz"
if validate "$work/hardlink.tar.gz"; then exit 1; fi
rm "$work/fixture/$root/hardlink"
printf 'PASS bootstrap rejects hardlinks\n'
# Rename an inert member to traversal without extraction.
tar --format=gnu --owner=0 --group=0 --numeric-owner --transform="s|$root/install.sh|$root/../escape|" -czf "$work/traversal.tar.gz" -C "$work/fixture" "$root"
if validate "$work/traversal.tar.gz"; then exit 1; fi
[[ ! -e $work/escape ]]
printf 'PASS bootstrap rejects traversal\n'
tar --format=gnu --hard-dereference --owner=0 --group=0 --numeric-owner -czf "$work/duplicate.tar.gz" -C "$work/fixture" "$root" "$root/install.sh"
if validate "$work/duplicate.tar.gz"; then exit 1; fi
printf 'PASS bootstrap rejects duplicate paths\n'
printf 'data\n' > "$work/fixture/$root/"$'control\nname'
pack "$work/control.tar.gz"
if validate "$work/control.tar.gz"; then exit 1; fi
rm "$work/fixture/$root/"$'control\nname'
printf 'PASS bootstrap rejects control characters\n'
truncate -s 67108865 "$work/fixture/$root/large"
pack "$work/oversize.tar.gz"
if validate "$work/oversize.tar.gz"; then exit 1; fi
rm "$work/fixture/$root/large"
printf 'PASS bootstrap rejects excessive member size\n'
chmod 4755 "$work/fixture/$root/install.sh"
pack "$work/special.tar.gz"
if validate "$work/special.tar.gz"; then exit 1; fi
chmod 644 "$work/fixture/$root/install.sh"
printf 'PASS bootstrap rejects special permissions\n'
rm "$work/fixture/$root/bash/state.sh"
pack "$work/missing.tar.gz"
if validate "$work/missing.tar.gz"; then exit 1; fi
printf 'PASS bootstrap rejects incomplete active module layout\n'
printf '#!/usr/bin/env bash\nexit 0\n' > "$work/fixture/$root/bash/state.sh"
chmod 644 "$work/fixture/$root/bash/state.sh"
rm "$work/fixture/$root/bash/progress.sh"
pack "$work/missing-progress.tar.gz"
if validate "$work/missing-progress.tar.gz"; then exit 1; fi
printf 'PASS bootstrap requires progress module before extraction\n'
printf '#!/usr/bin/env bash\nexit 0\n' > "$work/fixture/$root/bash/progress.sh"
chmod 644 "$work/fixture/$root/bash/progress.sh"
rm "$work/fixture/$root/bash/preflight.sh"
pack "$work/missing-preflight.tar.gz"
if validate "$work/missing-preflight.tar.gz"; then exit 1; fi
printf '#!/usr/bin/env bash\nexit 0\n' > "$work/fixture/$root/bash/preflight.sh"
chmod 644 "$work/fixture/$root/bash/preflight.sh"
rm "$work/fixture/$root/bash/progress.sh"
printf 'PASS bootstrap requires preflight module before extraction\n'
# Neither source nor validation invokes the interactive installer.
[[ ! -e $BOOTSTRAP_TAR_SENTINEL ]]
bash "$base/tools/render-bootstrap.sh" "$version" "$work/valid.tar.gz" "$work/rendered" https://fixture.invalid/release.tar.gz https://fixture.invalid/bootstrap.sh > "$work/render.log"
bash -n "$work/rendered/bootstrap.sh" "$work/rendered/ONE-LINER.txt"
(cd "$work/rendered" && sha256sum --check BOOTSTRAP.sha256)
[[ $(cat "$work/rendered/bootstrap.sh") != *'@@'* ]]
expected_bootstrap_sha=$(sha256sum "$work/rendered/bootstrap.sh" | awk '{print $1}')
[[ $(cat "$work/rendered/ONE-LINER.txt") == *"$expected_bootstrap_sha"* ]]
[[ $(cat "$work/rendered/bootstrap.sh") == *"$(sha256sum "$work/valid.tar.gz" | awk '{print $1}')"* ]]
printf 'PASS renderer pins both trust-chain hashes and supports reviewed HTTPS fixture URLs\n'
if command -v script >/dev/null; then
  cat > "$work/bin/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -euo pipefail
url='' target='' previous=''
for argument in "$@"; do
  # Both --output FILE and combined short flags ending in o (-fsSLo FILE).
  if [[ $previous == --output || ( $previous == -[a-zA-Z]* && $previous == *o ) ]]; then target=$argument; fi
  [[ $argument != https://* ]] || url=$argument
  previous=$argument
done
[[ -n $target ]]
[[ ! ( ${MOCK_FAIL_ARCHIVE:-0} == 1 && $url != */bootstrap.sh ) ]] || exit 22
if [[ $url == */bootstrap.sh ]]; then cp "$BOOTSTRAP_FIXTURE" "$target"; else cp "$ARCHIVE_FIXTURE" "$target"; fi
printf '%s\n' "$target" >> "$DOWNLOAD_PATHS"
MOCK_CURL
  chmod 755 "$work/bin/curl"
  export BOOTSTRAP_FIXTURE=$work/rendered/bootstrap.sh ARCHIVE_FIXTURE=$work/valid.tar.gz DOWNLOAD_PATHS=$work/download-paths
  # The fixture install.sh only exits 0: this exercises both SHA pins, terminal
  # redirection, syntax validation and cleanup without any system action.
  PATH="$work/bin:$PATH" script -q -e -c "$(cat "$work/rendered/ONE-LINER.txt")" "$work/terminal.log" > "$work/console.log" 2>&1
  while IFS= read -r path; do [[ ! -e $path ]]; done < "$DOWNLOAD_PATHS"
  printf 'PASS real PTY one-liner runs verified inert fixture and cleans private downloads\n'
  printf '#!/usr/bin/env bash\nprintf compromised > "%s"\n' "$work/compromised" > "$work/tampered-bootstrap.sh"
  export BOOTSTRAP_FIXTURE=$work/tampered-bootstrap.sh
  if PATH="$work/bin:$PATH" script -q -e -c "$(cat "$work/rendered/ONE-LINER.txt")" "$work/tampered-terminal.log" > "$work/tampered-console.log" 2>&1; then exit 1; fi
  [[ ! -e $work/compromised ]]
  while IFS= read -r path; do [[ ! -e $path ]]; done < "$DOWNLOAD_PATHS"
  printf 'PASS real PTY loader rejects tampered bootstrap before execution and cleans download\n'

  # Recommended ONE-COMMAND route: readable, verifies the bootstrap before bash runs it.
  printf '#!/usr/bin/env bash\nexit 0\n' > "$work/fixture/$root/bash/progress.sh"
  printf '#!/usr/bin/env bash\nprintf ran > "%s"\n' "$work/installer-ran" > "$work/fixture/$root/install.sh"
  chmod 644 "$work/fixture/$root/bash/progress.sh" "$work/fixture/$root/install.sh"
  pack "$work/cmd.tar.gz"
  bash "$base/tools/render-bootstrap.sh" "$version" "$work/cmd.tar.gz" "$work/cmd" https://fixture.invalid/release.tar.gz https://fixture.invalid/bootstrap.sh > "$work/cmd-render.log"
  one_command=$(cat "$work/cmd/ONE-COMMAND.txt")
  [[ $one_command == "curl --proto '=https' --tlsv1.2 -fsSLo uli-bootstrap.sh https://fixture.invalid/bootstrap.sh && echo '$(awk '{print $1}' "$work/cmd/BOOTSTRAP.sha256")  uli-bootstrap.sh' | sha256sum -c - && bash uli-bootstrap.sh" ]]
  [[ $(wc -l < "$work/cmd/ONE-COMMAND.txt") == 1 && $one_command != *'| bash'* && $one_command != *sudo* ]]
  run_command() {
    local directory=$1; mkdir -p "$directory"
    (cd "$directory" && PATH="$work/bin:$PATH" script -q -e -c "$one_command" "$directory/terminal.log" > "$directory/console.log" 2>&1)
  }
  export BOOTSTRAP_FIXTURE=$work/cmd/bootstrap.sh ARCHIVE_FIXTURE=$work/cmd.tar.gz
  run_command "$work/op-valid"
  [[ $(cat "$work/installer-ran") == ran ]]; rm -f -- "$work/installer-ran"
  printf 'PASS one-command route verifies pinned bootstrap and archive, then starts installer\n'
  export BOOTSTRAP_FIXTURE=$work/tampered-bootstrap.sh
  if run_command "$work/op-tampered"; then exit 1; fi
  [[ ! -e $work/compromised && ! -e $work/installer-ran ]]
  grep -q 'FAILED' "$work/op-tampered/console.log"
  export BOOTSTRAP_FIXTURE=$work/cmd/bootstrap.sh
  cp "$work/cmd.tar.gz" "$work/cmd-tampered.tar.gz"; printf tamper >> "$work/cmd-tampered.tar.gz"
  if ARCHIVE_FIXTURE=$work/cmd-tampered.tar.gz run_command "$work/op-bad-archive"; then exit 1; fi
  grep -q 'SHA256 wijkt af' "$work/op-bad-archive/console.log"
  if MOCK_FAIL_ARCHIVE=1 run_command "$work/op-unreachable"; then exit 1; fi
  grep -q 'Download mislukt' "$work/op-unreachable/console.log"
  printf '9.9.9\n' > "$work/fixture/$root/VERSION"
  pack "$work/wrong-version.tar.gz"
  bash "$base/tools/render-bootstrap.sh" "$version" "$work/wrong-version.tar.gz" "$work/wrong" https://fixture.invalid/release.tar.gz https://fixture.invalid/bootstrap.sh > /dev/null
  printf '%s\n' "$version" > "$work/fixture/$root/VERSION"
  one_command=$(cat "$work/wrong/ONE-COMMAND.txt")
  if BOOTSTRAP_FIXTURE=$work/wrong/bootstrap.sh ARCHIVE_FIXTURE=$work/wrong-version.tar.gz run_command "$work/op-wrong-version"; then exit 1; fi
  grep -q 'Interne versie wijkt af' "$work/op-wrong-version/console.log"
  [[ ! -e $work/installer-ran ]]
  printf 'PASS one-command route stops on tampered bootstrap, tampered archive, unreachable release and wrong version\n'
fi
printf 'PASS bootstrap offline fixture tests\n'  
