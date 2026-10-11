# Bash V1 acceptance evidence

**NO-GO — validation in progress.**

Production approval requires successful Bash regression tests, all three profiles with actual Ubuntu 26.04.1 packages, actual swap activation (0/2/4+ GiB), a real second boot proving automatic interrupted-profile resume and persistent swap, idempotent repetition, interrupted-swap handling, APT failures, missing packages, sudo, read-only audit, locking, release integrity and no high/critical findings.

No isolated mock is counted as proof of actual installation or reboot. CI logs and artifacts must refer to the exact published commit. A prerelease with NO-GO is allowed if real acceptance is externally blocked; a stable release is prohibited until these checks pass.
