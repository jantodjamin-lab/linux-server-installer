# Recovery and automatic resume

Progress is persistent under `/var/lib/universal-linux-installer/`: profile, installer version, completed steps, interrupted step, status and UTC update time. State is data, never executable shell code. A process lock prevents simultaneous installations.

After the original confirmation the installer stages a root-owned copy and registers a systemd resume service. A reboot runs that copy, reads the original profile and checks completed components. Completed changes are not blindly reapplied. The swap invariant is checked after reboot, including completed installations; completed profiles never restart from the beginning.

An interrupted step is rechecked before retry. Swap creation records ownership and phases; a foreign file, incompatible state/version, changed configuration or an uncertain destructive operation stops with FAIL. The installer never truncates an unknown swap file or removes package-manager locks. No automatic `dpkg --configure -a`, OS upgrade, database repair or deletion is attempted.

Inspect status using menu option 4 or `bash install.sh --audit`. Inspect the root-only state/log and `journalctl -u universal-linux-installer-resume.service` as an administrator. Logs intentionally omit raw package output that could expose authenticated source URLs. Do not source or edit state files to bypass checks.

Before manual recovery, retain state and logs, identify the exact interrupted step and review package-manager/database health. Fix the underlying problem, then rerun the verified installer. A version mismatch requires operator review; do not replace the staged copy during a pending installation.
