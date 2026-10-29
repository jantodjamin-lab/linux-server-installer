# Security boundaries

No changes before installation authorization. No `curl | bash`, trust bypass, database/user removal, general OS upgrade, SSH changes or firewall changes. Resume executes only the staged root-owned Bash copy and data-only state. Ambiguous ownership, package health, version or recovery stops safely.

APT command output is not persisted in installer logs; source URLs may contain credentials. Do not enable shell tracing. Logs and state are root-only. Unknown filesystem swap semantics are not guessed.

Archived scripts are inert historical evidence and must not be used for installation. No live changes on APP-O or TEST-O were authorized. Production acceptance requires all real isolated tests, independent download verification and no high/critical findings.
