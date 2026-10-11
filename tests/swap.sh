#!/usr/bin/env bash
# Mock kernel commands only; never activates swap on the test host.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-swap-tests.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/bin"
export PATH="$work/bin:$PATH" ULI_TEST_MODE=1
cat > "$work/bin/stat" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == -c && $2 == %u ]]; then echo 0; else /usr/bin/stat "$@"; fi
MOCK
cat > "$work/bin/findmnt" <<'MOCK'
#!/usr/bin/env bash
echo "${MOCK_FS:-ext4}"
MOCK
cat > "$work/bin/df" <<'MOCK'
#!/usr/bin/env bash
printf 'Avail\n%s\n' "${MOCK_FREE:-9000000000}"
MOCK
cat > "$work/bin/dd" <<'MOCK'
#!/usr/bin/env bash
for arg; do case $arg in of=*) file=${arg#of=};; count=*) count=${arg#count=};; esac; done
if [[ ${MOCK_INTERRUPT:-0} == 1 ]]; then truncate -s 1048576 "$file"; exit 1; fi
truncate -s "$((count*1048576))" "$file"
echo "$count" >> "$ULI_ROOT/dd-calls"
MOCK
cat > "$work/bin/mkswap" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$1" >> "$ULI_ROOT/mkswap-calls"
MOCK
cat > "$work/bin/swapon" <<'MOCK'
#!/usr/bin/env bash
if [[ $1 == --show ]]; then
 if [[ $* == *SIZE* ]]; then
  cat "$ULI_ROOT/active-bytes"
  [[ ! -f $ULI_ROOT/activated ]] || echo "$(( $(/usr/bin/stat -c %s "$(cat "$ULI_ROOT/activated")") - 4096 ))"
 elif [[ -f $ULI_ROOT/activated ]]; then cat "$ULI_ROOT/activated"; fi
else printf '%s\n' "$1" > "$ULI_ROOT/activated"; fi
MOCK
chmod +x "$work/bin/"*
source "$base/bash/common.sh"
reset_case() {
 export ULI_ROOT=$work/case-$1
 mkdir -p "$ULI_ROOT/etc" "$ULI_ROOT/var/lib/universal-linux-installer"
 printf '# original\n' > "$ULI_ROOT/etc/fstab"
 printf '%s\n' "$2" > "$ULI_ROOT/active-bytes"
 source "$base/bash/state.sh"
 source "$base/bash/swap.sh"
}
for gib in 0 2 4 6; do
 reset_case "$gib" "$((gib*1073741824))"
 swap_ensure
 if ((gib<4)); then
  [[ $(/usr/bin/stat -c %s "$STATE_DIR/swapfile") == "$(((4-gib)*1073741824+1048576))" ]]
  [[ $(/usr/bin/stat -c %a "$STATE_DIR/swapfile") == 600 ]]
  [[ $(wc -l < "$ULI_ROOT/dd-calls") == 1 ]]
 else [[ ! -e $STATE_DIR/swapfile ]]; fi
 cp "$ULI_ROOT/etc/fstab" "$ULI_ROOT/fstab-before"
 swap_ensure
 cmp "$ULI_ROOT/fstab-before" "$ULI_ROOT/etc/fstab"
 [[ ! -e $ULI_ROOT/dd-calls || $(wc -l < "$ULI_ROOT/dd-calls") == 1 ]]
 echo "PASS mocked swap $gib GiB and repeat idempotence"
done
reset_case interrupted 0
export MOCK_INTERRUPT=1
if swap_ensure; then exit 1; fi
unset MOCK_INTERRUPT
if swap_ensure; then exit 1; fi
[[ ! -e $ULI_ROOT/mkswap-calls && ! -e $ULI_ROOT/activated ]]
echo 'PASS interrupted allocation blocks uncertain automatic recovery'
reset_case badfs 0
export MOCK_FS=btrfs
if swap_ensure; then exit 1; fi
[[ ! -e $STATE_DIR/swapfile ]]
unset MOCK_FS
echo 'PASS unsupported filesystem refused before writes'
reset_case lowspace 0
export MOCK_FREE=1000000000
if swap_ensure; then exit 1; fi
[[ ! -e $STATE_DIR/swapfile ]]
unset MOCK_FREE
echo 'PASS insufficient free space refused before writes'
reset_case reboot 0
swap_ensure
rm "$ULI_ROOT/activated"
swap_ensure
[[ $(wc -l < "$ULI_ROOT/dd-calls") == 1 && $(wc -l < "$ULI_ROOT/mkswap-calls") == 1 ]]
echo 'PASS reboot modeled: reactivates without recreating or reformatting'
