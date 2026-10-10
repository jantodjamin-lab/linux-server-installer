#!/bin/sh
# Local disposable KVM only. Never SSH/remote; never installs host prerequisites.
set -eu
profile=${1:-APP}
case "$profile" in APP|DB|APP+DB) ;; *) echo 'Invalid profile' >&2; exit 2;; esac
for binary in qemu-system-x86_64 qemu-img cloud-localds python3 tar timeout sha256sum; do
  command -v "$binary" >/dev/null || { echo "SKIP layer 3: missing $binary" >&2; exit 77; }
done
[ -r /dev/kvm ] && [ -w /dev/kvm ] || { echo 'SKIP layer 3: usable KVM absent' >&2; exit 77; }
: "${RC5_E2E_IMAGE:?Set path to a locally verified Ubuntu 26.04 amd64 cloud image}"
: "${RC5_E2E_IMAGE_SHA256:?Set independently trusted cloud-image SHA256}"
printf '%s  %s\n' "$RC5_E2E_IMAGE_SHA256" "$RC5_E2E_IMAGE" | sha256sum -c -
base=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/rc5-vm.XXXXXXXX")
export RC5_E2E_WORK=$work RC5_E2E_BASE=$base RC5_E2E_PROFILE=$profile
# All overlays, seed files and evidence are preserved for operator inspection.
python3 -B "$base/tools/e2e-seed.py"
run_cases() {
for case_dir in "$@"; do
  qemu-img create -f qcow2 -F qcow2 -b "$RC5_E2E_IMAGE" "$case_dir/disk.qcow2" 110G
  memory=$(cat "$case_dir/memory")
  timeout 90m qemu-system-x86_64 -enable-kvm -cpu host -smp 1 -m "$memory" \
    -drive "file=$case_dir/disk.qcow2,format=qcow2,if=virtio" \
    -drive "file=$case_dir/seed.img,format=raw,if=virtio,readonly=on" \
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
    -virtfs "local,path=$case_dir/artifacts,mount_tag=rc5logs,security_model=mapped-xattr" \
    -nographic -no-reboot >"$case_dir/serial.log" 2>&1
  [ -f "$case_dir/artifacts/result.json" ] || { echo "FAIL layer 3: no result; inspect $case_dir" >&2; exit 1; }
  python3 -B -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "PASS"' "$case_dir/artifacts/result.json"
done
}
run_cases "$work"/case-0*
if [ "${RC5_E2E_MATRIX:-0}" = 1 ]; then
  RC5_E2E_FAULT_EVENTS=$(python3 -B -c 'import json,sys; print(json.load(open(sys.argv[1]))["journal_events"])' "$work/case-000/artifacts/result.json")
  export RC5_E2E_ONLY_FAULTS=1 RC5_E2E_FAULT_EVENTS
  python3 -B "$base/tools/e2e-seed.py"
  run_cases "$work"/case-1*
fi
printf 'PASS local VM scenarios; evidence: %s; owner acceptance still required\n' "$work"
