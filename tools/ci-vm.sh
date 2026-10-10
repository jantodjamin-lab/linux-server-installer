#!/bin/sh
# Disposable GitHub-hosted Linux runner only. Never install development host prerequisites.
set -eu
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ] && [ "${RUNNER_OS:-}" = Linux ] || {
  echo 'Refusing: disposable GitHub-hosted Linux runner required' >&2; exit 2;
}
[ "$PWD" = "${GITHUB_WORKSPACE:-}" ] && [ -d "${RUNNER_TEMP:-/nonexistent}" ] || {
  echo 'Refusing: GitHub workspace and temporary directory required' >&2; exit 2;
}
: "${PROFILE:?Set profile}"
case "$PROFILE" in APP|DB|APP+DB) ;; *) exit 2;; esac
mkdir -p e2e-logs
IMAGE_URL=${IMAGE_URL:-https://cloud-images.ubuntu.com/releases/resolute/release/ubuntu-26.04-server-cloudimg-amd64.img}
case "$IMAGE_URL" in https://cloud-images.ubuntu.com/releases/resolute/*/ubuntu-26.04-server-cloudimg-amd64.img|https://cloud-images.ubuntu.com/resolute/*/resolute-server-cloudimg-amd64.img) ;; *) exit 2;; esac
# Only disposable CI-runner prerequisites; no development host or real target changes.
sudo apt-get -o DPkg::Lock::Timeout=600 update
sudo apt-get -o DPkg::Lock::Timeout=600 -y install qemu-system-x86 qemu-utils cloud-image-utils gpg gpgv
image_dir="$RUNNER_TEMP/verified-image"
mkdir -m 700 "$image_dir" "$image_dir/gnupg"
image_name=${IMAGE_URL##*/}
image_base=${IMAGE_URL%/*}
for name in SHA256SUMS SHA256SUMS.gpg; do
  curl -q --fail --location --connect-timeout 30 --max-time 300 --proto '=https' --proto-redir '=https' "$image_base/$name" -o "$image_dir/$name"
done
# Fingerprint pinned from Canonical public-image verification documentation.
cloud_key=D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81
curl -q --fail --location --connect-timeout 30 --max-time 300 --proto '=https' --proto-redir '=https' "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$cloud_key" -o "$image_dir/key.asc"
gpg --batch --homedir "$image_dir/gnupg" --import "$image_dir/key.asc"
actual_key=$(gpg --batch --homedir "$image_dir/gnupg" --with-colons --fingerprint "$cloud_key" | awk -F: '$1=="fpr" { print $10; exit }')
[ "$actual_key" = "$cloud_key" ]
gpg --batch --homedir "$image_dir/gnupg" --export "$cloud_key" > "$image_dir/keyring.gpg"
gpgv --homedir "$image_dir/gnupg" --keyring "$image_dir/keyring.gpg" --status-fd 1 "$image_dir/SHA256SUMS.gpg" "$image_dir/SHA256SUMS" > "$image_dir/signature-status.txt"
grep -Eq "^\[GNUPG:\] VALIDSIG $cloud_key " "$image_dir/signature-status.txt"
verified_sha=$(awk -v file="*$image_name" '$2==file { print $1 }' "$image_dir/SHA256SUMS")
[ "${#verified_sha}" -eq 64 ]
[ -z "$IMAGE_SHA" ] || [ "$IMAGE_SHA" = "$verified_sha" ]
curl -q --fail --location --connect-timeout 30 --max-time 300 --proto '=https' --proto-redir '=https' "$IMAGE_URL" -o "$image_dir/$image_name"
printf '%s  %s\n' "$verified_sha" "$image_dir/$image_name" | sha256sum -c -
cp "$image_dir/SHA256SUMS" "$image_dir/signature-status.txt" e2e-logs/
export RC5_E2E_IMAGE="$image_dir/$image_name" RC5_E2E_IMAGE_SHA256="$verified_sha" TMPDIR="$PWD/e2e-logs"
if [ "${VM_SECURITY:-false}" = true ]; then export RC5_E2E_SECURITY=1; fi
# Smoke all three profiles with real systemd, TransIP mirror and APP development tools.
# Each parallel fault job selects exactly one fresh-VM interruption event.
sh tools/e2e-vm.sh "$PROFILE" > e2e-logs/status.txt 2>&1
cat e2e-logs/status.txt
