"""The verb registry: the broker's security boundary (docs/architecture.md §3.3-3.4).

A client names a verb from this registry and passes only its id parameters. The broker builds the
ncl frame from the registry entry: the ncl command name and any fixed args are constants here, so
a client can never choose the command, add a flag or reach ncl's dash-prefix fallback.

The reads: 15 ncl reads, `usage` (an ncl read whose text is parsed) and four reads that are not
ncl commands (`LOCAL_VERBS`: health, mount-allowlist, task-file, claude-probe).

The writes (decision D4, release 2): exactly `tasks-pause`, `tasks-resume`, `tasks-run` and
`groups-restart`, each with `params=("id",)`, `cacheable=False` and no fixed args, so ncl's
`--rebuild`, `--message`, `--group` and `--session` can never be sent. Nothing else is ever added
here: creating or editing tasks, grants, mounts and the rest stay in `ncl`.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import BrokerError
from .redact import redact_group_config, redact_reply
from .usage import parse_usage

# Every parameter is an id. [0-9] and [A-Za-z] are ASCII-only (unlike \d and \w), fullmatch has
# no trailing-newline loophole (unlike $), and an id cannot start with "-".
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,79}")

_NO_ARGS: Mapping[str, object] = MappingProxyType({})


@dataclass(frozen=True)
class Verb:
    name: str
    command: str
    params: tuple[str, ...] = ()
    fixed_args: Mapping[str, object] = field(default=_NO_ARGS)
    redactor: Callable[[object], object] = redact_reply
    cacheable: bool = True
    ttl: float | None = None  # seconds; None means the cache default
    write: bool = False
    # A write only: the cached reads (verb names) it can change, dropped after it runs.
    invalidates: tuple[str, ...] = ()
    # A write only: the status a repeat finds the task already in ("no live task matched").
    settles_to: str | None = None

    def build_args(self, params: Mapping[str, str]) -> dict[str, object]:
        """The frame's `args`: the fixed args, then the validated ids. Always a fresh dict."""
        args: dict[str, object] = dict(self.fixed_args)
        for name in self.params:
            args[name] = params[name]
        return args


@dataclass(frozen=True)
class LocalVerb:
    """A read that is not an ncl command: the broker does it itself (docs/architecture.md §3.8)."""

    name: str
    params: tuple[str, ...]
    ttl: float


def _verb(
    name: str,
    *params: str,
    fixed_args: Mapping[str, object] | None = None,
    redactor: Callable[[object], object] = redact_reply,
    ttl: float | None = None,
) -> tuple[str, Verb]:
    """A read verb whose broker name is its ncl command name."""
    return name, Verb(
        name=name,
        command=name,
        params=params,
        fixed_args=MappingProxyType(dict(fixed_args)) if fixed_args else _NO_ARGS,
        redactor=redactor,
        ttl=ttl,
    )


_TASK_READS = ("tasks-list", "tasks-get", "health")  # health carries the task counts
_SESSION_READS = ("sessions-list", "health")


def _write(
    name: str, invalidates: tuple[str, ...], settles_to: str | None = None
) -> tuple[str, Verb]:
    """One of D4's four writes: its ncl command name, the id only, never cached."""
    return name, Verb(
        name=name,
        command=name,
        params=("id",),
        cacheable=False,
        write=True,
        invalidates=invalidates,
        settles_to=settles_to,
    )


REGISTRY: Mapping[str, Verb] = MappingProxyType(
    dict(
        [
            _verb("groups-list"),
            _verb("groups-get", "id"),
            _verb("groups-config-get", "id", redactor=redact_group_config),
            _verb("messaging-groups-list"),
            _verb("wirings-list"),
            _verb("destinations-list"),
            _verb("sessions-list"),
            # `--all` is the host default already (tasks.ts:448-450); sent for explicitness.
            _verb("tasks-list", fixed_args={"all": True}),
            _verb("tasks-get", "id"),
            _verb("roles-list"),
            _verb("members-list"),
            _verb("policies-list"),
            _verb("approvals-list"),
            _verb("users-list"),
            _verb("dropped-messages-list"),
            # ncl returns the quota as rendered text; the redactor parses it into fields.
            _verb("usage", redactor=parse_usage, ttl=300.0),
            # Release 2 (D4). The id is a task's series id, or an agent group's id.
            _write("tasks-pause", _TASK_READS, settles_to="paused"),
            _write("tasks-resume", _TASK_READS, settles_to="pending"),
            _write("tasks-run", _TASK_READS),
            _write("groups-restart", _SESSION_READS),
        ]
    )
)

LOCAL_VERBS: Mapping[str, LocalVerb] = MappingProxyType(
    {
        verb.name: verb
        for verb in (
            LocalVerb("health", (), 60.0),
            LocalVerb("mount-allowlist", (), 60.0),
            LocalVerb("task-file", ("id",), 20.0),  # id = the task's series id
            LocalVerb("claude-probe", (), 300.0),
        )
    }
)


def resolve(verb: object, params: object) -> tuple[Verb | LocalVerb, dict[str, str]]:
    """Look up a verb and validate its params; raise `unknown_verb` or `invalid_params`.

    Error messages never echo the client's values.
    """
    if not isinstance(verb, str):
        raise BrokerError("unknown_verb", "unknown verb")
    entry: Verb | LocalVerb
    if verb in REGISTRY:
        entry = REGISTRY[verb]
    elif verb in LOCAL_VERBS:
        entry = LOCAL_VERBS[verb]
    else:
        raise BrokerError("unknown_verb", "unknown verb")
    if not isinstance(params, dict):
        raise BrokerError("invalid_params", "params must be an object")
    expected = set(entry.params)
    given = set(params)
    if given != expected:
        want = ", ".join(entry.params) or "none"
        raise BrokerError("invalid_params", f"{verb} takes exactly these params: {want}")
    validated: dict[str, str] = {}
    for name in entry.params:
        value = params[name]
        if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
            raise BrokerError(
                "invalid_params", f"{name} must match {ID_PATTERN.pattern} (an id, 1-80 chars)"
            )
        validated[name] = value
    return entry, validated
