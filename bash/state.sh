#!/usr/bin/env bash
ROOT=''
if [[ ${ULI_TEST_MODE:-0} == 1 ]]; then
  [[ ${ULI_ROOT:-} == /tmp/* ]] || { printf 'Unsafe test root\n' >&2; exit 1; }
  ROOT=$ULI_ROOT
fi
STATE_DIR=$ROOT/var/lib/universal-linux-installer
STATE_FILE=$STATE_DIR/state
PROFILE='' STATUS=new CURRENT='' COMPLETED='' UPDATED='' STATE_VERSION=''
state_load() {
  if [[ -d $STATE_DIR && ! -x $STATE_DIR ]]; then fail 'Statusmap ontoegankelijk; administratorrechten vereist'; return 1; fi
  [[ -e $STATE_FILE ]] || return 0
  [[ -f $STATE_FILE && ! -L $STATE_FILE && $(stat -c %u "$STATE_FILE") == 0 && $(stat -c %a "$STATE_FILE") == 600 ]] || { fail 'Onveilig statusbestand'; return 1; }
  local key value
  local -A seen=()
  while IFS='=' read -r key value; do
    [[ -z ${seen[$key]:-} ]] || { fail 'Dubbel statusveld'; return 1; }
    seen[$key]=1
    case $key in
      profile) [[ $value =~ ^(app|database|combined)$ ]] || return 1; PROFILE=$value;;
      status) [[ $value =~ ^(new|running|failed|complete)$ ]] || return 1; STATUS=$value;;
      current) [[ $value =~ ^[a-z_]*$ ]] || return 1; CURRENT=$value;;
      completed) [[ $value =~ ^[a-z_\ ]*$ ]] || return 1; COMPLETED=$value;;
      version) [[ $value =~ ^[a-zA-Z0-9.+-]+$ ]] || return 1; STATE_VERSION=$value;;
      updated) UPDATED=$value;;
      *) fail 'Onbekend statusveld'; return 1;;
    esac
  done < "$STATE_FILE"
  [[ ${#seen[@]} == 6 && -n $PROFILE && -n $STATE_VERSION && -n $UPDATED ]] || { fail 'Onvolledig statusbestand'; return 1; }
}
state_save() {
  local temporary
  temporary=$(mktemp "$STATE_DIR/.state.XXXXXX") || return
  chmod 600 "$temporary" || return
  printf 'profile=%s\nversion=%s\ncompleted=%s\ncurrent=%s\nstatus=%s\nupdated=%s\n' "$PROFILE" "$VERSION" "$COMPLETED" "$CURRENT" "$STATUS" "$(date -u +%FT%TZ)" > "$temporary" || return
  mv -f "$temporary" "$STATE_FILE" || return
  sync -f "$STATE_DIR" || return
}
state_step() {
  local name=$1; shift
  if [[ " $COMPLETED " == *" $name "* ]]; then pass "Stap reeds afgerond: $name"; return; fi
  CURRENT=$name STATUS=running; state_save || return
  if "$@"; then COMPLETED="${COMPLETED:+$COMPLETED }$name"; CURRENT=''; state_save || return
  else STATUS=failed; state_save || true; return 1; fi
}
resume_service_install() {
  local target=$STATE_DIR/installer-$VERSION
  [[ ! -L $target ]] || { fail 'Onveilige hervatmap'; return 1; }
  if [[ -e $target ]]; then
    [[ -d $target && $(stat -c %u "$target") == 0 && $(stat -c %a "$target") == 700 ]] || { fail 'Onveilige hervatcode'; return 1; }
    if [[ $INSTALLER_DIR != "$target" ]]; then
      local source relative
      while IFS= read -r -d '' source; do
        relative=${source#"$INSTALLER_DIR/"}
        if [[ ! -f $target/$relative || -L $target/$relative ]] || ! cmp -s "$source" "$target/$relative"; then
          fail 'Hervatcode verschilt; handmatig onderzoek vereist'; return 1
        fi
      done < <(find "$INSTALLER_DIR/bash" -type f -print0)
      if ! cmp -s "$INSTALLER_DIR/install.sh" "$target/install.sh" || ! cmp -s "$INSTALLER_DIR/VERSION" "$target/VERSION"; then
        fail 'Hervatversie verschilt'; return 1
      fi
    fi
  else
    local staging source
    staging=$(mktemp -d "$STATE_DIR/.installer.XXXXXX") || return
    install -d -m 700 "$staging/bash" || return
    install -m 700 "$INSTALLER_DIR/install.sh" "$staging/install.sh" || return
    install -m 600 "$INSTALLER_DIR/VERSION" "$staging/VERSION" || return
    for source in "$INSTALLER_DIR"/bash/*.sh; do install -m 600 "$source" "$staging/bash/" || return; done
    if [[ -d $INSTALLER_DIR/bash/assets ]]; then
      install -d -m 700 "$staging/bash/assets" || return
      cp -R -- "$INSTALLER_DIR/bash/assets/." "$staging/bash/assets/" || return
      chmod -R go-rwx "$staging/bash/assets" || return
    fi
    sync -f "$staging" || return
    mv -T "$staging" "$target" || return
    sync -f "$STATE_DIR" || return
  fi
  [[ ${ULI_TEST_MODE:-0} == 1 ]] && return 0
  local unit=/etc/systemd/system/universal-linux-installer-resume.service unit_temp
  [[ ! -L $unit ]] || { fail 'Onveilige hervatservice'; return 1; }
  if [[ -e $unit ]]; then
    if [[ ! -f $unit || $(stat -c %u "$unit") != 0 ]] || ! grep -Fx '# Managed by Universal Linux Installer' "$unit" >/dev/null; then
      fail 'Bestaande onbeheerde hervatservice'; return 1
    fi
  fi
  unit_temp=$(mktemp /etc/systemd/system/.uli-resume.XXXXXX) || return
  cat > "$unit_temp" <<EOF_UNIT || return
# Managed by Universal Linux Installer
[Unit]
Description=Resume authorized Universal Linux Installer
Wants=network-online.target
After=network-online.target nginx.service postgresql.service postgresql@18-main.service
ConditionPathExists=$STATE_FILE
[Service]
Type=oneshot
ExecStart=/bin/bash $target/install.sh --resume
TimeoutStartSec=infinity
[Install]
WantedBy=multi-user.target
EOF_UNIT
  chmod 644 "$unit_temp" || return
  mv -f "$unit_temp" "$unit" || return
  sync -f /etc/systemd/system || return
  systemctl daemon-reload || return
  systemctl enable universal-linux-installer-resume.service || return
}
state_codex_patch_eligible() {
  [[ $STATE_VERSION == 1.0.0-bash.1 && $VERSION == 1.0.0-bash.2 && $STATUS == complete && -z $CURRENT && $PROFILE != database ]]
}
state_codex_patch_authorized() {
  local marker=$STATE_DIR/codex-permissions-patch
  [[ -f $marker && ! -L $marker && $(stat -c %u "$marker") == 0 && $(stat -c %a "$marker") == 600 &&
     $(cat "$marker") == "$PROFILE:1.0.0-bash.1:1.0.0-bash.2" ]]
}
state_authorize_codex_patch() {
  local temporary
  temporary=$(mktemp "$STATE_DIR/.codex-patch.XXXXXXXX") || return
  chmod 600 "$temporary" || return
  printf '%s:1.0.0-bash.1:1.0.0-bash.2\n' "$PROFILE" > "$temporary" || return
  mv -f "$temporary" "$STATE_DIR/codex-permissions-patch" || return
  sync -f "$STATE_DIR" || return
}
state_prepare() {
  [[ ! -L $ROOT/var && ! -L $ROOT/var/lib ]] || { fail 'Onveilige statusbovenmap'; return 1; }
  [[ ! -L $STATE_DIR ]] || { fail 'Onveilige statusmap'; return 1; }
  install -d -m 700 "$STATE_DIR" || return
  [[ $(stat -c %u "$STATE_DIR") == 0 && $(stat -c %a "$STATE_DIR") == 700 ]] || { fail 'Statusmap moet root-eigendom en 0700 zijn'; return 1; }
  [[ ! -L $STATE_DIR/lock ]] || { fail 'Onveilig lockbestand'; return 1; }
  exec 9>"$STATE_DIR/lock" || return
  flock -n 9 || { fail 'Een andere installatie draait'; return 1; }
  state_load
}
