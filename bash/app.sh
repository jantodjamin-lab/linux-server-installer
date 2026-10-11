#!/usr/bin/env bash
# Ubuntu archive packages only; npm uses a reviewed immutable SRI lock.
CODEX_VERSION=0.128.0
CODEX_LOCK_SHA256=b2645d7cb42265680842553b3d16a5f512a645187c96abe55c6f1d1d5f859d71
CODEX_DIR=/opt/universal-linux-installer/codex

app_codex_path_security() {
  local directory mode
  for directory in /opt /opt/universal-linux-installer "$CODEX_DIR"; do
    [[ ! -L $directory ]] || { fail 'Symlink in Codex-beheerpad'; return 1; }
    [[ -e $directory ]] || continue
    [[ -d $directory && $(stat -c %u "$directory") == 0 ]] || return 1
    mode=$(stat -c %a "$directory") || return
    (( (8#$mode & 8#022) == 0 )) || { fail 'Onveilig schrijfbaar Codex-beheerpad'; return 1; }
  done
  if [[ -e $CODEX_DIR ]]; then
    [[ -f $CODEX_DIR/.uli-managed && ! -L $CODEX_DIR/.uli-managed &&
       $(stat -c %u "$CODEX_DIR/.uli-managed") == 0 &&
       $(stat -c %a "$CODEX_DIR/.uli-managed") == 600 &&
       $(cat "$CODEX_DIR/.uli-managed") == "$CODEX_VERSION" ]] || {
      fail 'Onbeheerde Codex-map: handmatige beoordeling vereist'; return 1;
    }
  fi
}

app_codex_verify() {
  app_codex_path_security || return
  [[ -x $CODEX_DIR/node_modules/.bin/codex ]] || return 1
  [[ $("$CODEX_DIR/node_modules/.bin/codex" --version) == "codex-cli $CODEX_VERSION" ]] || return 1
  [[ -L /usr/local/bin/codex && $(readlink /usr/local/bin/codex) == "$CODEX_DIR/node_modules/.bin/codex" ]]
}

app_codex_install() {
  local assets="$INSTALLER_DIR/bash/assets/codex" major npm_output npm_work
  major=$(node --version) || return
  major=${major#v}; major=${major%%.*}
  if ! [[ $major =~ ^[0-9]+$ ]] || (( major != 22 && major != 24 )); then
    fail 'Codex vereist een gevalideerde Node LTS-versie (22 of 24)'; return 1
  fi
  [[ $(sha256sum "$assets/package-lock.json" | awk '{print $1}') == "$CODEX_LOCK_SHA256" ]] || {
    fail 'Codex lock-integriteit mislukt'; return 1;
  }
  app_codex_path_security || return
  app_codex_verify && return 0
  if [[ -e /usr/local/bin/codex || -L /usr/local/bin/codex ]]; then
    [[ -L /usr/local/bin/codex && $(readlink /usr/local/bin/codex) == "$CODEX_DIR/node_modules/.bin/codex" ]] || {
      fail 'Bestaande Codex-installatie wordt niet overschreven'; return 1;
    }
  fi
  install -d -m 0755 "$CODEX_DIR" || return
  (umask 077; printf '%s\n' "$CODEX_VERSION" > "$CODEX_DIR/.uli-managed") || return
  install -m 0644 "$assets/package.json" "$assets/package-lock.json" "$CODEX_DIR/" || return
  # npm ci safely replaces only managed node_modules, including interrupted runs.
  npm_work=$(mktemp -d /tmp/uli-npm.XXXXXXXX) || return
  npm_output=$npm_work/output
  install -m 600 /dev/null "$npm_work/user.npmrc" || return
  install -m 600 /dev/null "$npm_work/global.npmrc" || return
  if ! env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME="$CODEX_DIR" \
    npm ci --prefix "$CODEX_DIR" --ignore-scripts --include=optional --engine-strict \
    --registry=https://registry.npmjs.org --userconfig="$npm_work/user.npmrc" --globalconfig="$npm_work/global.npmrc" \
    --audit=false --fund=false --loglevel=error > "$npm_output" 2>&1; then
    rm -f -- "$npm_output" "$npm_work/user.npmrc" "$npm_work/global.npmrc"
    rmdir -- "$npm_work"
    fail 'Codex npm-integriteitsinstallatie mislukt; uitvoer afgeschermd'; return 1
  fi
  rm -f -- "$npm_output" "$npm_work/user.npmrc" "$npm_work/global.npmrc"
  rmdir -- "$npm_work"
  [[ $("$CODEX_DIR/node_modules/.bin/codex" --version) == "codex-cli $CODEX_VERSION" ]] || {
    fail 'Codex native pakket ontbreekt of versie is onjuist'; return 1;
  }
  ln -sfn "$CODEX_DIR/node_modules/.bin/codex" /usr/local/bin/codex || return
  app_codex_verify
}

app_verify() {
  local package
  for package in git python3 dotnet-sdk-10.0 nodejs npm nginx; do
    [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null) == 'install ok installed' ]] || return 1
  done
  dotnet --list-sdks | grep -q '^10\.' || return 1
  nginx -t || return
  systemctl is-active --quiet nginx || return
  app_codex_verify
}

app_install() {
  uli_apt_install git python3 dotnet-sdk-10.0 nodejs npm nginx ca-certificates || return
  app_codex_install || return
  nginx -t || return
  systemctl enable --now nginx || return
  app_verify || { fail 'APP service- of versiecontrole mislukt'; return 1; }
  pass 'APP-profiel geïnstalleerd en gecontroleerd'
}
