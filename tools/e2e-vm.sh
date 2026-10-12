#!/usr/bin/env bash
# Never provisions the host; all target changes occur in disposable QEMU guests.
set -Eeuo pipefail
profile=${1:-APP}; scenario=${2:-swap0}
case $profile in APP|DB|APP+DB) ;; *) exit 2;; esac
case $scenario in swap0|swap2|swap4|interruption|swap-interruption|transip|codex-repair|baseline-reuse|bootstrap-candidate|bootstrap-public) ;; *) exit 2;; esac
for cmd in qemu-system-x86_64 qemu-img cloud-localds tar timeout sha256sum base64; do
 command -v "$cmd" >/dev/null || { echo "BLOCKED missing $cmd" >&2; exit 77; }
done
: "${ULI_VM_IMAGE:?verified Ubuntu image required}" "${ULI_VM_SHA256:?trusted SHA256 required}"
printf '%s  %s\n' "$ULI_VM_SHA256" "$ULI_VM_IMAGE" | sha256sum -c -
base=$(cd -- "$(dirname "$0")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/bash-v1-vm.XXXXXXXX")
mkdir "$work/artifacts"
tar -czf "$work/installer.tar.gz" -C "$base" install.sh bash VERSION
payload=$(base64 -w0 "$work/installer.tar.gz")
previous_payload=''
bootstrap_payload='' fixture_ca=''
fixture_pid=''
trap 'if [[ -n $fixture_pid ]]; then kill "$fixture_pid" 2>/dev/null || true; fi' EXIT
if [[ $scenario == bootstrap-candidate || $scenario == bootstrap-public ]]; then
 [[ $profile == DB ]] || { echo 'Bootstrap acceptance requires DB profile' >&2; exit 2; }
 version=$(cat "$base/VERSION")
 [[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]
 if [[ $scenario == bootstrap-candidate ]]; then
  command -v openssl >/dev/null
  bash "$base/tools/release.sh"
  archive=$base/release/universal-linux-installer-$version.tar.gz
  archive_sha=$(sha256sum "$archive" | awk '{print $1}')
  mkdir -m 700 "$work/https"
  cp "$archive" "$work/https/"
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=isolated-uli-fixture' \
   -addext 'subjectAltName=IP:10.0.2.2' -addext 'basicConstraints=critical,CA:TRUE' \
   -keyout "$work/fixture.key" -out "$work/fixture.crt" > "$work/fixture-cert.log" 2>&1
  fixture_ca=$(base64 -w0 "$work/fixture.crt")
  (cd "$work/https" && exec openssl s_server -accept 127.0.0.1:8443 -cert "$work/fixture.crt" -key "$work/fixture.key" -WWW -quiet) > "$work/https.log" 2>&1 & fixture_pid=$!
  for ((attempt=0;attempt<10;attempt++)); do
   if curl -q --fail --silent --connect-timeout 2 --max-time 5 --cacert "$work/fixture.crt" --resolve 10.0.2.2:8443:127.0.0.1 --noproxy '*' "https://10.0.2.2:8443/universal-linux-installer-$version.tar.gz" -o "$work/fixture-check.tar.gz"; then break; fi
   sleep 0.1
  done
  [[ $(sha256sum "$work/fixture-check.tar.gz" | awk '{print $1}') == "$archive_sha" ]]
 else
  archive_sha=${ULI_PUBLIC_ARCHIVE_SHA:-}
  [[ $archive_sha =~ ^[a-f0-9]{64}$ ]] || { echo 'Trusted public archive SHA required' >&2; exit 2; }
  archive=$work/public-release.tar.gz
  curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 30 --max-time 300 --max-filesize 33554432 \
   "https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v$version/universal-linux-installer-$version.tar.gz" --output "$archive"
  [[ $(sha256sum "$archive" | awk '{print $1}') == "$archive_sha" ]]
 fi
 if [[ $scenario == bootstrap-candidate ]]; then
  bash "$base/tools/render-bootstrap.sh" "$version" "$archive" "$work/rendered" \
   "https://10.0.2.2:8443/universal-linux-installer-$version.tar.gz" 'https://10.0.2.2:8443/bootstrap.sh'
  cp "$work/rendered/bootstrap.sh" "$work/https/bootstrap.sh"
 else
  bash "$base/tools/render-bootstrap.sh" "$version" "$archive" "$work/rendered"
 fi
 # Execute the generated user command, including HTTPS bootstrap download/pin.
 bootstrap_payload=$(base64 -w0 "$work/rendered/ONE-LINER.txt")
 cp "$work/rendered/ONE-LINER.txt" "$work/artifacts/bootstrap-command.txt"
 cp "$work/rendered/BOOTSTRAP.sha256" "$work/artifacts/BOOTSTRAP.sha256"
 printf 'version=%s\narchive_sha256=%s\nscenario=%s\n' "$version" "$archive_sha" "$scenario" > "$work/artifacts/bootstrap-pins.txt"
fi
if [[ $scenario == codex-repair || $scenario == baseline-reuse ]]; then
 previous_commit=7f8e74f0f8fc7892abc10ba5b2f1c5b63f612db1
 [[ $scenario != baseline-reuse ]] || previous_commit=cf024d7b23eb94a008db560760a3878f7f825ea4
 git -C "$base" archive "$previous_commit" install.sh bash VERSION | gzip -n > "$work/previous.tar.gz"
 previous_payload=$(base64 -w0 "$work/previous.tar.gz")
fi
cat > "$work/guest.sh" <<'GUEST'
#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /evidence
mount -t 9p -o trans=virtio,version=9p2000.L evidence /evidence
exec > >(tee -a /evidence/guest.log) 2>&1
guest_pid=$BASHPID
failure_evidence() {
 local failure_status=$? failure_line=${BASH_LINENO[0]:-unknown}
 trap - ERR
 # A failed command substitution must fail its parent, never power off itself.
 if [[ $BASHPID != "$guest_pid" ]]; then exit "$failure_status"; fi
 set +e
 echo "FAIL exit=$failure_status line=$failure_line" > /evidence/failure.txt
 cp /etc/os-release /evidence/os-release
 uname -a > /evidence/uname.txt
 df -h > /evidence/disk.txt
 swapon --show > /evidence/swap-failure.txt
 cp /var/lib/universal-linux-installer/state /evidence/failed-state
 systemctl show universal-linux-installer-resume.service postgresql@18-main.service nginx.service -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus -p ExecMainStartTimestampMonotonic > /evidence/component-service-status.txt
 if command -v pg_lsclusters >/dev/null; then pg_lsclusters > /evidence/postgresql-clusters.txt; fi
 journalctl --no-pager -u universal-linux-installer-resume.service -u uli-vm-test.service > /evidence/services.txt
 echo FAIL > /evidence/result
 sync
 systemctl poweroff
 exit "$failure_status"
}
trap failure_evidence ERR
source /etc/os-release
cp /etc/os-release /evidence/os-release
uname -a > /evidence/uname.txt
printf "Guest OS: %s\n" "$PRETTY_NAME"
[[ $VERSION_ID == 26.04 && $PRETTY_NAME == *26.04.1* ]] || { echo 'BLOCKED exact Ubuntu 26.04.1 image required'; false; }
cd /opt/installer
if [[ ! -e /var/lib/uli-vm-firstboot ]]; then
 touch /var/lib/uli-vm-firstboot
 if [[ $SCENARIO == transip ]]; then
  mkdir -p /etc/apt/sources.list.d
  mv /etc/apt/sources.list.d/ubuntu.sources /etc/apt/ubuntu.sources.saved
  printf "%s\n" "Types: deb" "URIs: https://mirror.transip.net/ubuntu/ubuntu/" "Suites: resolute resolute-updates resolute-security" "Components: main universe restricted multiverse" "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg" > /etc/apt/sources.list.d/provider-test.sources
 fi
 if [[ $SCENARIO == swap2 || $SCENARIO == swap4 ]]; then
  size=2; [[ $SCENARIO != swap4 ]] || size=4
  dd if=/dev/zero of=/existing-swap bs=1M count=$((size*1024+1)) status=none
  chmod 600 /existing-swap; mkswap /existing-swap; swapon /existing-swap
  echo '/existing-swap none swap sw 0 0' >> /etc/fstab
 fi
 if [[ $SCENARIO == bootstrap-candidate || $SCENARIO == bootstrap-public ]]; then
  [[ ! -e /var/lib/universal-linux-installer/state ]]
  if [[ $SCENARIO == bootstrap-candidate ]]; then
   install -m 644 /opt/fixture-ca.crt /usr/local/share/ca-certificates/uli-test-fixture.crt
   update-ca-certificates
  fi
  id ubuntu > /evidence/bootstrap-user.txt
  # script allocates the controlling terminal required by the exact bootstrap.
  printf '2\nja\n' | runuser -u ubuntu -- env TERM=xterm script --quiet --return --command '/bin/bash /opt/candidate-bootstrap.sh' /tmp/uli-bootstrap-session.txt
  cp /tmp/uli-bootstrap-session.txt /evidence/bootstrap-pty.txt
  grep -q 'UNIVERSAL LINUX INSTALLER' /evidence/bootstrap-pty.txt
  grep -q 'Bevestig installatie' /evidence/bootstrap-pty.txt
  grep -Eq '\[[#-]{20}\]' /evidence/bootstrap-pty.txt
  grep -Eq '7/7.*100%' /evidence/bootstrap-pty.txt
  [[ -f /var/lib/universal-linux-installer/state ]]
  grep -qx 'profile=database' /var/lib/universal-linux-installer/state
  grep -qx 'status=complete' /var/lib/universal-linux-installer/state
  [[ $(stat -c %u /var/lib/universal-linux-installer/state) == 0 && $(stat -c %a /var/lib/universal-linux-installer/state) == 600 ]]
  target_version=$(cat /opt/installer/VERSION)
  staged=/var/lib/universal-linux-installer/installer-$target_version
  [[ -d $staged && $(stat -c %u "$staged") == 0 && $(stat -c %a "$staged") == 700 ]]
  for component in /opt/installer/install.sh /opt/installer/VERSION /opt/installer/bash/*.sh /opt/installer/bash/assets/codex/*.json; do
   relative=${component#/opt/installer/}
   cmp "$component" "$staged/$relative"
   sha256sum "$staged/$relative" >> /evidence/bootstrap-staged-source.sha256
  done
  sha256sum /var/lib/universal-linux-installer/state > /evidence/state-before-status.sha256
  runuser -u ubuntu -- /bin/bash /opt/installer/install.sh --status > /evidence/status-normal-user.txt
  grep -qx 'Status: COMPLETE' /evidence/status-normal-user.txt
  grep -q 'Voortgang: 7/7 (100%)' /evidence/status-normal-user.txt
  [[ $(stat -c %u /var/lib/universal-linux-installer-status/status) == 0 && $(stat -c %a /var/lib/universal-linux-installer-status/status) == 644 ]]
  runuser -u ubuntu -- test -r /etc/profile.d/universal-linux-installer-status.sh
  runuser -u ubuntu -- env TERM=xterm script --quiet --return --command "/bin/bash --login -i -c ':'" /tmp/uli-login-session.txt </dev/null
  cp /tmp/uli-login-session.txt /evidence/login-status-pty.txt
  grep -q 'UNIVERSAL LINUX INSTALLER' /evidence/login-status-pty.txt
  sha256sum -c /evidence/state-before-status.sha256
  echo 'PASS pinned HTTPS archive bootstrap, real ubuntu PTY menu authorization and root staging' > /evidence/bootstrap-result.txt
 elif [[ $SCENARIO == codex-repair || $SCENARIO == baseline-reuse ]]; then
  bash /opt/previous-installer/install.sh --profile "$PROFILE" --yes
  previous_version=$(cat /opt/previous-installer/VERSION)
  /usr/local/bin/codex --version
  if [[ $SCENARIO == codex-repair ]]; then
   if runuser -u ubuntu -- /usr/local/bin/codex --version >/dev/null 2>&1; then echo 'FAIL previous release did not reproduce root-only Codex'; false; fi
  else
   runuser -u ubuntu -- /usr/local/bin/codex --version > /evidence/baseline-codex-normal-user.txt
   grep -qx 'codex-cli 0.128.0' /evidence/baseline-codex-normal-user.txt
  fi
  cp /var/lib/universal-linux-installer/state /evidence/state-before-codex-repair
  # Harmless private fixtures prove permissions repair does not expose data.
  install -d -m 700 /opt/universal-linux-installer/codex/.private-permission-fixture
  (umask 077; printf 'private regression fixture\n' > /opt/universal-linux-installer/codex/.private-permission-fixture/config)
  sha256sum /opt/universal-linux-installer/codex/.private-permission-fixture/config > /evidence/private-fixture.sha256
  if [[ $SCENARIO == baseline-reuse ]]; then
   cat > /usr/local/sbin/apt-get <<'BASELINE_APT_WRAPPER'
#!/usr/bin/env bash
echo 'FAIL APT mutation during complete baseline reuse' > /evidence/unexpected-baseline-apt
exit 1
BASELINE_APT_WRAPPER
   chmod 755 /usr/local/sbin/apt-get
  fi
  # Interrupt precisely after switching the resume unit but before committing
  # the new state version. The persistent authorization must bridge this reboot.
  cat > /usr/local/sbin/systemctl <<'SYSTEMCTL_WRAPPER'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $1 == daemon-reload && -e /var/lib/universal-linux-installer/codex-permissions-patch && ! -e /var/lib/uli-codex-patch-paused ]]; then
 /usr/bin/systemctl "$@"
 touch /var/lib/uli-codex-patch-paused
 echo 'Paused after authorized resume unit switch' > /evidence/codex-patch-pause
 while :; do sleep 1; done
fi
exec /usr/bin/systemctl "$@"
SYSTEMCTL_WRAPPER
  chmod 755 /usr/local/sbin/systemctl
  bash install.sh --profile "$PROFILE" --yes & pid=$!
  for ((i=0;i<900;i++)); do [[ ! -e /evidence/codex-patch-pause ]] || break; sleep 1; done
  [[ -e /evidence/codex-patch-pause ]]
  grep -qx "version=$previous_version" /var/lib/universal-linux-installer/state
  [[ $(stat -c %a /var/lib/universal-linux-installer/codex-permissions-patch) == 600 ]]
  cp /var/lib/universal-linux-installer/state /evidence/interrupted-codex-patch-state
  kill -0 "$pid"
 elif [[ $SCENARIO == swap-interruption ]]; then
  cat > /usr/local/sbin/dd <<'DD_WRAPPER'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $* == *of=/var/lib/universal-linux-installer/swapfile* && ! -e /var/lib/uli-vm-swap-paused ]]; then
 /usr/bin/dd if=/dev/zero of=/var/lib/universal-linux-installer/swapfile bs=1048576 count=1 conv=fsync status=none
 touch /var/lib/uli-vm-swap-paused
 echo 'Paused after actual 1 MiB allocation' > /evidence/swap-allocation-pause
 while :; do sleep 1; done
fi
exec /usr/bin/dd "$@"
DD_WRAPPER
  chmod 0755 /usr/local/sbin/dd
  bash install.sh --profile "$PROFILE" --yes & pid=$!
  for ((i=0;i<900;i++)); do
   [[ ! -e /evidence/swap-allocation-pause ]] || break
   sleep 1
  done
  [[ -e /evidence/swap-allocation-pause ]]
  systemctl is-enabled --quiet universal-linux-installer-resume.service
  grep -qx 'current=swap' /var/lib/universal-linux-installer/state
  [[ ! -e /var/lib/universal-linux-installer/swap-owner ]]
  stat -c %s /var/lib/universal-linux-installer/swapfile > /evidence/partial-size
  [[ $(cat /evidence/partial-size) == 1048576 ]]
  sha256sum /var/lib/universal-linux-installer/swapfile > /evidence/partial-sha256
  cp /etc/fstab /evidence/fstab-before
  cp /var/lib/universal-linux-installer/state /evidence/interrupted-state
  kill -0 "$pid"
 elif [[ $SCENARIO == interruption ]]; then
  cat > /usr/local/sbin/apt-get <<'APT_WRAPPER'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $* == *install* && $* != *--simulate* && ! -e /var/lib/uli-vm-paused ]]; then
 touch /var/lib/uli-vm-paused
 echo 'Paused before actual apt install' > /evidence/pre-mutation-pause
 while :; do sleep 1; done
fi
exec /usr/bin/apt-get "$@"
APT_WRAPPER
  chmod 0755 /usr/local/sbin/apt-get
  bash install.sh --profile "$PROFILE" --yes & pid=$!
  for ((i=0;i<900;i++)); do
   if [[ -e /evidence/pre-mutation-pause ]] && systemctl is-enabled --quiet universal-linux-installer-resume.service && grep -Eq "^current=(app_packages|codex|nginx|postgres|database_check|app|database)" /var/lib/universal-linux-installer/state 2>/dev/null; then break; fi
   sleep 1
  done
  systemctl is-enabled --quiet universal-linux-installer-resume.service
  [[ -e /evidence/pre-mutation-pause ]]
  grep -Eq "^current=(app_packages|codex|nginx|postgres|database_check|app|database)" /var/lib/universal-linux-installer/state
  cp /var/lib/universal-linux-installer/state /evidence/interrupted-state
  kill -0 "$pid"
 else
  if [[ $PROFILE == DB && $SCENARIO == swap0 ]]; then
   # Actual nonroot entry and cloud-image sudo, confined to this disposable guest.
   id ubuntu > /evidence/sudo-entry-user.txt
   runuser -u ubuntu -- /bin/bash /opt/installer/install.sh --profile DB --yes
   echo 'PASS actual ubuntu entry and sudo escalation completed' > /evidence/sudo-result.txt
  else
   if [[ $PROFILE == APP && $SCENARIO == swap0 ]]; then
    # VM-only fault: root succeeds, normal-user verification must block complete.
    cat > /usr/local/sbin/runuser <<'RUNUSER_WRAPPER'
#!/usr/bin/env bash
if [[ $1 == -u && $2 == nobody && -e /var/lib/uli-deny-codex-user ]]; then exit 1; fi
exec /usr/sbin/runuser "$@"
RUNUSER_WRAPPER
    chmod 755 /usr/local/sbin/runuser
    touch /var/lib/uli-deny-codex-user
    if bash install.sh --profile "$PROFILE" --yes; then echo 'FAIL root-only verifier allowed complete'; false; fi
    grep -qx 'status=failed' /var/lib/universal-linux-installer/state
    /usr/local/bin/codex --version
    cp /var/lib/universal-linux-installer/state /evidence/root-only-rejected-state
    rm /var/lib/uli-deny-codex-user
    echo 'PASS real root-only execution rejection prevents complete' > /evidence/root-only-rejection.txt
   fi
   bash install.sh --profile "$PROFILE" --yes
   if [[ $PROFILE == APP && $SCENARIO == swap0 ]]; then
    touch /var/lib/uli-deny-codex-user
    if bash install.sh --profile "$PROFILE" --yes; then echo 'FAIL completed root-only Codex accepted'; false; fi
    grep -qx 'status=failed' /var/lib/universal-linux-installer/state
    grep -qx 'current=verification' /var/lib/universal-linux-installer/state
    cp /var/lib/universal-linux-installer/state /evidence/completed-root-only-rejected-state
    rm /var/lib/uli-deny-codex-user
    # A verification-only retry must never enter the APT mutation route.
    cat > /usr/local/sbin/apt-get <<'VERIFY_APT_WRAPPER'
#!/usr/bin/env bash
echo 'FAIL unexpected APT during completed verification recovery' > /evidence/unexpected-apt
exit 1
VERIFY_APT_WRAPPER
    chmod 755 /usr/local/sbin/apt-get
    bash install.sh --resume
    [[ ! -e /evidence/unexpected-apt ]]
    rm /usr/local/sbin/apt-get
   fi
  fi
 fi
 echo REBOOT_REQUIRED > /evidence/result
 sync; systemctl reboot
else
 if [[ $SCENARIO == swap-interruption ]]; then
  for ((i=0;i<60;i++)); do
   grep -qx 'status=failed' /var/lib/universal-linux-installer/state && break
   sleep 1
  done
  grep -qx 'status=failed' /var/lib/universal-linux-installer/state
  grep -qx 'current=swap' /var/lib/universal-linux-installer/state
  systemctl show universal-linux-installer-resume.service -p Result -p ExecMainStatus -p ExecMainStartTimestampMonotonic > /evidence/resume-service.txt
  grep -qx 'Result=exit-code' /evidence/resume-service.txt
  resume_exit=$(systemctl show universal-linux-installer-resume.service -p ExecMainStatus --value)
  [[ $resume_exit =~ ^[0-9]+$ && $resume_exit != 0 ]]
  resume_started=$(systemctl show universal-linux-installer-resume.service -p ExecMainStartTimestampMonotonic --value)
  [[ $resume_started =~ ^[0-9]+$ && $resume_started != 0 ]]
  [[ ! -e /var/lib/universal-linux-installer/swap-owner ]]
  [[ $(stat -c %s /var/lib/universal-linux-installer/swapfile) == $(cat /evidence/partial-size) ]]
  sha256sum -c /evidence/partial-sha256
  cmp /etc/fstab /evidence/fstab-before
  active_names=$(swapon --show=NAME --noheadings --raw)
  [[ $active_names != */var/lib/universal-linux-installer/swapfile* ]]
  printf "%s\n" "$active_names" > /evidence/active-swap-names
  cp /var/lib/universal-linux-installer/state /evidence/failed-state
  bash install.sh --audit > /evidence/audit.txt
  cmp /var/lib/universal-linux-installer/state /evidence/failed-state
  sha256sum -c /evidence/partial-sha256
  cmp /etc/fstab /evidence/fstab-before
  journalctl --no-pager -u universal-linux-installer-resume.service > /evidence/resume-journal.txt
  echo 'PASS expected fail-safe stop after actual interrupted swap allocation'
  echo PASS > /evidence/result; sync; systemctl poweroff
  exit 0
 fi
 for ((i=0;i<1800;i++)); do
  if bash install.sh --status > /evidence/status.txt 2>&1 && grep -Eq 'COMPLETE|complete' /evidence/status.txt; then break; fi
  sleep 2
 done
 grep -Eq 'COMPLETE|complete' /evidence/status.txt
 # Prove the original enabled service ran successfully on this real second boot.
 systemctl show universal-linux-installer-resume.service -p Result -p ExecMainStatus -p ExecMainStartTimestampMonotonic > /evidence/resume-service.txt
 grep -qx 'Result=success' /evidence/resume-service.txt
 grep -qx 'ExecMainStatus=0' /evidence/resume-service.txt
 resume_started=$(systemctl show universal-linux-installer-resume.service -p ExecMainStartTimestampMonotonic --value)
 [[ $resume_started =~ ^[0-9]+$ && $resume_started != 0 ]]
 journalctl --no-pager -u universal-linux-installer-resume.service > /evidence/resume-journal.txt
 swap=$(swapon --show=SIZE --bytes --noheadings | awk '{s+=$1} END {printf "%.0f",s}')
 ((swap >= 4294967296))
 cp /etc/fstab /evidence/fstab-before
 bash install.sh --profile "$PROFILE" --yes
 cmp /etc/fstab /evidence/fstab-before
 command -v python3 >/dev/null || [[ $PROFILE == DB ]]
 if [[ $PROFILE != DB ]]; then
  git --version; dotnet --list-sdks | grep '^10\.'; node --version; npm --version; codex --version; systemctl is-active nginx
  # Real ordinary user, not merely a root executable-bit check.
  runuser -u ubuntu -- /usr/local/bin/codex --version > /evidence/codex-normal-user.txt
  grep -qx 'codex-cli 0.128.0' /evidence/codex-normal-user.txt
  runuser -u nobody -- env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/nonexistent CODEX_HOME=/nonexistent /usr/local/bin/codex --version > /evidence/codex-unprivileged-probe.txt
  source bash/common.sh; source bash/app.sh
  app_codex_verify
  app_codex_runtime_paths
  for runtime_path in "${CODEX_RUNTIME_DIRS[@]}" "${CODEX_RUNTIME_DATA[@]}" "${CODEX_RUNTIME_EXEC[@]}"; do
   [[ $(stat -c %u "$runtime_path") == 0 ]]
   if runuser -u ubuntu -- test -w "$runtime_path"; then echo 'FAIL user writable Codex runtime'; false; fi
   stat -c '%u %a %n' "$runtime_path" >> /evidence/codex-runtime-permissions.txt
  done
  [[ $(stat -c %a /opt/universal-linux-installer/codex/.uli-managed) == 600 ]]
  if runuser -u ubuntu -- test -r /opt/universal-linux-installer/codex/.uli-managed; then false; fi
  # Other APP tools are package-managed; verify their actual nonroot execution.
  runuser -u ubuntu -- /bin/bash -c 'git --version; python3 --version; dotnet --list-sdks; node --version; npm --version; nginx -v' > /evidence/app-tools-normal-user.txt 2>&1
  if [[ $SCENARIO == codex-repair || $SCENARIO == baseline-reuse ]]; then
   previous_version=$(cat /opt/previous-installer/VERSION)
   target_version=$(cat /opt/installer/VERSION)
   grep -qx "version=$target_version" /var/lib/universal-linux-installer/state
   if [[ $SCENARIO == codex-repair ]]; then
    [[ -d /var/lib/universal-linux-installer/installer ]]
   else
    [[ -d /var/lib/universal-linux-installer/installer-$previous_version ]]
   fi
   [[ -d /var/lib/universal-linux-installer/installer-$target_version ]]
   [[ $(stat -c %a /opt/universal-linux-installer/codex/.private-permission-fixture) == 700 ]]
   [[ $(stat -c %a /opt/universal-linux-installer/codex/.private-permission-fixture/config) == 600 ]]
   sha256sum -c /evidence/private-fixture.sha256
   if runuser -u ubuntu -- test -r /opt/universal-linux-installer/codex/.private-permission-fixture/config; then false; fi
   [[ ! -e /evidence/unexpected-baseline-apt ]]
   echo "PASS actual $previous_version installation reused across interrupted authorized $target_version upgrade" > /evidence/codex-repair-result.txt
  fi
 fi
 if [[ $PROFILE != APP ]]; then
  sudo -u postgres psql -Atc 'show server_version' | grep '^18\.'
  systemctl is-active postgresql
 fi
 swapon --show > /evidence/swap-after-reboot.txt
 # A successful foreground exit is insufficient: a former renderer descendant
 # overwrote COMPLETE after exiting. Require persistent state to remain stable.
 grep -qx 'status=complete' /var/lib/universal-linux-installer/state
 grep -qx 'current=' /var/lib/universal-linux-installer/state
 cp /var/lib/universal-linux-installer/state /evidence/state-before-final-settle
 sleep 5
 grep -qx 'status=complete' /var/lib/universal-linux-installer/state
 grep -qx 'current=' /var/lib/universal-linux-installer/state
 cmp /evidence/state-before-final-settle /var/lib/universal-linux-installer/state
 echo 'PASS COMPLETE persistent state unchanged after foreground retry and renderer settlement' > /evidence/final-state-stability.txt
 # Whitelist metadata only: never export swap contents, VM disks or guest keys.
 mkdir -p /evidence/state
 for metadata in state swap-owner install.log; do
  [[ ! -f /var/lib/universal-linux-installer/$metadata ]] || cp -- /var/lib/universal-linux-installer/"$metadata" /evidence/state/
 done
 journalctl --no-pager -u universal-linux-installer-resume.service > /evidence/resume-journal.txt
 echo PASS > /evidence/result; sync; systemctl poweroff
fi
GUEST
# A persistent boot service starts evidence verification on the second real boot.
script=$(base64 -w0 "$work/guest.sh")
cat > "$work/user-data" <<EOF2
#cloud-config
write_files:
  - path: /opt/candidate-bootstrap.sh
    permissions: '0644'
    encoding: b64
    content: "$bootstrap_payload"
  - path: /opt/fixture-ca.crt
    permissions: '0644'
    encoding: b64
    content: "$fixture_ca"
  - path: /opt/previous.tar.gz
    encoding: b64
    content: "$previous_payload"
  - path: /opt/installer.tar.gz
    encoding: b64
    content: $payload
  - path: /usr/local/sbin/uli-vm-test
    permissions: '0755'
    encoding: b64
    content: $script
  - path: /etc/systemd/system/uli-vm-test.service
    content: |
      [Unit]
      After=network-online.target universal-linux-installer-resume.service
      Wants=network-online.target
      [Service]
      Type=oneshot
      Environment=PROFILE=$profile
      Environment=SCENARIO=$scenario
      ExecStart=/usr/local/sbin/uli-vm-test
      [Install]
      WantedBy=multi-user.target
runcmd:
  - mkdir -p /opt/installer
  - tar -xzf /opt/installer.tar.gz -C /opt/installer
  - if [ "$scenario" = codex-repair ] || [ "$scenario" = baseline-reuse ]; then mkdir -p /opt/previous-installer; tar -xzf /opt/previous.tar.gz -C /opt/previous-installer; fi
  - systemctl enable uli-vm-test.service
  - systemctl start --no-block uli-vm-test.service
EOF2
printf 'instance-id: uli-%s\nlocal-hostname: uli-test\n' "$RANDOM" > "$work/meta-data"
cloud-localds "$work/seed.img" "$work/user-data" "$work/meta-data"
qemu-img create -f qcow2 -F qcow2 -b "$(realpath "$ULI_VM_IMAGE")" "$work/disk.qcow2" 35G
accel=(-accel "tcg,thread=multi" -cpu max)
[[ ! -r /dev/kvm || ! -w /dev/kvm ]] || accel=(-enable-kvm -cpu host)
for boot in 1 2; do
 if timeout --kill-after=30s "${ULI_VM_TIMEOUT:-100m}" qemu-system-x86_64 "${accel[@]}" -smp 2 -m 4096 \
 -drive "file=$work/disk.qcow2,format=qcow2,if=virtio" \
 -drive "file=$work/seed.img,format=raw,if=virtio,readonly=on" \
 -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
 -virtfs "local,path=$work/artifacts,mount_tag=evidence,security_model=none" \
 -nographic -no-reboot > "$work/serial-$boot.log" 2>&1; then :
 else
  vm_status=$?
  printf 'FAIL VM boot %s exited %s; evidence=%s\n' "$boot" "$vm_status" "$work"
  [[ ! -f $work/artifacts/guest.log ]] || tail -60 "$work/artifacts/guest.log"
  exit "$vm_status"
 fi
 [[ -f $work/artifacts/result ]] || { echo "FAIL missing guest result; evidence=$work" >&2; exit 1; }
 result=$(cat "$work/artifacts/result")
 if [[ $result == FAIL ]]; then
  [[ ! -f $work/artifacts/failure.txt ]] || cat "$work/artifacts/failure.txt"
  [[ ! -f $work/artifacts/guest.log ]] || tail -60 "$work/artifacts/guest.log"
  exit 1
 fi
 [[ $result != PASS ]] || break
 [[ $result == REBOOT_REQUIRED ]]
done
[[ $(cat "$work/artifacts/result") == PASS ]]
echo "PASS $profile/$scenario evidence=$work"
