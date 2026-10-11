"""Typed WP-003 offline model. No I/O, commands, privilege or live adapter."""
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import PurePosixPath


class Stop(ValueError):
    """Uncertain/unsupported state requires human review; never retry."""


class Action(Enum):
    BACKUP_FSTAB = 'backup-fstab'
    CREATE_FILE = 'create-exclusive-file'
    SET_OWNER_MODE = 'root-root-0600'
    FORMAT = 'format-swap'
    REGISTER = 'append-exact-fstab-entry'
    ACTIVATE = 'activate-swap'


@dataclass(frozen=True)
class Plan:
    path: str
    size_bytes: int
    active_bytes: int  # reviewed usable size; header overhead is not normalized
    reserve_bytes: int
    fstab_before: str
    release: str

    def __post_init__(self):
        if (not isinstance(self.path, str) or not self.path.startswith('/') or
                str(PurePosixPath(self.path)) != self.path or
                any(c.isspace() for c in self.path) or '..' in PurePosixPath(self.path).parts or
                self.path in ('/', '/etc/fstab') or
                any(type(x) is not int for x in (self.size_bytes, self.active_bytes, self.reserve_bytes)) or
                not 0 < self.active_bytes <= self.size_bytes or self.reserve_bytes < 0 or
                not isinstance(self.fstab_before, str) or not self.release):
            raise Stop('Incomplete/invalid reviewed plan')
        if self.fstab_before and not self.fstab_before.endswith('\n'):
            raise Stop('Unreviewed fstab line boundary')
        for line in self.fstab_before.splitlines():
            fields = line.split('#', 1)[0].split()
            if self.path in fields or (len(fields) >= 3 and fields[2] == 'swap'):
                raise Stop('Existing swap/fstab collision')

    @property
    def fstab_after(self):
        return self.fstab_before + f'{self.path} none swap sw 0 0\n'


@dataclass(frozen=True)
class Observation:
    identity: tuple  # host, hostkey, provider, generation, machine-id, boot-id
    observed_at: int  # fictive monotonic seconds within one run
    complete: bool
    preflight: str
    compatible: bool  # reviewed filesystem/mount/symlink/hardlink checks
    free_bytes: int
    fstab: str
    file_bytes: int
    uid: int
    gid: int
    mode: int
    active: tuple  # ((path, usable_bytes), ...), all swap devices
    backup: str | None
    unchanged: tuple  # reviewed non-swap config, services, sockets, ports, versions


@dataclass(frozen=True)
class Context:
    identity: tuple
    now: int
    max_age: int
    human_present: bool
    go_reference: str  # fictive record only; never grants authorization


def conditions(plan: Plan, state: Observation, context: Context):
    if (len(context.identity) != 6 or not all(context.identity) or
            state.identity != context.identity or state.complete is not True or
            state.preflight != 'PASS' or state.compatible is not True or
            context.human_present is not True or not context.go_reference or
            type(context.max_age) is not int or context.max_age <= 0 or
            not 0 <= context.now - state.observed_at <= context.max_age or
            any(type(x) is not int or x < 0 for x in
                (state.free_bytes, state.file_bytes, state.uid, state.gid, state.mode))):
        raise Stop('Identity/freshness/inventory/privilege STOP')
    if (state.file_bytes == plan.size_bytes and state.uid == state.gid == 0 and
            state.mode == 0o600 and state.active == ((plan.path, plan.active_bytes),) and
            state.fstab == plan.fstab_after and state.backup == plan.fstab_before):
        return ()
    if (state.file_bytes != 0 or state.active or state.fstab != plan.fstab_before or
            state.backup is not None or state.free_bytes < plan.size_bytes + plan.reserve_bytes):
        raise Stop('Collision/drift/partial state/insufficient space STOP')
    return tuple(Action)


def simulate(plan: Plan, state: Observation, context: Context):
    """Pure fictional transition, deliberately no executor callback."""
    actions = conditions(plan, state, context)
    if not actions:
        return state, actions
    return replace(state, free_bytes=state.free_bytes-plan.size_bytes,
                   file_bytes=plan.size_bytes, uid=0, gid=0, mode=0o600,
                   active=((plan.path, plan.active_bytes),), backup=state.fstab,
                   fstab=plan.fstab_after), actions
