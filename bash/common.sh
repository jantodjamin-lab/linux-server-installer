#!/usr/bin/env bash
# Shared functions. No command strings are evaluated.
# Colour only on a real terminal: never with NO_COLOR, TERM=dumb, pipes or the
# installation log. Decided per stream by ui_init (on load and again after the
# installer redirects output to its log), not inside command substitutions.
ui_init() {
  UI_COLOR_1=0 UI_COLOR_2=0
  if [[ -z ${NO_COLOR:-} && ${TERM:-dumb} != dumb ]]; then
    if [[ -t 1 ]]; then UI_COLOR_1=1; fi
    if [[ -t 2 ]]; then UI_COLOR_2=1; fi
  fi
}
ui_label() {
  local code enabled=$UI_COLOR_1
  [[ ${2:-1} != 2 ]] || enabled=$UI_COLOR_2
  case $1 in PASS) code='32';; WARN) code='33';; FAIL) code='1;31';; *) printf '%s' "$1"; return;; esac
  if (( enabled )); then printf '\033[%sm%s\033[0m' "$code" "$1"; else printf '%s' "$1"; fi
}
ui_init
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
pass() { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$(ui_label PASS 1)" "$*"; }
warn() { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$(ui_label WARN 2)" "$*" >&2; }
fail() { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$(ui_label FAIL 2)" "$*" >&2; return 1; }
require_root() { [[ $EUID == 0 ]] || fail 'Start de installer met sudo bash install.sh.'; }
run_apt() {
  local output result=0
  output=$(mktemp "$STATE_DIR/.apt-output.XXXXXX") || return
  chmod 600 "$output" || return
  DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout="${ULI_APT_LOCK_TIMEOUT:-180}" -o APT::Update::Error-Mode=any -o Acquire::AllowInsecureRepositories=false -o Acquire::AllowWeakRepositories=false -o Acquire::AllowDowngradeToInsecureRepositories=false -o APT::Get::AllowUnauthenticated=false "$@" > "$output" 2>&1 || result=$?
  # Never copy raw package output, which may contain repository credentials, into logs.
  rm -f -- "$output"
  if (( result )); then fail "APT $1 mislukt (exit $result)"; return "$result"; fi
  pass "APT $1"
}

uli_fail() { fail "$@"; }
uli_log() { log "$*"; }
uli_apt_install() { run_apt install --yes --no-remove --no-install-recommends "$@"; }
