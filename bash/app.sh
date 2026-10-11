#!/usr/bin/env bash
# Ubuntu archive packages only; npm uses a reviewed immutable SRI lock.
CODEX_VERSION=0.128.0
CODEX_LOCK_SHA256=b2645d7cb42265680842553b3d16a5f512a645187c96abe55c6f1d1d5f859d71
CODEX_PARENT=/opt/universal-linux-installer
CODEX_DIR=$CODEX_PARENT/codex
CODEX_LINK=/usr/local/bin/codex

app_codex_path_security() {
  local directory mode
  for directory in /opt /usr /usr/local /usr/local/bin "$CODEX_PARENT" "$CODEX_DIR"; do
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

# Exact runtime allowlist for the pinned Linux package; never chmod the cache,
# root HOME, npm configs, marker or unrelated files recursively.
app_codex_runtime_paths() {
  local native target
  case $(uname -m) in
    x86_64) native=$CODEX_DIR/node_modules/@openai/codex-linux-x64; target=x86_64-unknown-linux-musl;;
    aarch64) native=$CODEX_DIR/node_modules/@openai/codex-linux-arm64; target=aarch64-unknown-linux-musl;;
    *) fail 'Codex-runtimearchitectuur niet ondersteund'; return 1;;
  esac
  CODEX_RUNTIME_DIRS=("$CODEX_PARENT" "$CODEX_DIR" "$CODEX_DIR/node_modules" "$CODEX_DIR/node_modules/.bin"
    "$CODEX_DIR/node_modules/@openai" "$CODEX_DIR/node_modules/@openai/codex" "$CODEX_DIR/node_modules/@openai/codex/bin"
    "$native" "$native/vendor" "$native/vendor/$target" "$native/vendor/$target/codex" "$native/vendor/$target/path")
  CODEX_RUNTIME_DATA=("$CODEX_DIR/node_modules/@openai/codex/package.json" "$native/package.json")
  CODEX_RUNTIME_EXEC=("$CODEX_DIR/node_modules/@openai/codex/bin/codex.js"
    "$native/vendor/$target/codex/codex" "$native/vendor/$target/path/rg")
}

app_codex_runtime_present() {
  app_codex_runtime_paths || return
  local path
  for path in "${CODEX_RUNTIME_DIRS[@]}"; do [[ -d $path ]] || return 1; done
  for path in "${CODEX_RUNTIME_DATA[@]}" "${CODEX_RUNTIME_EXEC[@]}"; do [[ -f $path ]] || return 1; done
  [[ -L $CODEX_DIR/node_modules/.bin/codex ]]
}

app_codex_runtime_security() {
  app_codex_path_security || return
  app_codex_runtime_present || return
  local path mode
  for path in "${CODEX_RUNTIME_DIRS[@]}" "${CODEX_RUNTIME_DATA[@]}" "${CODEX_RUNTIME_EXEC[@]}"; do
    [[ ! -L $path && $(stat -c %u "$path") == 0 ]] || { fail 'Onveilig Codex-runtimepad'; return 1; }
    mode=$(stat -c %a "$path") || return
    (( (8#$mode & 8#7022) == 0 )) || { fail 'Onveilige Codex-runtimerechten'; return 1; }
  done
  [[ $(stat -c %u "$CODEX_DIR/node_modules/.bin/codex") == 0 &&
     $(readlink -f "$CODEX_DIR/node_modules/.bin/codex") == "$CODEX_DIR/node_modules/@openai/codex/bin/codex.js" ]] || return 1
}

app_codex_permissions_repair() {
  app_codex_runtime_security || return
  local path
  for path in "${CODEX_RUNTIME_DIRS[@]}" "${CODEX_RUNTIME_EXEC[@]}"; do chmod 755 "$path" || return; done
  for path in "${CODEX_RUNTIME_DATA[@]}"; do chmod 644 "$path" || return; done
}

app_codex_verify() {
  app_codex_runtime_security || return
  local path
  for path in "${CODEX_RUNTIME_DIRS[@]}" "${CODEX_RUNTIME_EXEC[@]}"; do [[ $(stat -c %a "$path") == 755 ]] || return 1; done
  for path in "${CODEX_RUNTIME_DATA[@]}"; do [[ $(stat -c %a "$path") == 644 ]] || return 1; done
  [[ -L $CODEX_LINK && $(readlink "$CODEX_LINK") == "$CODEX_DIR/node_modules/.bin/codex" ]] || return 1
  [[ $("$CODEX_DIR/node_modules/.bin/codex" --version) == "codex-cli $CODEX_VERSION" ]] || return 1
  # A real unprivileged execution, with no inherited credentials or root config.
  [[ $(runuser -u nobody -- env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/nonexistent CODEX_HOME=/nonexistent \
    "$CODEX_LINK" --version 2>/dev/null) == "codex-cli $CODEX_VERSION" ]] || {
    fail 'Codex werkt niet zonder rootrechten'; return 1;
  }
}

app_codex_install() {
  local assets="$INSTALLER_DIR/bash/assets/codex" major npm_work
  major=$(node --version) || return
  major=${major#v}; major=${major%%.*}
  if ! [[ $major =~ ^[0-9]+$ ]] || (( major != 22 && major != 24 )); then
    fail 'Codex vereist een gevalideerde Node LTS-versie (22 of 24)'; return 1
  fi
  [[ $(sha256sum "$assets/package-lock.json" | awk '{print $1}') == "$CODEX_LOCK_SHA256" ]] || {
    fail 'Codex lock-integriteit mislukt'; return 1;
  }
  app_codex_path_security || return
  if [[ -e $CODEX_LINK || -L $CODEX_LINK ]]; then
    [[ -L $CODEX_LINK && $(readlink "$CODEX_LINK") == "$CODEX_DIR/node_modules/.bin/codex" ]] || {
      fail 'Bestaande Codex-installatie wordt niet overschreven'; return 1;
    }
  fi
  if app_codex_runtime_present; then
    app_codex_permissions_repair || return
    ln -sfn "$CODEX_DIR/node_modules/.bin/codex" "$CODEX_LINK" || return
    app_codex_verify
    return
  fi
  [[ ! -L $CODEX_DIR/node_modules ]] || { fail 'Onveilige npm-runtime'; return 1; }
  # Explicit parent mode: install -d otherwise creates an implicit 0700 parent.
  install -d -m 0755 "$CODEX_PARENT" "$CODEX_DIR" || return
  (umask 077; printf '%s\n' "$CODEX_VERSION" > "$CODEX_DIR/.uli-managed") || return
  install -m 0644 "$assets/package.json" "$assets/package-lock.json" "$CODEX_DIR/" || return
  npm_work=$(mktemp -d /tmp/uli-npm.XXXXXXXX) || return
  install -m 600 /dev/null "$npm_work/user.npmrc" || return
  install -m 600 /dev/null "$npm_work/global.npmrc" || return
  # Public package runtime only; HOME/cache/config/output remain below private 0700.
  if ! (umask 022; env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME="$npm_work" \
    npm ci --prefix "$CODEX_DIR" --ignore-scripts --include=optional --engine-strict \
    --registry=https://registry.npmjs.org --userconfig="$npm_work/user.npmrc" --globalconfig="$npm_work/global.npmrc" \
    --audit=false --fund=false --loglevel=error > "$npm_work/output" 2>&1); then
    rm -rf -- "$npm_work"
    fail 'Codex npm-integriteitsinstallatie mislukt; uitvoer afgeschermd'; return 1
  fi
  rm -rf -- "$npm_work"
  app_codex_permissions_repair || return
  ln -sfn "$CODEX_DIR/node_modules/.bin/codex" "$CODEX_LINK" || return
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
