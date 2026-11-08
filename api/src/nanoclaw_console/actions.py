"""The four actions (docs/architecture.md §4.8): pause, resume and run a task; restart a group.

Each is a `POST` the console's own page makes, and nothing else can: past the Access check (every
route has it), a request must carry a JSON body that is exactly `{}`, `Content-Type:
application/json`, `X-Console-Action: 1`, `Origin` equal to `CONSOLE_ORIGIN`, and `Sec-Fetch-Site:
same-origin`. A cross-site form cannot set the header or the JSON type without a CORS preflight
the console never answers, and a browser always sends the real Origin and Sec-Fetch-Site.

Every attempt that passed the Access check is audited (§4.9), refusals included. The audit file is
opened before the broker is asked: if it cannot be, the action is refused with 503 and nothing is
sent. The broker is asked only for the action's own verb with the id; the console never takes a
verb, a flag or any other value from the request.
"""

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from .audit import AuditLog, AuditUnavailable, AuditWriter
from .broker_client import BrokerClient, BrokerError
from .schedule import iso

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,79}")
_CF_RAY = re.compile(r"[0-9A-Za-z-]{1,64}")
MAX_BODY = 1024
NO_STORE = {"Cache-Control": "no-store"}
_FACT_CHARS = 200  # how much of a refused request's Origin and the like is written down


@dataclass(frozen=True)
class Action:
    name: str
    verb: str
    target: str  # "task" or "group"
    detail: tuple[str, ...]  # the fields of the broker's answer the console passes on


ACTIONS: Mapping[tuple[str, str], Action] = {
    ("task", "pause"): Action("pause", "tasks-pause", "task", ("touched",)),
    ("task", "resume"): Action("resume", "tasks-resume", "task", ("touched",)),
    ("task", "run"): Action("run", "tasks-run", "task", ("row_id",)),
    ("group", "restart"): Action("restart", "groups-restart", "group", ("restarted",)),
}
DETAIL_FIELDS = frozenset(f for a in ACTIONS.values() for f in a.detail)

# The broker's typed answers to a write (architecture.md §3.9) -> (HTTP status, result).
_BROKER_RESULTS = {
    "already_in_state": (200, "already_in_state"),
    "not_found": (404, "not_found"),
    "no_live_run": (409, "no_live_run"),
}


@dataclass
class _Outcome:
    status: int
    result: str
    code: str | None = None
    detail: dict[str, object] | None = None


class ActionRunner:
    def __init__(
        self,
        *,
        broker: BrokerClient,
        audit: AuditLog,
        origin: str,
        clock: Callable[[], datetime],
    ) -> None:
        self._broker = broker
        self._audit = audit
        self._origin = origin
        self._clock = clock
        self._busy: set[tuple[str, str]] = set()
        # Busy keys whose request was cancelled while the shielded broker call still runs: they
        # stay busy until that call finishes, so a retry cannot overlap it.
        self._settling: set[tuple[str, str]] = set()

    async def handle(self, request: Request, action: Action, target_id: str) -> JSONResponse:
        valid_id = ID_PATTERN.fullmatch(target_id) is not None
        entry: dict[str, Any] = {
            "at": iso(self._clock()),
            "email": getattr(request.state, "access_email", None),
            "action": action.name,
            "verb": action.verb,
            "target": {"type": action.target, "id": target_id if valid_id else None},
            "result": None,
            "reason": None,
            "code": None,
            "detail": None,
            "cf_ray": _cf_ray(request),
        }

        reason = _header_refusal(request, self._origin) or await _body_refusal(request)
        if reason is None and not valid_id:
            reason = "bad_id"
        if reason is not None:
            entry.update(result="refused", reason=reason, request=_request_facts(request))
            self._audit_refusal(entry)
            return _answer(
                404 if reason == "bad_id" else 403, {"result": "refused", "reason": reason}
            )

        key = (action.verb, target_id)
        if key in self._busy:  # checked and taken with no await between: atomic on one loop
            entry.update(result="busy")
            self._audit_refusal(entry)
            return _answer(409, self._body(entry))
        self._busy.add(key)
        try:
            return await self._act(action, target_id, entry, key)
        finally:
            if key not in self._settling:
                self._busy.discard(key)

    async def _act(
        self, action: Action, target_id: str, entry: dict[str, Any], key: tuple[str, str]
    ) -> JSONResponse:
        try:
            writer = self._audit.open()
        except AuditUnavailable:
            entry.update(result="audit_unavailable")
            self._audit.echo(entry)
            logger.error("Audit log %s cannot be written; action refused", self._audit.path)
            return _answer(503, self._body(entry))
        with writer:
            # Shielded: a client that hangs up cancels this handler, not the broker call, so an
            # action the broker has started always ends in an audit line with what came of it.
            call = asyncio.ensure_future(self._call(action, target_id))
            try:
                outcome = await asyncio.shield(call)
            except asyncio.CancelledError:
                entry.update(result="interrupted")
                self._write_or_log(writer, entry)
                self._settling.add(key)
                call.add_done_callback(lambda done: self._record_late(entry, done, key))
                raise
            except Exception as exc:
                # The type name only: an exception's message may carry anything.
                entry.update(result="error", code=type(exc).__name__)
                self._write_or_log(writer, entry)
                raise
            entry.update(result=outcome.result, code=outcome.code, detail=outcome.detail)
            try:
                writer.write(entry)
            except OSError:
                # The broker has answered (it may have acted), and the line is on stdout; say
                # the file missed it, with what the broker answered.
                logger.error("Audit log %s write failed after the action", self._audit.path)
                return _answer(
                    500,
                    {**self._body(entry), "result": "audit_failed", "acted_result": outcome.result},
                )
        return _answer(outcome.status, self._body(entry))

    async def _call(self, action: Action, target_id: str) -> _Outcome:
        if action.target == "group":
            # ncl restarts nothing and answers {restarted: 0} for any id, so make sure it exists.
            try:
                groups = await self._broker.call("groups-list")
            except BrokerError as exc:
                return _Outcome(502, "broker_error", exc.code)
            known = isinstance(groups, list) and any(
                isinstance(g, dict) and g.get("id") == target_id for g in groups
            )
            if not known:
                return _Outcome(404, "not_found")
        try:
            data = await self._broker.call(action.verb, {"id": target_id})
        except BrokerError as exc:
            if exc.code in _BROKER_RESULTS:
                status, result = _BROKER_RESULTS[exc.code]
                return _Outcome(status, result)
            return _Outcome(502, "broker_error", exc.code)
        return _Outcome(200, "done", detail=_detail(action, data))

    def _write_or_log(self, writer: AuditWriter, entry: Mapping[str, Any]) -> None:
        """On the way out of a failed call: the line if the file takes it, else a log line."""
        try:
            writer.write(entry)
        except OSError:
            logger.error("Audit log %s write failed after an interrupted action", self._audit.path)

    def _record_late(
        self, entry: Mapping[str, Any], done: "asyncio.Future[_Outcome]", key: tuple[str, str]
    ) -> None:
        """The outcome of a broker call whose request was cancelled, as a second line."""
        self._settling.discard(key)
        self._busy.discard(key)
        late = dict(entry)
        if done.cancelled():
            late.update(result="interrupted")
        elif (exc := done.exception()) is not None:
            late.update(result="error", code=type(exc).__name__)
        else:
            outcome = done.result()
            late.update(result=outcome.result, code=outcome.code, detail=outcome.detail)
        self._audit_refusal(late)

    def _audit_refusal(self, entry: dict[str, Any]) -> None:
        """A refusal is written down if it can be; it acted on nothing, so it never waits on it."""
        try:
            with self._audit.open() as writer:
                writer.write(entry)
        except AuditUnavailable:
            self._audit.echo(entry)
        except OSError:
            logger.error("Audit log %s write failed for a refusal", self._audit.path)

    @staticmethod
    def _body(entry: Mapping[str, Any]) -> dict[str, object]:
        return {
            "result": entry["result"],
            "code": entry["code"],
            "action": entry["action"],
            "target": entry["target"],
            "at": entry["at"],
            "detail": entry["detail"],
        }


def _answer(status: int, body: Mapping[str, object]) -> JSONResponse:
    return JSONResponse(dict(body), status_code=status, headers=NO_STORE)


def _header_refusal(request: Request, origin: str) -> str | None:
    headers = request.headers
    if headers.get("x-console-action") != "1":
        return "action_header"
    if headers.get("origin") != origin:
        return "origin"
    if headers.get("sec-fetch-site") != "same-origin":
        return "fetch_site"
    media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media != "application/json":
        return "content_type"
    return None


async def _body_refusal(request: Request) -> str | None:
    """`body` unless the body is exactly `{}`. At most MAX_BODY bytes are ever held: a declared
    length over it is refused unread, and a chunked body stops being read once it passes it."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if not 0 <= int(declared) <= MAX_BODY:
                return "body"
        except ValueError:
            return "body"
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            return "body"
    try:
        value = json.loads(bytes(body))
    except (UnicodeDecodeError, ValueError):
        return "body"
    if value != {}:
        return "body"
    return None


def _detail(action: Action, data: object) -> dict[str, object] | None:
    """The fields of the broker's answer this action shows, by name; a field of another type is
    dropped, so nothing the broker failed to redact can ride along."""
    if not isinstance(data, dict):
        return None
    return {name: data[name] for name in action.detail if _plain(data.get(name))}


def _plain(value: object) -> bool:
    """A count, or an id: the only values an action's detail carries."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, str) and bool(ID_PATTERN.fullmatch(value)))


def _cf_ray(request: Request) -> str | None:
    value = request.headers.get("cf-ray")
    return value if value is not None and _CF_RAY.fullmatch(value) else None


def _request_facts(request: Request) -> dict[str, str | None]:
    """For a refusal: what the request said about where it came from, cut short."""
    facts: dict[str, str | None] = {}
    for name in ("origin", "sec-fetch-site", "content-type", "x-console-action"):
        value = request.headers.get(name)
        facts[name.replace("-", "_")] = value[:_FACT_CHARS] if value is not None else None
    return facts


def audit_view(log: AuditLog, now: datetime) -> dict[str, object]:
    """`GET /api/audit`: the recent entries, newest first, each shaped field by field."""
    recent = log.recent()
    return {
        "generated_at": iso(now),
        "available": recent.available,
        "writable": log.writable() if recent.available else False,
        "truncated": recent.truncated,
        "entries": [_shape(e) for e in recent.entries],
    }


def _text(value: object) -> str | None:
    return value[:_FACT_CHARS] if isinstance(value, str) else None


def _shape(entry: Mapping[str, Any]) -> dict[str, object]:
    target = entry.get("target")
    target = target if isinstance(target, dict) else {}
    detail = entry.get("detail")
    shaped_detail = (
        {k: v for k, v in detail.items() if k in DETAIL_FIELDS and _plain(v)}
        if isinstance(detail, dict)
        else None
    )
    return {
        "at": _text(entry.get("at")),
        "email": _text(entry.get("email")),
        "action": _text(entry.get("action")),
        "target": {"type": _text(target.get("type")), "id": _text(target.get("id"))},
        "result": _text(entry.get("result")),
        "reason": _text(entry.get("reason")),
        "code": _text(entry.get("code")),
        "detail": shaped_detail,
        "cf_ray": _text(entry.get("cf_ray")),
    }
