#!/usr/bin/env bash
# Progress counts completed phases only. Renderer reads atomic private snapshots.
progress_init() {
  local profile=$1
  PROGRESS_IDS=(system plan swap)
  case "$profile" in
    app|APP) PROGRESS_IDS+=(app_packages codex nginx);;
    database|DB) PROGRESS_IDS+=(postgres database_check);;
    combined|APP+DB) PROGRESS_IDS+=(app_packages codex nginx postgres database_check);;
    *) return 1;;
  esac
  PROGRESS_IDS+=(resume verification)
  declare -gA PROGRESS_COMPLETED=()
  PROGRESS_TOTAL=${#PROGRESS_IDS[@]} PROGRESS_COUNT=0
  PROGRESS_CURRENT=- PROGRESS_LABEL='Gereed voor uitvoering' PROGRESS_STARTED=$(date +%s)
  PROGRESS_INSTALL_STARTED=$PROGRESS_STARTED
  PROGRESS_DYNAMIC=0 PROGRESS_PID='' PROGRESS_OWNS_FD=0
  PROGRESS_DIRECTORY=$(mktemp -d "${TMPDIR:-/tmp}/uli-progress.XXXXXXXX") || return
  PROGRESS_DATA=$PROGRESS_DIRECTORY/data
  if [[ ${TERM:-dumb} != dumb && ${PROGRESS_PLAIN:-0} != 1 ]]; then
    if [[ -n ${PROGRESS_FD:-} ]]; then
      [[ -t $PROGRESS_FD ]] && PROGRESS_DYNAMIC=1
    elif [[ -t 1 ]]; then
      if { exec {PROGRESS_FD}>/dev/tty; } 2>/dev/null; then
        PROGRESS_DYNAMIC=1 PROGRESS_OWNS_FD=1
      fi
    fi
  fi
  progress_snapshot || return
  local owner=$BASHPID
  (exec 9>&-; progress_renderer "$owner") &
  PROGRESS_PID=$!
}

progress_snapshot() {
  local temporary
  temporary=$(mktemp "$PROGRESS_DIRECTORY/.data.XXXXXXXX") || return
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$PROGRESS_COUNT" "$PROGRESS_TOTAL" "$PROGRESS_STARTED" "$PROGRESS_INSTALL_STARTED" "$PROGRESS_CURRENT" "$PROGRESS_LABEL" > "$temporary" || return
  mv -f -- "$temporary" "$PROGRESS_DATA"
}

progress_known() {
  local candidate
  for candidate in "${PROGRESS_IDS[@]}"; do [[ $candidate != "$1" ]] || return 0; done
  return 1
}

progress_percent() { printf '%s\n' "$((PROGRESS_COUNT*100/PROGRESS_TOTAL))"; }

progress_invalidate() {
  progress_known "$1" || return 1
  if [[ -n ${PROGRESS_COMPLETED[$1]:-} ]]; then
    unset 'PROGRESS_COMPLETED[$1]'
    PROGRESS_COUNT=$((PROGRESS_COUNT-1))
    progress_snapshot
  fi
}

progress_bar() {
  local filled=$(( $1*20/$2 )) cell bar=''
  for ((cell=0;cell<20;cell++)); do
    if (( cell < filled )); then bar+='#'; else bar+='-'; fi
  done
  printf '[%s]' "$bar"
}

progress_restore() {
  local phase
  local -a restored
  read -r -a restored <<< "$1"
  for phase in "${restored[@]}"; do progress_done "$phase" || return; done
}

progress_begin() {
  progress_known "$1" || return 1
  PROGRESS_CURRENT=$1 PROGRESS_LABEL=${2:-$1} PROGRESS_STARTED=$(date +%s)
  # Labels cannot inject control sequences into the terminal or snapshot format.
  PROGRESS_LABEL=$(printf '%s' "$PROGRESS_LABEL" | LC_ALL=C tr -cd '[:print:]')
  progress_snapshot || return
  if (( ! PROGRESS_DYNAMIC )); then
    printf 'PROGRESS %s/%s (%s%%) START %s\n' "$PROGRESS_COUNT" "$PROGRESS_TOTAL" "$(progress_percent)" "$PROGRESS_LABEL"
  fi
}

progress_done() {
  progress_known "$1" || return 1
  if [[ -z ${PROGRESS_COMPLETED[$1]:-} ]]; then
    PROGRESS_COMPLETED[$1]=1
    PROGRESS_COUNT=$((PROGRESS_COUNT+1))
    [[ $PROGRESS_CURRENT != "$1" ]] || PROGRESS_CURRENT=-
    progress_snapshot || return
    if (( ! PROGRESS_DYNAMIC )); then
      printf 'PROGRESS %s/%s (%s%%) DONE %s\n' "$PROGRESS_COUNT" "$PROGRESS_TOTAL" "$(progress_percent)" "$1"
    fi
  fi
}

progress_renderer() {
  local owner=$1 count total started installed current label elapsed overall percent activity index=0 now status bar
  local last_notice heartbeat=${PROGRESS_PLAIN_HEARTBEAT:-30}
  last_notice=$(date +%s) || return
  [[ $heartbeat =~ ^[1-9][0-9]*$ ]] || heartbeat=30
  local -a frames=('|' '/' '-' '+')
  while kill -0 "$owner" 2>/dev/null; do
    if IFS=$'\t' read -r count total started installed current label < "$PROGRESS_DATA"; then
      now=$(date +%s)
      elapsed=$((now-started)); (( elapsed >= 0 )) || elapsed=0
      overall=$((now-installed)); (( overall >= 0 )) || overall=0
      percent=$((count*100/total))
      label="$current: $label"
      activity=${frames[index%4]}; index=$((index+1))
      status=RUNNING
      [[ $current != - ]] || status=WAITING
      (( count < total )) || status=DONE
      if (( elapsed >= 60 )) && [[ $status == RUNNING ]]; then label="$label - duurt langer; nog actief"; fi
      bar=$(progress_bar "$count" "$total")
      if (( PROGRESS_DYNAMIC )); then
        printf '\r\033[2K%s [%s] %s %s/%s %s%% %s (totaal %ss; stap %ss)' "$bar" "$activity" "$status" "$count" "$total" "$percent" "$label" "$overall" "$elapsed" >&"$PROGRESS_FD"
      elif [[ $status == RUNNING ]] && (( now-last_notice >= heartbeat )); then
        printf 'PROGRESS %s RUNNING %s/%s (%s%%) %s (totaal %ss; stap %ss)\n' "$bar" "$count" "$total" "$percent" "$label" "$overall" "$elapsed"
        last_notice=$now
      fi
    fi
    sleep "${PROGRESS_INTERVAL:-1}"
  done
}

progress_stop() {
  if [[ -n ${PROGRESS_PID:-} ]]; then
    kill "$PROGRESS_PID" 2>/dev/null || true
    wait "$PROGRESS_PID" 2>/dev/null || true
    PROGRESS_PID=''
  fi
  if [[ ${PROGRESS_DYNAMIC:-0} == 1 ]]; then
    printf '\r\033[2KPROGRESS %s/%s (%s%%) %s\n' "$PROGRESS_COUNT" "$PROGRESS_TOTAL" "$(progress_percent)" "$PROGRESS_LABEL" >&"$PROGRESS_FD"
  fi
  if [[ ${PROGRESS_OWNS_FD:-0} == 1 ]]; then exec {PROGRESS_FD}>&-; unset PROGRESS_FD; fi
  if [[ -n ${PROGRESS_DIRECTORY:-} ]]; then
    rm -f -- "$PROGRESS_DATA"
    rmdir -- "$PROGRESS_DIRECTORY" 2>/dev/null || true
    PROGRESS_DIRECTORY=''
  fi
}
