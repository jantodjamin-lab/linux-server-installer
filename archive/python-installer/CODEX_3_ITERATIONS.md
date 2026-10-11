> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# Universal Linux Installer V1 — Codex implementation contract

Status: DEVELOPMENT. This branch does not authorize execution on TEST-O or production.

## Goal
Build a generic, locally executed, manually launched Ubuntu Linux installer with three roles: APP, DB, APP+DB. No remote SSH execution, remote provisioning, or automated host management.

## Safety
- Never modify the archived ramin-platform repository.
- Do not install, upgrade or reconfigure APP-O while developing; work only in repository and offline isolated tests.
- No secrets or private SSH keys in public GitHub; separate public distribution repository only after security review.
- Default dry-run, explicit confirmation for changes, never silently alter existing databases, firewall, SSH, users, or services.
- Pin dependencies and release artifacts; verify checksums; no curl-to-shell from mutable main.
- Ubuntu 26.04 support must be verified for each dependency; unsupported configurations fail safely.
- Do not create public repo or publish artifacts without explicit review.
- Commit after each iteration, report PASS/WARN/FAIL and commit SHA.

## Iteration 1 — structure and audit
Inspect existing repository and historical references read-only. Implement modular CLI, profile manifest, OS/preflight and package inventory, audit/dry-run, log and JSON report, idempotence contracts, unit tests.

## Iteration 2 — implementation
Implement role-specific package installation (Git, Python, .NET 10, Node/Angular, Nginx, PostgreSQL 18, optional development-only Codex), package source verification, update/reboot handling, checkpoints and recovery, validators and security tests. Avoid destructive rollback and secret leakage.

## Iteration 3 — release readiness
Run static analysis, unit/integration tests in isolated disposable environment, all profiles, negative and interrupted runs, clean re-run, security review, operator runbook, release manifest, versioned archive, checksums. Prepare candidate v1.0.0; no live TEST-O run or public publication.

## Deliverables
installer/README.md; installer/install.sh; installer/lib/; installer/profiles/; installer/tests/; installer/docs/; installer/release/ (as applicable). Keep existing application functionality untouched.

## Gate
No GO for TEST-O until owner confirms fresh snapshot and explicitly approves manual installation.
