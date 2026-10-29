#!/usr/bin/env bash
set -Eeuo pipefail
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/uli-progress-test.XXXXXXXX)
trap 'result=$?; if ((result)); then printf "Progress-test evidence: %s\n" "$work" >&2; else rm -rf -- "$work"; fi' EXIT
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
  trap 'printf "mutation\n" >> "$work/renderer-mutation"' ERR EXIT INT TERM HUP
  parent_traps=$(trap -p ERR EXIT INT TERM HUP)
  # Failure inside a command substitution reproduces inherited ERR propagation.
  # shellcheck disable=SC2317
  progress_renderer() { local _result; _result=$(false); }
  progress_init app
  wait "$PROGRESS_PID" || true
  progress_stop
  [[ ! -e $work/renderer-mutation ]]
  [[ $(trap -p ERR EXIT INT TERM HUP) == "$parent_traps" ]]
  # Expected shutdown must not emit diagnostics or run parent's mutation traps.
  # shellcheck disable=SC2317
  progress_renderer() { while :; do sleep 0.01; done; }
  for _shutdown in 1 2 3 4 5; do
    progress_init app
    sleep 0.02
    progress_stop
    progress_stop
  done
  [[ ! -e $work/renderer-mutation ]]
  trap - ERR EXIT INT TERM HUP
) > "$work/renderer-shutdown-stdout" 2> "$work/renderer-shutdown-stderr"
[[ ! -s $work/renderer-shutdown-stdout && ! -s $work/renderer-shutdown-stderr ]]
echo 'PASS renderer failures/shutdown cannot invoke parent mutation traps; repeated stop has no diagnostics'
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
stty cols 80 rows 24
progress_init app
[[ $PROGRESS_DYNAMIC == 1 ]]
trap progress_stop EXIT
progress_begin system 'TTY heartbeat'
sleep 1
[[ $(progress_percent) == 0 ]]
progress_done system
progress_begin plan 'TTY heartbeat plan with a deliberately long human description that must remain in START logs and never wrap the dynamic eighty column terminal frame'
PROGRESS_STARTED=$(($(date +%s)-61)); progress_snapshot
sleep 1
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
  grep -q 'RUNNING/LONG.*T:.*s S:.*s' "$work/pty-output"
  grep -q 'START TTY heartbeat plan with a deliberately long human description' "$work/pty-output"
  [[ $(grep -o 'WARN Fase duurt langer dan 60s' "$work/pty-output" | wc -l) == 1 ]]
  # Every dynamic frame must fit width-1. Full START/WARN log lines may wrap normally.
  LC_ALL=C awk -v marker="$(printf '\033[2K')" 'BEGIN {RS="\r"; frames=0} index($0,marker)==1 {text=substr($0,length(marker)+1); sub(/\n.*/,"",text); if(text ~ /^\[/) {frames++; if(length(text)>79) exit 1}} END {if(!frames) exit 1}' "$work/pty-output"
  grep -q 'PROGRESS 1/7 (14%) DONE system' "$work/pty-output"
  echo 'PASS real PTY heartbeat, elapsed warning and NO_COLOR ASCII rendering'
else
  echo 'WARN real PTY progress test requires util-linux script'
fi

# Finding B (O2 live): the final frame must say DONE after a complete run and
# STOPPED only when the run ends before all phases are complete.
final_frame() { # profile phases-to-complete output
  local profile=$1 count=$2 output=$3 index=0 phase
  (
    unset PROGRESS_FD
    PROGRESS_PLAIN=1 progress_init "$profile" > /dev/null
    exec {PROGRESS_FD}>"$output"
    PROGRESS_DYNAMIC=1
    for phase in "${PROGRESS_IDS[@]}"; do
      (( index < count )) || break
      progress_done "$phase" > /dev/null; index=$((index+1))
    done
    progress_stop
  )
}
final_frame combined 10 "$work/final-complete"
grep -q ' DONE 10/10 100% ' "$work/final-complete"
if grep -q 'STOPPED' "$work/final-complete"; then echo 'complete run shown as STOPPED'; exit 1; fi
final_frame combined 4 "$work/final-partial"
grep -q ' STOPPED 4/10 40% ' "$work/final-partial"
final_frame database 7 "$work/final-db"
grep -q ' DONE 7/7 100% ' "$work/final-db"
echo 'PASS final progress frame shows DONE when complete and STOPPED only when interrupted'
