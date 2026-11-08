"""Client for NanoClaw's control socket, data/ncl.sock (docs/architecture.md §3.2).

One request per connection, as NanoClaw's own client does (src/cli/socket-client.ts): connect,
write one `{"id", "command", "args"}` line, read one line, close. A fresh connection per call means
a socket recreated by a NanoClaw restart is picked up with no reconnect logic.

The client never half-closes its side after writing. NanoClaw's server is a Node `net.Server`
with the default `allowHalfOpen: false`, which ends the connection on the client's FIN, before
the asynchronous dispatch has replied.
"""

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path

from .errors import NclError, NclProtocolError, NclTimeout, NclUnavailable

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_REPLY = 8 * 1024 * 1024


class NclClient:
    def __init__(
        self,
        path: Path,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_reply: int = DEFAULT_MAX_REPLY,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._path = path
        self._timeout = timeout
        self._max_reply = max_reply
        self._id_factory = id_factory

    async def call(self, command: str, args: Mapping[str, object]) -> object:
        """Send one frame and return its `data`; never the server-rendered `human` text."""
        request_id = self._id_factory()
        # json.dumps escapes newlines inside strings, so the frame is always exactly one line.
        line = json.dumps({"id": request_id, "command": command, "args": dict(args)}) + "\n"
        try:
            async with asyncio.timeout(self._timeout):
                raw = await self._exchange(line.encode())
        except TimeoutError:
            raise NclTimeout(f"ncl did not answer within {self._timeout:g} s") from None
        return _parse_reply(raw, request_id)

    async def _exchange(self, request: bytes) -> bytes:
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(self._path), limit=self._max_reply
            )
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise NclUnavailable(
                f"ncl socket not accepting connections ({type(exc).__name__})"
            ) from None
        except OSError as exc:
            raise NclUnavailable(f"ncl socket cannot be opened ({type(exc).__name__})") from None
        try:
            writer.write(request)
            await writer.drain()
            return await reader.readuntil(b"\n")
        except asyncio.LimitOverrunError:
            raise NclProtocolError(f"ncl reply too large (over {self._max_reply} bytes)") from None
        except asyncio.IncompleteReadError:
            raise NclProtocolError("ncl closed the connection without a complete reply") from None
        except ConnectionError as exc:
            raise NclProtocolError(f"ncl connection failed ({type(exc).__name__})") from None
        finally:
            writer.close()


def _parse_reply(raw: bytes, request_id: str) -> object:
    try:
        frame = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NclProtocolError("ncl reply is not JSON") from None
    if not isinstance(frame, dict) or not isinstance(frame.get("ok"), bool):
        raise NclProtocolError("ncl reply is not a frame")
    if frame["ok"] is False:
        error = frame.get("error")
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not isinstance(error.get("message"), str)
        ):
            raise NclProtocolError("ncl error reply has no code and message")
        # A frame NanoClaw could not parse is answered with id "unknown" (socket-server.ts:112-119).
        if frame.get("id") not in (request_id, "unknown"):
            raise NclProtocolError("ncl reply is for another request")
        raise NclError(error["code"], error["message"])
    if frame.get("id") != request_id:
        raise NclProtocolError("ncl reply is for another request")
    if "data" not in frame:
        raise NclProtocolError("ncl reply has no data")
    return frame["data"]
