"""The broker's protocol, console side (docs/architecture.md §3.3, §4.3).

One connection per call: one `{"verb", "params"}` JSON line out, one `{"ok", "data" | "error"}`
line back, then the broker closes. A fresh connection each time picks up a recreated socket.
Errors carry a code only; the broker's message text is never passed on.
"""

import asyncio
import json
import re
from collections.abc import Mapping
from pathlib import Path

DEFAULT_TIMEOUT = 30.0  # the broker gives up at 25 s itself
DEFAULT_MAX_REPLY = 16 * 1024 * 1024
DEFAULT_MAX_CONCURRENT = 4
_CODE = re.compile(r"[a-z][a-z0-9_]{0,39}")


class BrokerError(Exception):
    """A broker call that gave no data. `code` is safe to show; there is no other text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BrokerClient:
    def __init__(
        self,
        socket_path: Path,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_reply: int = DEFAULT_MAX_REPLY,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self._path = socket_path
        self._timeout = timeout
        self._max_reply = max_reply
        self._slots = asyncio.Semaphore(max_concurrent)

    async def call(self, verb: str, params: Mapping[str, str] | None = None) -> object:
        """The verb's `data`, or `BrokerError` with a code."""
        request = json.dumps({"verb": verb, "params": dict(params or {})}).encode() + b"\n"
        async with self._slots:
            try:
                async with asyncio.timeout(self._timeout):
                    line = await self._exchange(request)
            except TimeoutError:
                raise BrokerError("timeout") from None
        return _parse(line)

    async def _exchange(self, request: bytes) -> bytes:
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(self._path), limit=self._max_reply
            )
        except OSError:
            raise BrokerError("unavailable") from None
        try:
            writer.write(request)
            await writer.drain()
            return await reader.readuntil(b"\n")
        except asyncio.LimitOverrunError:
            raise BrokerError("protocol_error") from None
        except asyncio.IncompleteReadError as exc:
            # Closed without a full line: nothing at all means the broker went away.
            raise BrokerError("unavailable" if not exc.partial else "protocol_error") from None
        except OSError:
            raise BrokerError("unavailable") from None
        finally:
            writer.close()


def _parse(line: bytes) -> object:
    try:
        reply: object = json.loads(line)
    except (UnicodeDecodeError, ValueError):
        raise BrokerError("protocol_error") from None
    if not isinstance(reply, dict) or not isinstance(reply.get("ok"), bool):
        raise BrokerError("protocol_error")
    if reply["ok"]:
        if "data" not in reply:
            raise BrokerError("protocol_error")
        return reply["data"]
    error = reply.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    raise BrokerError(code if isinstance(code, str) and _CODE.fullmatch(code) else "unknown")
