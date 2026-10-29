#!/usr/bin/env bash
# Run the real CLI against harmless fixture probes; mocked sudo never elevates.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
if (( EUID == 0 )); then echo 'WARN authorization/sudo test needs nonroot runner'; exit 0; fi
work=$(mktemp -d /tmp/uli-sudo-tests.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/fixture" "$work/bin"
cp "$base/install.sh" "$base/VERSION" "$work/fixture/"
cp -a "$base/bash" "$work/fixture/"
printf 'checks_system() { return 0; }\n' > "$work/fixture/bash/checks.sh"
printf 'swap_active_bytes() { echo 0; }\n' >> "$work/fixture/bash/swap.sh"
cat > "$work/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$ULI_SUDO_LOG"
MOCK
chmod +x "$work/bin/sudo"
export PATH="$work/bin:$PATH" ULI_SUDO_LOG=$work/sudo-args ULI_TEST_MODE=1 ULI_ROOT=$work/root
printf 'nee\n' | bash "$work/fixture/install.sh" --profile APP > "$work/refused"
[[ ! -e $ULI_SUDO_LOG && ! -e $ULI_ROOT ]]
echo 'PASS denied authorization never invokes sudo or writes state'
printf 'ja\n' | bash "$work/fixture/install.sh" --profile APP > "$work/authorized"
mapfile -t args < "$ULI_SUDO_LOG"
[[ ${args[0]} == -- && ${args[1]} == /bin/bash && ${args[2]} == "$work/fixture/install.sh" && ${args[3]} == --profile && ${args[4]} == app && ${args[5]} == --yes ]]
[[ ! -e $ULI_ROOT ]]
echo 'PASS authorized sudo reexec preserves canonical profile and confirmation'
rm "$ULI_SUDO_LOG"
bash "$work/fixture/install.sh" --profile DB --yes > "$work/yes"
grep -qx database "$ULI_SUDO_LOG"
echo 'PASS explicit --yes authorizes database sudo route'
