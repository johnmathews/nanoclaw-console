"""The broker's Unix socket server (docs/architecture.md §3.3, §3.7).

One JSON line in (`{"verb", "params"}`), one JSON line out (`{"ok": true, "data"}` or
`{"ok": false, "error": {"code", "message"}}`), then the connection is closed.
"""

import asyncio
import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from .cache import ReadCache
from .errors import BrokerError
from .events import EventLog
from .ncl_client import DEFAULT_MAX_REPLY, DEFAULT_TIMEOUT, NclClient
from .verbs import REGISTRY, Verb, resolve

MAX_REQUEST = 64 * 1024
_REQUEST_KEYS = frozenset({"verb", "params"})


@dataclass(frozen=True)
class BrokerConfig:
    socket_path: Path
    ncl_socket: Path
    socket_mode: int = 0o660
    socket_group: int | None = None
    ttl: float = 20.0
    max_inflight: int = 2
    ncl_timeout: float = DEFAULT_TIMEOUT
    request_deadline: float = 25.0
    read_timeout: float = 5.0
    max_request: int = MAX_REQUEST
    max_reply: int = DEFAULT_MAX_REPLY


@dataclass
class _Outcome:
    """What one request did, for its log line. Holds names and ids only, never data."""

    verb: str | None = None
    params: dict[str, str] | None = None
    cache: str | None = None
    outcome: str = "ok"
    error: str | None = None


class Broker:
    def __init__(self, config: BrokerConfig, *, events: EventLog | None = None) -> None:
        self._config = config
        self._events = events or EventLog()
        self._client = NclClient(
            config.ncl_socket, timeout=config.ncl_timeout, max_reply=config.max_reply
        )
        self._cache = ReadCache(ttl=config.ttl, max_inflight=config.max_inflight)
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        path = self._config.socket_path
        _remove_stale_socket(path)
        # Bind with umask 0177 so the socket is never wider than 0600 before chmod below.
        old_umask = os.umask(0o177)
        try:
            self._server = await asyncio.start_unix_server(
                self._handle, path=str(path), limit=self._config.max_request
            )
        finally:
            os.umask(old_umask)
        if self._config.socket_group is not None:
            os.chown(path, -1, self._config.socket_group)
        os.chmod(path, self._config.socket_mode)
        self._events.emit(
            "listening",
            socket=str(path),
            ncl_socket=str(self._config.ncl_socket),
            mode=oct(self._config.socket_mode),
            group=self._config.socket_group,
        )

    async def close(self) -> None:
        if self._server is None:
            return
        server, self._server = self._server, None
        server.close()
        await server.wait_closed()
        self._config.socket_path.unlink(missing_ok=True)
        self._events.emit("stopped")

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        started = time.monotonic()
        result = _Outcome()
        try:
            reply = await self._serve_one(reader, result)
        except BrokerError as exc:
            result.outcome = exc.code
            reply = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
        except Exception as exc:  # the client gets a bare "internal", the log the type name
            result.outcome = "internal"
            result.error = type(exc).__name__
            reply = {"ok": False, "error": {"code": "internal", "message": "internal error"}}
        try:
            writer.write(json.dumps(reply).encode() + b"\n")
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()
        self._events.emit(
            "request",
            verb=result.verb,
            params=result.params,
            cache=result.cache,
            outcome=result.outcome,
            error=result.error,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )

    async def _serve_one(self, reader: asyncio.StreamReader, result: _Outcome) -> dict[str, object]:
        request = await self._read_request(reader)
        raw_verb = request.get("verb")
        if isinstance(raw_verb, str) and raw_verb in REGISTRY:
            result.verb = raw_verb  # a registry name, never a client-made string
        verb, params = resolve(raw_verb, request.get("params", {}))
        result.verb = verb.name
        result.params = params
        try:
            async with asyncio.timeout(self._config.request_deadline):
                data, result.cache = await self._fetch(verb, params)
        except TimeoutError:
            raise BrokerError(
                "timeout", f"no answer within {self._config.request_deadline:g} s"
            ) from None
        return {"ok": True, "data": data}

    async def _read_request(self, reader: asyncio.StreamReader) -> dict[str, object]:
        try:
            async with asyncio.timeout(self._config.read_timeout):
                line = await reader.readuntil(b"\n")
        except asyncio.LimitOverrunError:
            raise BrokerError(
                "request_too_large", f"requests are capped at {self._config.max_request} bytes"
            ) from None
        except asyncio.IncompleteReadError as exc:
            line = exc.partial  # the client closed its side without a newline
        except TimeoutError:
            raise BrokerError("bad_request", "request not received in time") from None
        if not line.strip():
            raise BrokerError("bad_request", "empty request")
        try:
            request = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BrokerError("bad_request", "request is not one JSON object") from None
        if not isinstance(request, dict) or "verb" not in request:
            raise BrokerError("bad_request", 'request must be {"verb": ..., "params": {...}}')
        if not set(request) <= _REQUEST_KEYS:
            raise BrokerError("bad_request", "request may contain only verb and params")
        return request

    async def _fetch(self, verb: Verb, params: dict[str, str]) -> tuple[object, str]:
        async def load() -> object:
            data = await self._client.call(verb.command, verb.build_args(params))
            return verb.redactor(data)

        if not verb.cacheable:
            return await self._cache.run_uncached(load), "none"
        key = (verb.name, tuple(sorted(params.items())))
        return await self._cache.get(key, load)


def _remove_stale_socket(path: Path) -> None:
    """Remove a socket left by an earlier run; refuse to touch any other kind of file."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(mode):
        raise FileExistsError(f"refusing to replace {path}: it exists and is not a socket")
    path.unlink()


async def serve(
    config: BrokerConfig, stop: asyncio.Event, *, events: EventLog | None = None
) -> None:
    """Run the broker until `stop` is set, then close it and remove its socket."""
    broker = Broker(config, events=events)
    await broker.start()
    try:
        await stop.wait()
    finally:
        await broker.close()
