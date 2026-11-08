"""A fake broker on a real Unix socket, replaying `fixtures/broker_replies.json`.

It speaks the broker's protocol (docs/architecture.md §3.3): one JSON line in, one line out, then
close. It runs in its own thread (the app under test runs on TestClient's event loop), records
every request, and can be told to fail a verb, delay, answer garbage or stay silent.
"""

import json
import socketserver
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"


def load_replies() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "broker_replies.json").read_text())
    replies: dict[str, Any] = data["replies"]
    return replies


def reply_key(verb: str, params: dict[str, Any] | None) -> str:
    return verb + (" " + json.dumps(params, sort_keys=True) if params else "")


# A raw answer: bytes written as is (None: close without answering).
RawResponder = Callable[[dict[str, Any]], bytes | None]


class FakeBroker:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.replies: dict[str, Any] = load_replies()
        self.errors: dict[str, str] = {}  # verb -> error code
        self.requests: list[dict[str, Any]] = []
        self.delay = 0.0
        self.raw: RawResponder | None = None
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()
        self._server: socketserver.ThreadingUnixStreamServer | None = None
        self._thread: threading.Thread | None = None

    # -- scripting ------------------------------------------------------------------------------

    def set(self, verb: str, data: Any, params: dict[str, str] | None = None) -> None:
        self.replies[reply_key(verb, params)] = data

    def data(self, verb: str, params: dict[str, str] | None = None) -> Any:
        return self.replies[reply_key(verb, params)]

    def fail(self, verb: str, code: str = "unavailable") -> None:
        self.errors[verb] = code

    def verbs(self) -> list[str]:
        return [r.get("verb", "") for r in self.requests]

    # -- server ---------------------------------------------------------------------------------

    def start(self) -> None:
        fake = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                fake._handle(self)

        self._server = socketserver.ThreadingUnixStreamServer(str(self.path), Handler)
        self._server.daemon_threads = True
        server = self._server
        self._thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self.path.unlink(missing_ok=True)

    def _handle(self, conn: socketserver.StreamRequestHandler) -> None:
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            line = conn.rfile.readline()
            request: dict[str, Any] = json.loads(line)
            with self._lock:
                self.requests.append(request)
            if self.delay:
                time.sleep(self.delay)
            if self.raw is not None:
                out = self.raw(request)
            else:
                out = (json.dumps(self._answer(request)) + "\n").encode()
            if out is not None:
                conn.wfile.write(out)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client gave up first (the timeout tests)
        finally:
            with self._lock:
                self.in_flight -= 1

    def _answer(self, request: dict[str, Any]) -> dict[str, Any]:
        verb = request.get("verb", "")
        if verb in self.errors:
            code = self.errors[verb]
            return {"ok": False, "error": {"code": code, "message": f"fake {code}"}}
        key = reply_key(verb, request.get("params"))
        if key not in self.replies:
            if any(k.split(" ", 1)[0] == verb for k in self.replies):
                message = "ncl rejected the request (not-found)"
                return {"ok": False, "error": {"code": "ncl_error", "message": message}}
            return {"ok": False, "error": {"code": "unknown_verb", "message": "unknown verb"}}
        return {"ok": True, "data": self.replies[key]}
