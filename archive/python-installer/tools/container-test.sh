#!/bin/sh
# Only run INSIDE the disposable Ubuntu 26.04 CI container.
set -eu
[ -f /.dockerenv ] || { echo 'Refusing: container marker missing' >&2; exit 2; }
. /etc/os-release
[ "$ID:$VERSION_ID" = ubuntu:26.04 ] || exit 2
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=600 update
apt-get -o DPkg::Lock::Timeout=600 --no-remove --no-install-recommends -y install python3 gpg gpgv util-linux ca-certificates curl iproute2
python3 -B tools/container-test.py
