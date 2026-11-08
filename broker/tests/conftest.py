"""Shared fixtures: a fake ncl socket server replaying frames captured from the live host.

The fake speaks NanoClaw's protocol as deployed (479a9510, src/cli/socket-server.ts): read one
line, answer one line, close. It records every frame it receives so tests can assert exactly what
the broker sent, and counts how many calls are in flight at once.
"""

import asyncio
import contextlib
import io
import json
import shutil
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from nanoclaw_broker.events import EventLog
from nanoclaw_broker.server import Broker, BrokerConfig

FIXTURES = Path(__file__).parent / "fixtures"

Reply = dict[str, Any]
Responder = Callable[[dict[str, Any]], Awaitable[bytes | None]]


def load_frames() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "ncl_frames.json").read_text())
    return data


def load_commands() -> list[str]:
    data: dict[str, Any] = json.loads((FIXTURES / "ncl_commands.json").read_text())
    commands: list[str] = data["commands"]
    return commands


def frame_key(command: str, args: dict[str, Any]) -> str:
    return f"{command} {json.dumps(args, sort_keys=True)}"


class FakeNcl:
    """An asyncio Unix server standing in for NanoClaw's ncl.sock."""

    def __init__(self, path: Path, entries: list[dict[str, Any]]) -> None:
        self.path = path
        self.replies: dict[str, Reply] = {
            frame_key(e["command"], e["args"]): e["reply"] for e in entries
        }
        self.frames: list[dict[str, Any]] = []
        self.delay = 0.0
        self.in_flight = 0
        self.max_in_flight = 0
        self.responder: Responder | None = None
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_unix_server(self._handle, path=str(self.path))

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.path.unlink(missing_ok=True)

    async def restart(self) -> None:
        """Stop and start again on the same path: a new socket inode, as a NanoClaw restart."""
        await self.stop()
        await self.start()

    def calls(self, command: str | None = None) -> int:
        return sum(1 for f in self.frames if command is None or f.get("command") == command)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            line = await reader.readline()
            frame: dict[str, Any] = json.loads(line)
            self.frames.append(frame)
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.responder is not None:
                out = await self.responder(frame)
                if out is not None:
                    writer.write(out)
            else:
                writer.write(self._default_reply(frame))
            await writer.drain()
        finally:
            self.in_flight -= 1
            writer.close()

    def _default_reply(self, frame: dict[str, Any]) -> bytes:
        reply = self.replies.get(frame_key(frame["command"], frame["args"]))
        if reply is None:
            reply = {
                "ok": False,
                "error": {"code": "handler-error", "message": f"not found: {frame['command']}"},
            }
        return (json.dumps({**reply, "id": frame["id"]}) + "\n").encode()


@pytest.fixture
def short_dir() -> Iterator[Path]:
    """A short directory: macOS caps a Unix socket path at 104 bytes, and tmp_path is long."""
    d = Path(tempfile.mkdtemp(prefix="ncb-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def frames() -> dict[str, Any]:
    return load_frames()


@pytest.fixture
async def fake_ncl(short_dir: Path, frames: dict[str, Any]) -> AsyncIterator[FakeNcl]:
    fake = FakeNcl(short_dir / "ncl.sock", frames["entries"])
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


async def ask(path: Path, payload: dict[str, Any] | bytes) -> dict[str, Any]:
    """Send one request; tolerate the broker closing before we finish writing (oversize)."""
    reader, writer = await asyncio.open_unix_connection(str(path), limit=16 * 1024 * 1024)
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode() + b"\n"

    async def send() -> None:
        with contextlib.suppress(ConnectionError):
            writer.write(data)
            await writer.drain()

    sender = asyncio.create_task(send())
    line = await reader.readline()
    await sender
    writer.close()
    with contextlib.suppress(ConnectionError):
        await writer.wait_closed()
    reply: dict[str, Any] = json.loads(line)
    return reply


class Running:
    def __init__(self, broker: Broker, log: io.StringIO, path: Path) -> None:
        self.broker = broker
        self.log = log
        self.path = path

    def events(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.log.getvalue().splitlines()]


StartBroker = Callable[..., Any]


@pytest.fixture
async def start_broker(short_dir: Path, fake_ncl: FakeNcl) -> AsyncIterator[Callable[..., Any]]:
    started: list[Broker] = []

    async def _start(**overrides: Any) -> Running:
        log = io.StringIO()
        config = BrokerConfig(
            socket_path=short_dir / "broker.sock",
            ncl_socket=fake_ncl.path,
            **overrides,
        )
        broker = Broker(config, events=EventLog(log))
        await broker.start()
        started.append(broker)
        return Running(broker, log, config.socket_path)

    yield _start
    for b in started:
        await b.close()
