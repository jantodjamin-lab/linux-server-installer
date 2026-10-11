#!/usr/bin/env bash
# Never provisions the host; all target changes occur in disposable QEMU guests.
set -Eeuo pipefail
profile=${1:-APP}; scenario=${2:-swap0}
case $profile in APP|DB|APP+DB) ;; *) exit 2;; esac
case $scenario in swap0|swap2|swap4|interruption|transip) ;; *) exit 2;; esac
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
cat > "$work/guest.sh" <<'GUEST'
#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /evidence
mount -t 9p -o trans=virtio,version=9p2000.L evidence /evidence
exec > >(tee -a /evidence/guest.log) 2>&1
trap 'echo FAIL > /evidence/result; sync; systemctl poweroff' ERR
source /etc/os-release
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
 if [[ $SCENARIO == interruption ]]; then
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
   if [[ -e /evidence/pre-mutation-pause ]] && systemctl is-enabled --quiet universal-linux-installer-resume.service && grep -Eq "^current=(app|database)" /var/lib/universal-linux-installer/state 2>/dev/null; then break; fi
   sleep 1
  done
  systemctl is-enabled --quiet universal-linux-installer-resume.service
  [[ -e /evidence/pre-mutation-pause ]]
  grep -Eq "^current=(app|database)" /var/lib/universal-linux-installer/state
  cp /var/lib/universal-linux-installer/state /evidence/interrupted-state
  kill -0 "$pid"
 else
  bash install.sh --profile "$PROFILE" --yes
 fi
 echo REBOOT_REQUIRED > /evidence/result
 sync; systemctl reboot
else
 for ((i=0;i<1800;i++)); do
  if bash install.sh --status > /evidence/status.txt 2>&1 && grep -Eq 'COMPLETE|complete' /evidence/status.txt; then break; fi
  sleep 2
 done
 grep -Eq 'COMPLETE|complete' /evidence/status.txt
 swap=$(swapon --show=SIZE --bytes --noheadings | awk '{s+=$1} END {printf "%.0f",s}')
 ((swap >= 4294967296))
 cp /etc/fstab /evidence/fstab-before
 bash install.sh --profile "$PROFILE" --yes
 cmp /etc/fstab /evidence/fstab-before
 command -v python3 >/dev/null || [[ $PROFILE == DB ]]
 if [[ $PROFILE != DB ]]; then
  git --version; dotnet --list-sdks | grep '^10\.'; node --version; npm --version; codex --version; systemctl is-active nginx
 fi
 if [[ $PROFILE != APP ]]; then
  sudo -u postgres psql -Atc 'show server_version' | grep '^18\.'
  systemctl is-active postgresql
 fi
 swapon --show > /evidence/swap-after-reboot.txt
 cp -a /var/lib/universal-linux-installer /evidence/state
 echo PASS > /evidence/result; sync; systemctl poweroff
fi
GUEST
# A persistent boot service starts evidence verification on the second real boot.
script=$(base64 -w0 "$work/guest.sh")
cat > "$work/user-data" <<EOF2
#cloud-config
write_files:
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
      After=network-online.target cloud-final.service universal-linux-installer-resume.service
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
  - systemctl enable uli-vm-test.service
  - systemctl start --no-block uli-vm-test.service
EOF2
printf 'instance-id: uli-%s\nlocal-hostname: uli-test\n' "$RANDOM" > "$work/meta-data"
cloud-localds "$work/seed.img" "$work/user-data" "$work/meta-data"
qemu-img create -f qcow2 -F qcow2 -b "$(realpath "$ULI_VM_IMAGE")" "$work/disk.qcow2" 35G
accel=(-accel "tcg,thread=multi" -cpu max)
[[ ! -r /dev/kvm || ! -w /dev/kvm ]] || accel=(-enable-kvm -cpu host)
for boot in 1 2; do
 timeout --kill-after=30s "${ULI_VM_TIMEOUT:-100m}" qemu-system-x86_64 "${accel[@]}" -smp 2 -m 4096 \
 -drive "file=$work/disk.qcow2,format=qcow2,if=virtio" \
 -drive "file=$work/seed.img,format=raw,if=virtio,readonly=on" \
 -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
 -virtfs "local,path=$work/artifacts,mount_tag=evidence,security_model=none" \
 -nographic -no-reboot > "$work/serial-$boot.log" 2>&1
 [[ -f $work/artifacts/result ]]
 result=$(cat "$work/artifacts/result")
 [[ $result != FAIL ]] || exit 1
 [[ $result != PASS ]] || break
 [[ $result == REBOOT_REQUIRED ]]
done
[[ $(cat "$work/artifacts/result") == PASS ]]
echo "PASS $profile/$scenario evidence=$work"
