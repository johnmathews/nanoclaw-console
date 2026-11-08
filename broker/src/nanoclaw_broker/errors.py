"""Typed errors. Each carries the `code` the console sees (docs/architecture.md §3.3)."""

import re

from .redact import redact_text

# ncl's own error text goes to the broker's log only, redacted and cut to this length.
MAX_NCL_DETAIL = 500
_NCL_CODE = re.compile(r"[a-z][a-z0-9-]{0,39}")

# The two refusals of a task write that mean something to the console (NanoClaw 479a9510,
# src/cli/resources/tasks.ts:277 and :404). They are matched on ncl's raw text at its start and
# only classified; the text itself never leaves the broker.
_NO_LIVE_TASK = "no live task matched: "
_TASK_NOT_FOUND = "task not found: "


class BrokerError(Exception):
    """An error the broker reports to its client as `{"code", "message"}`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class NclError(BrokerError):
    """ncl answered `ok: false`.

    The client sees only `ncl_code` (ncl's own code, `handler-error`, `invalid-args`...; anything
    that is not a short kebab-case word becomes `unknown`) in a fixed sentence. ncl's free text
    is untrusted: it can repeat a secret from the request. It is kept as `detail`, redacted and
    cut, for the broker's log only, and is not part of `message` or `str(error)`.
    """

    def __init__(self, ncl_code: str, detail: str) -> None:
        safe = ncl_code if _NCL_CODE.fullmatch(ncl_code) else "unknown"
        super().__init__("ncl_error", f"ncl rejected the request ({safe})")
        self.ncl_code = safe
        self.detail = redact_text(detail)[:MAX_NCL_DETAIL]
        # What the refusal was, for the write verbs: "no_live_task", "task_not_found" or None.
        self.kind: str | None = None
        if safe == "handler-error":
            if detail.startswith(_NO_LIVE_TASK):
                self.kind = "no_live_task"
            elif detail.startswith(_TASK_NOT_FOUND):
                self.kind = "task_not_found"


class NclUnavailable(BrokerError):
    """ncl.sock is missing, refuses connections or cannot be opened: NanoClaw is down."""

    def __init__(self, message: str) -> None:
        super().__init__("unavailable", message)


class NclTimeout(BrokerError):
    """ncl did not answer in time."""

    def __init__(self, message: str) -> None:
        super().__init__("timeout", message)


class NclProtocolError(BrokerError):
    """ncl's reply was not one well-formed frame for our request."""

    def __init__(self, message: str) -> None:
        super().__init__("protocol_error", message)
