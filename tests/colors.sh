#!/usr/bin/env bash
# Green PASS, yellow WARN, red FAIL on a real terminal only. Never with NO_COLOR,
# TERM=dumb, pipes/redirects or in log files; text labels always remain.
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
command -v script >/dev/null || { echo 'WARN colour test skipped: script missing'; exit 0; }
work=$(mktemp -d /tmp/uli-colors.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
esc=$'\033'
cat > "$work/probe.sh" <<PROBE
source "$base/bash/common.sh"
pass 'kleurtest'; warn 'kleurtest'; fail 'kleurtest' || true
PROBE
in_pty() { TERM=${2:-xterm} script -q -e -c "bash $work/probe.sh" /dev/null > "$1" 2>&1; }
in_pty "$work/tty"
grep -q "${esc}\[32mPASS${esc}\[0m kleurtest" "$work/tty"
grep -q "${esc}\[33mWARN${esc}\[0m kleurtest" "$work/tty"
grep -q "${esc}\[1;31mFAIL${esc}\[0m kleurtest" "$work/tty"
NO_COLOR=1 in_pty "$work/nocolor"
in_pty "$work/dumb" dumb
bash "$work/probe.sh" > "$work/redirect" 2>&1
TERM=xterm script -q -e -c "bash $work/probe.sh | cat > $work/piped" /dev/null > /dev/null 2>&1
for file in nocolor dumb redirect piped; do
  if grep -q "$esc" "$work/$file"; then echo "ANSI in $file"; exit 1; fi
  grep -q 'PASS kleurtest' "$work/$file"
  [[ $file == piped ]] || { grep -q 'WARN kleurtest' "$work/$file" && grep -q 'FAIL kleurtest' "$work/$file"; }
done
echo 'PASS colours only on a terminal; NO_COLOR, TERM=dumb, redirect and pipe (log/tee) stay plain text'

# The installation log is written through tee, i.e. a pipe: also exercise the real menu.
mkdir -p "$work/fixture"
cp "$base/install.sh" "$base/VERSION" "$work/fixture/"; cp -a "$base/bash" "$work/fixture/"
printf 'checks_system() { pass "Systeemcontroles fixture"; }\n' > "$work/fixture/bash/checks.sh"
printf 'swap_active_bytes() { echo 0; }\n' >> "$work/fixture/bash/swap.sh"
TERM=xterm ULI_TEST_MODE=1 ULI_ROOT=$work/root script -q -e -c "printf '6\n' | bash $work/fixture/install.sh" /dev/null > "$work/menu-tty" 2>&1 || true
grep -q "${esc}\[3[23]m" "$work/menu-tty"
printf '6\n' | ULI_TEST_MODE=1 ULI_ROOT=$work/root bash "$work/fixture/install.sh" > "$work/menu-plain" 2>&1 || true
if grep -q "$esc" "$work/menu-plain"; then exit 1; fi
grep -q 'PASS' "$work/menu-plain"
echo 'PASS control output is coloured on a terminal and plain when redirected'

# Same sequence as install.sh: terminal first, then output through tee into a log.
cat > "$work/logprobe.sh" <<PROBE
source "$base/bash/common.sh"
pass 'voor log'
exec > >(tee -a "$work/install.log") 2>&1
ui_init
pass 'in log'; warn 'in log'; fail 'in log' || true
PROBE
TERM=xterm script -q -e -c "bash $work/logprobe.sh" /dev/null > "$work/logprobe-tty" 2>&1
for _ in $(seq 50); do grep -q 'FAIL in log' "$work/install.log" 2>/dev/null && break; sleep 0.1; done
grep -q "${esc}\[32mPASS${esc}\[0m voor log" "$work/logprobe-tty"
if grep -q "$esc" "$work/install.log"; then exit 1; fi
grep -q 'PASS in log' "$work/install.log" && grep -q 'WARN in log' "$work/install.log" && grep -q 'FAIL in log' "$work/install.log"
echo 'PASS installation log written through tee contains no ANSI codes'
