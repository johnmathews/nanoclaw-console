"""`health`: NanoClaw's loopback /health, passed on as is or reported unavailable."""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from nanoclaw_broker.health import fetch_health

# Captured from NanoClaw 479a9510 on the agent host, 2026-11-08.
LIVE = {
    "uptimeSeconds": 72739,
    "channels": [{"name": "cli", "connected": True}, {"name": "slack", "connected": True}],
    "messageLoopRunning": True,
    "queue": {"active": 1, "max": 0, "waiting": 0},
    "registeredGroupCount": 15,
    "activeSessionCount": 18,
    "lastMessageTimestamp": "2026-11-08T13:37:45.983Z",
    "lastMessageAge": "39m ago",
    "tasks": {
        "activeCount": 14,
        "pausedCount": 2,
        "nextRunTime": "2026-11-08T14:22:00.000Z",
        "recentFailures": 0,
    },
    "healthy": True,
}
UNAVAILABLE = {"available": False}


class Handler(BaseHTTPRequestHandler):
    status = 200
    body: bytes = json.dumps(LIVE).encode()
    delay = 0.0
    seen: list[str] = []  # noqa: RUF012

    def do_GET(self) -> None:
        type(self).seen.append(self.path)
        if self.delay:
            threading.Event().wait(self.delay)
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def health_server() -> Iterator[tuple[int, type[Handler]]]:
    handler = type("H", (Handler,), {"seen": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield server.server_address[1], handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


async def test_the_live_shape_is_returned_as_is(health_server: tuple[int, type[Handler]]) -> None:
    port, handler = health_server
    assert await fetch_health(port) == LIVE
    assert handler.seen == ["/health"]


async def test_an_unhealthy_503_still_carries_the_data(
    health_server: tuple[int, type[Handler]],
) -> None:
    port, handler = health_server
    handler.status = 503
    handler.body = json.dumps({**LIVE, "healthy": False}).encode()
    assert await fetch_health(port) == {**LIVE, "healthy": False}


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, b'{"error": "boom Bearer PLANTED-SECRET-h"}'),
        (404, b'{"error": "Not found"}'),
        (200, b"not json"),
        (200, b"[1, 2]"),
        (200, b'"text"'),
        (200, b""),
        (200, b"\xff\xfe"),
        (200, b'{"a": "' + b"x" * (70 * 1024) + b'"}'),
    ],
)
async def test_anything_else_is_unavailable(
    health_server: tuple[int, type[Handler]], status: int, body: bytes
) -> None:
    port, handler = health_server
    handler.status = status
    handler.body = body
    assert await fetch_health(port) == UNAVAILABLE


async def test_a_closed_port_is_unavailable() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert await fetch_health(port) == UNAVAILABLE


async def test_a_slow_answer_is_unavailable(health_server: tuple[int, type[Handler]]) -> None:
    port, handler = health_server
    handler.delay = 1.0
    assert await fetch_health(port, timeout=0.2) == UNAVAILABLE


async def test_secrets_in_the_body_are_still_redacted(
    health_server: tuple[int, type[Handler]],
) -> None:
    port, handler = health_server
    handler.body = json.dumps({"healthy": True, "note": "see https://u:p@ss@h.example/x"}).encode()
    out = await fetch_health(port)
    assert out == {"healthy": True, "note": "see https://•••@h.example/x"}
