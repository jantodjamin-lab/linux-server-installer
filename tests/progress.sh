#!/usr/bin/env bash
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-progress-test.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
# shellcheck disable=SC1091
source "$base/bash/progress.sh"
export PROGRESS_PLAIN=1
for profile in app database combined; do
  progress_init "$profile"
  case $profile in app) expected=8;; database) expected=7;; combined) expected=10;; esac
  [[ $PROGRESS_TOTAL == "$expected" && $(progress_percent) == 0 ]]
  [[ $(progress_bar 0 "$expected") == '[--------------------]' ]]
  progress_begin system 'Systeemcontrole' > "$work/plain"
  [[ $(progress_percent) == 0 ]]
  progress_done system >> "$work/plain"
  [[ $(progress_percent) == "$((100/expected))" ]]
  progress_done system >> "$work/plain"
  progress_restore 'system system' >> "$work/plain"
  [[ $PROGRESS_COUNT == 1 && $(wc -l < "$work/plain") == 2 ]]
  if progress_done invalid; then exit 1; fi
  for phase in "${PROGRESS_IDS[@]}"; do progress_done "$phase" >> "$work/plain"; done
  [[ $(progress_percent) == 100 ]]
  [[ $(progress_bar "$expected" "$expected") == '[####################]' ]]
  progress_invalidate verification
  [[ $PROGRESS_COUNT == "$((expected-1))" && $(progress_percent) == "$(((expected-1)*100/expected))" ]]
  progress_done verification
  [[ $(progress_percent) == 100 ]]
  if LC_ALL=C grep -q $'\033' "$work/plain"; then exit 1; fi
  if [[ $profile == database ]]; then [[ " ${PROGRESS_IDS[*]} " != *' codex '* ]]; fi
  progress_stop
done
echo 'PASS profile phase counts, actual completion percentages, idempotence and plain output'
(
  export PROGRESS_PLAIN_HEARTBEAT=1 PROGRESS_INTERVAL=0.1
  progress_init app
  trap progress_stop EXIT
  progress_begin system 'Long plain phase'
  sleep 1.35
  [[ $(progress_percent) == 0 && $(progress_bar 0 8) == '[--------------------]' ]]
  progress_stop
  trap - EXIT
) > "$work/plain-heartbeat"
grep -Fq 'PROGRESS [--------------------] RUNNING 0/8 (0%)' "$work/plain-heartbeat"
grep -q 'totaal .*s; stap .*s' "$work/plain-heartbeat"
if LC_ALL=C grep -q $'\033' "$work/plain-heartbeat"; then exit 1; fi
echo 'PASS sparse plain heartbeat keeps zero progress during blocked phase and shows total/step elapsed'
if command -v script >/dev/null; then
  cat > "$work/pty.sh" <<'PTY'
#!/usr/bin/env bash
set -Eeuo pipefail
source "$PROGRESS_TEST_BASE/bash/progress.sh"
unset PROGRESS_PLAIN
export TERM=xterm PROGRESS_INTERVAL=0.1 NO_COLOR=1
progress_init app
[[ $PROGRESS_DYNAMIC == 1 ]]
trap progress_stop EXIT
progress_begin system 'TTY heartbeat'
sleep 0.35
[[ $(progress_percent) == 0 ]]
progress_done system
progress_begin plan 'TTY heartbeat plan'
PROGRESS_STARTED=$(($(date +%s)-61)); progress_snapshot
sleep 0.35
progress_stop
trap - EXIT
export TERM=dumb
progress_init database
[[ $PROGRESS_DYNAMIC == 0 ]]
progress_begin system 'Dumb terminal plain output'
progress_done system
progress_stop
PTY
  PROGRESS_TEST_BASE=$base script -q -e -c "bash '$work/pty.sh'" "$work/pty-output" > /dev/null
  grep -q 'TTY heartbeat' "$work/pty-output"
  grep -q 'nog actief' "$work/pty-output"
  grep -q '12%' "$work/pty-output"
  grep -Fq '[--------------------]' "$work/pty-output"
  grep -Fq '[##------------------]' "$work/pty-output"
  grep -q 'RUNNING.*totaal .*s; stap .*s' "$work/pty-output"
  grep -q 'PROGRESS 1/7 (14%) DONE system' "$work/pty-output"
  echo 'PASS real PTY heartbeat, elapsed warning and NO_COLOR ASCII rendering'
else
  echo 'WARN real PTY progress test requires util-linux script'
fi
