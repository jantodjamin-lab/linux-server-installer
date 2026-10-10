"""Bounded public failure metadata, separately redacted private diagnostics."""
import re


PUBLIC_FAILURE_CODES = frozenset(['source-policy-changed','angular-major', 'angular-version', 'apt-components', 'apt-pin', 'apt-simulation-format', 'apt-simulation-incomplete', 'apt-source-architecture', 'apt-source-duplicate', 'apt-source-enabled', 'apt-source-format', 'apt-source-keyring', 'apt-source-owner', 'apt-source-path', 'apt-source-symlink', 'apt-source-type', 'apt-source-unreviewed-option', 'apt-source-uri-required', 'apt-suite', 'archive-key-fingerprint', 'archive-key-format', 'archive-key-gpg-required', 'archive-key-invalid', 'archive-key-owner', 'archive-key-symlink', 'archive-signature-fingerprint', 'archive-signature-invalid', 'artifact-checksum', 'artifact-kind', 'artifact-path', 'artifact-type', 'checkpoint-binding', 'checkpoint-symlink', 'codex-app-only', 'codex-development-only', 'codex-requires-app', 'completed-step-drift', 'config-symlink', 'development-binding', 'dotnet-major', 'dotnet-version', 'duplicate-json-key', 'duplicate-update', 'existing-config-conflict', 'existing-listener-conflict', 'existing-package-validation', 'existing-service-or-data-conflict', 'existing-swap-file-refused', 'existing-version-conflict', 'explicit-plan-snapshot-and-candidate-approval-required', 'explicit-snapshot-and-candidate-required', 'final-validators', 'foreign-architecture-package-refused', 'incomplete-closure', 'insecure-apt-source', 'installation-not-confirmed', 'intent-approval-mismatch', 'interactive-confirmation-required', 'journal-binding', 'journal-integrity', 'journal-owner', 'journal-types', 'journal-unknown-step', 'lock-map', 'lock-owner', 'lock-schema', 'manifest-schema', 'mirror-uri-invalid', 'new-package-limit-exceeded', 'nginx-default-conflict', 'no-approved-apt-sources', 'node-angular-compatibility', 'node-architecture', 'node-runtime-pin', 'node-version', 'nonfinite-json', 'npm-bundle-required', 'npm-destination-symlink', 'npm-lock-checksum', 'npm-lock-integrity', 'npm-lock-version', 'npm-package-path', 'npm-package-set', 'npm-pin', 'npm-registry', 'npm-root-binding', 'npm-root-package', 'npm-sri', 'npm-symlink', 'npm-version', 'npm-version-binding', 'ownership-binding', 'ownership-symlink', 'package-authenticated-metadata', 'package-dependency-format', 'package-downgrade-refused', 'package-list', 'package-metadata-duplicate', 'package-name', 'package-removal-refused', 'package-schema', 'package-version', 'pinned-package-unavailable', 'plan-date-invalid', 'plan-expired', 'plan-integrity', 'postgresql-major', 'postgresql-version', 'preflight-failed', 'private-directory-required', 'profile-package-set', 'reboot-required-manual-resume', 'refresh-metadata-authorization-required', 'release-metadata-owner', 'release-metadata-symlink', 'root-required', 'root-required-use-interactive-sudo', 'saved-plan-integrity', 'saved-plan-options', 'saved-plan-schema-regenerate-rc5', 'saved-plan-target-or-actions', 'service-guard-drift', 'service-start-guard', 'signed-release-metadata-required', 'snapshot-not-confirmed', 'sudo-execute-only', 'sudo-interactive-terminal-required', 'sudo-start-failed', 'sudo-trusted-executable-required', 'swap-activation', 'swap-active-drift', 'swap-capacity', 'swap-checkpoint', 'swap-checkpoint-capacity', 'swap-checkpoint-integrity', 'swap-disk-reserve', 'swap-file-mode', 'swap-file-owner', 'swap-file-race', 'swap-filesystem', 'swap-format', 'swap-fstab-conflict', 'swap-fstab-drift', 'swap-fstab-unowned', 'swap-holes-or-size', 'swap-inventory-format', 'swap-mount', 'swap-ownership', 'swap-parent-symlink', 'swap-symlink', 'swap-target', 'symlink-directory', 'system-update-approval-required', 'target-binding', 'ubuntu-keyring-required', 'uncertain-effects-review-required', 'unexpected-active-swap', 'universe-base-source-required', 'unknown-step', 'unpinned-dependency', 'unreviewed-source', 'unsupported-bundle', 'unvalidated-candidate-not-accepted', 'update-limit-exceeded'])


def redact(value):
    value = str(value)
    value = re.sub(r'(?i)(https?://)[^\s/]*@', r'\1[REDACTED]@', value)
    value = re.sub(r'(?im)(authorization|proxy-authorization)\s*:[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*', r'\1: [REDACTED]', value)
    value = re.sub(r'(?i)\b(?:bearer\s+\S+|(?:token|password|secret|api[_-]?key)\s*[=:]\s*[^\s&]+)', '[REDACTED]', value)
    value = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AKIA[A-Z0-9]{16})\b', '[REDACTED]', value)
    value = re.sub(r'\b[A-Za-z0-9_+/=-]{32,}\b', '[REDACTED]', value)
    value = ''.join(c if c in '\n\t' or 32 <= ord(c) < 127 else '?' for c in value)
    return value.encode()[-4096:].decode(errors='replace')


class CommandError(RuntimeError):
    def __init__(self, argv, exit_code, stderr=''):
        # Never include options, URLs, arguments, credentials or SQL in reports.
        from pathlib import Path
        binary = Path(argv[0]).name
        self.command = [binary] if re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}', binary) else ['command']
        allowed = {'apt-get': {'update','install'}, 'apt-cache': {'policy','show'},
                   'npm': {'ci','install'}, 'systemctl': {'enable','reload','is-active'},
                   'cloud-init': {'status'}}
        self.command += [a for a in argv[1:] if a in allowed.get(binary, set())][:1]
        self.exit_code = exit_code
        self.stderr_tail = redact(stderr)
        super().__init__('command-timeout' if exit_code == 124 else 'command-failed')


class WorkflowError(RuntimeError):
    def __init__(self, metadata, diagnostic_path=None, directory=None):
        self.metadata = metadata
        self.directory = str(directory) if directory else None
        self.diagnostic_path = str(diagnostic_path) if diagnostic_path else None
        super().__init__('action-failed-see-private-journal')


def failure_metadata(step, error):
    code = 'action-failed'
    if isinstance(error, CommandError): code = error.args[0]
    elif isinstance(error, ValueError) and error.args and str(error.args[0]) in PUBLIC_FAILURE_CODES:
        code = error.args[0]
    result = {'step': step, 'code': code}
    if isinstance(error, CommandError):
        result.update(command=error.command, exit_code=error.exit_code)
    return result
