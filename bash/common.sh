#!/usr/bin/env bash
# Shared functions. No command strings are evaluated.
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
pass() { log "PASS $*"; }
warn() { log "WARN $*" >&2; }
fail() { log "FAIL $*" >&2; return 1; }
require_root() { [[ $EUID == 0 ]] || fail 'Start de installer met sudo bash install.sh.'; }
run_apt() {
  local output result=0
  output=$(mktemp "$STATE_DIR/.apt-output.XXXXXX") || return
  chmod 600 "$output" || return
  DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=180 -o APT::Update::Error-Mode=any -o Acquire::AllowInsecureRepositories=false -o Acquire::AllowWeakRepositories=false -o Acquire::AllowDowngradeToInsecureRepositories=false -o APT::Get::AllowUnauthenticated=false "$@" > "$output" 2>&1 || result=$?
  # Never copy raw package output, which may contain repository credentials, into logs.
  rm -f -- "$output"
  if (( result )); then fail "APT $1 mislukt (exit $result)"; return "$result"; fi
  pass "APT $1"
}

uli_fail() { fail "$@"; }
uli_log() { log "$*"; }
uli_apt_install() { run_apt install --yes --no-remove --no-install-recommends "$@"; }
