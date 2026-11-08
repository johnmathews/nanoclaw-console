"""`claude-probe`: one empty-body call to Anthropic through OneCLI (docs/architecture.md §3.8).

A fake OneCLI API hands out container-config, and a fake MITM proxy terminates TLS with a CA the
test generates with the openssl CLI (skipped where it is missing). The proxy token is planted and
must be absent from the result, the log, stdout and stderr, whatever goes wrong.
"""

import asyncio
import base64
import io
import json
import shutil
import socket
import ssl
import subprocess
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from nanoclaw_broker import probe as probe_module
from nanoclaw_broker.events import EventLog
from nanoclaw_broker.probe import ClaudeProbe

TOKEN = "PLANTED-SECRET-onecli-token-0123456789"
USER = "agentuser"
BASIC = base64.b64encode(f"{USER}:{TOKEN}".encode()).decode()
GROUP = "ag-test-probe"


class Ca:
    def __init__(self, directory: Path, name: str) -> None:
        self.cert = directory / f"{name}.pem"
        self.key = directory / f"{name}.key"
        subprocess.run(  # noqa: S603
            [  # noqa: S607
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(self.key), "-out", str(self.cert), "-days", "2",
                "-subj", f"/CN={name}",
                "-addext", "subjectAltName=DNS:api.anthropic.com",
                "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,digitalSignature,keyEncipherment",
            ],
            check=True,
            capture_output=True,
        )  # fmt: skip

    @property
    def pem(self) -> str:
        return self.cert.read_text()

    def server_context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self.cert, self.key)
        return ctx


@pytest.fixture(scope="module")
def ca(tmp_path_factory: pytest.TempPathFactory) -> Ca:
    if shutil.which("openssl") is None:
        pytest.skip("openssl CLI not available")
    try:
        return Ca(tmp_path_factory.mktemp("ca"), "good")
    except subprocess.CalledProcessError:
        pytest.skip("this openssl cannot make the test certificate")


@pytest.fixture(scope="module")
def other_ca(tmp_path_factory: pytest.TempPathFactory) -> Ca:
    if shutil.which("openssl") is None:
        pytest.skip("openssl CLI not available")
    return Ca(tmp_path_factory.mktemp("ca2"), "other")


class FakeProxy:
    """Speaks just enough of a MITM proxy: CONNECT, then (optionally) TLS and one HTTP request."""

    def __init__(self, mode: str, ca: Ca | None = None, status: int = 400) -> None:
        self.mode = mode
        self.ca = ca
        self.status = status
        self.connects: list[dict[str, str]] = []
        self.requests: list[dict[str, Any]] = []
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port: int = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=2)

    def _accept(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(3)
            try:
                head = _read_head(conn)
                lines = head.decode().split("\r\n")
                headers = dict(line.split(": ", 1) for line in lines[1:] if ": " in line)
                self.connects.append({"line": lines[0], **headers})
                self._respond(conn)
            except (OSError, ssl.SSLError):
                return

    def _respond(self, conn: socket.socket) -> None:
        if self.mode == "407":
            conn.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
        elif self.mode == "garbage":
            conn.sendall(b"HTTP/1.1 200 OK\r\n\r\nthis is not a TLS handshake")
            threading.Event().wait(0.3)
        elif self.mode == "hang":
            threading.Event().wait(2)
        else:
            assert self.ca is not None
            conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            with self.ca.server_context().wrap_socket(conn, server_side=True) as tls:
                head = _read_head(tls)
                lines = head.decode().split("\r\n")
                headers = dict(line.split(": ", 1) for line in lines[1:] if ": " in line)
                body = tls.recv(int(headers.get("Content-Length", "0"))) if headers else b""
                self.requests.append({"line": lines[0], "headers": headers, "body": body})
                payload = json.dumps({"error": {"message": f"echo {TOKEN}"}}).encode()
                reply = f"HTTP/1.1 {self.status} X\r\nContent-Length: {len(payload)}\r\n\r\n"
                tls.sendall(reply.encode() + payload)


def _read_head(sock: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data.split(b"\r\n\r\n")[0]


class FakeOneCli:
    def __init__(self) -> None:
        self.status = 200
        self.body: bytes = b"{}"
        self.paths: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer.paths.append(self.path)
                self.send_response(outer.status)
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self._thread.start()

    def serve_config(self, proxy_port: int, ca_pem: str, **overrides: Any) -> None:
        env = {
            "HTTPS_PROXY": f"http://{USER}:{TOKEN}@host.docker.internal:{proxy_port}",
            "CLAUDE_CODE_OAUTH_TOKEN": "placeholder",
        }
        config: dict[str, Any] = {
            "env": env,
            "caCertificate": ca_pem,
            "caCertificateContainerPath": "/x",
        }
        config.update(overrides)
        self.body = json.dumps(config).encode()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture
def onecli() -> Iterator[FakeOneCli]:
    fake = FakeOneCli()
    try:
        yield fake
    finally:
        fake.close()


@pytest.fixture
def proxies() -> Iterator[Callable[..., FakeProxy]]:
    made: list[FakeProxy] = []

    def make(mode: str, ca: Ca | None = None, status: int = 400) -> FakeProxy:
        proxy = FakeProxy(mode, ca, status)
        made.append(proxy)
        return proxy

    yield make
    for proxy in made:
        proxy.close()


def make_probe(onecli: FakeOneCli, log: io.StringIO | None = None, timeout: float = 3.0) -> Any:
    return ClaudeProbe(
        onecli_url=onecli.url,
        agent_group=GROUP,
        timeout=timeout,
        events=EventLog(log or io.StringIO()),
    )


def assert_token_absent(*things: object) -> None:
    for thing in things:
        text = thing if isinstance(thing, str) else json.dumps(thing, default=repr)
        assert TOKEN not in text
        assert TOKEN[:8] not in text
        assert BASIC not in text
        assert base64.b64encode(TOKEN.encode()).decode() not in text


async def test_400_is_ok_and_the_request_is_exactly_the_w2_probe(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("tls", ca, 400)
    onecli.serve_config(proxy.port, ca.pem)
    result = await make_probe(onecli).run()
    assert result["status"] == "ok"
    assert result["http_status"] == 400
    assert str(result["checked_at"]).startswith("20")
    assert set(result) == {"status", "http_status", "checked_at"}
    assert onecli.paths == [f"/v1/container-config?identifier={GROUP}"]
    (connect,) = proxy.connects
    assert connect["line"].startswith("CONNECT api.anthropic.com:443 ")
    assert connect["Proxy-Authorization"] == f"Basic {BASIC}"
    (request,) = proxy.requests
    assert request["line"] == "POST /v1/messages HTTP/1.1"
    assert request["headers"]["Authorization"] == "Bearer placeholder"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["body"] == b"{}"
    assert_token_absent(result)


@pytest.mark.parametrize(("http_status", "expected"), [(401, "failing"), (403, "failing")])
async def test_401_and_403_are_failing(
    ca: Ca,
    onecli: FakeOneCli,
    proxies: Callable[..., FakeProxy],
    http_status: int,
    expected: str,
) -> None:
    proxy = proxies("tls", ca, http_status)
    onecli.serve_config(proxy.port, ca.pem)
    result = await make_probe(onecli).run()
    assert (result["status"], result["http_status"]) == (expected, http_status)
    assert_token_absent(result)


@pytest.mark.parametrize("http_status", [200, 404, 429, 500, 529])
async def test_any_other_status_is_unknown(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy], http_status: int
) -> None:
    proxy = proxies("tls", ca, http_status)
    onecli.serve_config(proxy.port, ca.pem)
    result = await make_probe(onecli).run()
    assert (result["status"], result["http_status"]) == ("unknown", http_status)
    assert_token_absent(result)


async def test_the_proxy_host_in_the_config_is_never_contacted(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    """host.docker.internal does not resolve here: success proves the broker used 127.0.0.1."""
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("host.docker.internal", 1)
    proxy = proxies("tls", ca, 400)
    onecli.serve_config(proxy.port, ca.pem)
    assert (await make_probe(onecli).run())["status"] == "ok"


async def test_a_certificate_from_another_ca_is_unknown(
    ca: Ca, other_ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("tls", other_ca, 400)  # the proxy presents a cert the config's CA never signed
    onecli.serve_config(proxy.port, ca.pem)
    result = await make_probe(onecli).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    assert proxy.requests == []  # no request, so no Authorization header, was sent
    assert_token_absent(result)


async def test_a_refusing_proxy_is_unknown(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("407")
    onecli.serve_config(proxy.port, ca.pem)
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    assert_token_absent(result, log.getvalue())


async def test_a_proxy_that_does_not_speak_tls_is_unknown(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("garbage")
    onecli.serve_config(proxy.port, ca.pem)
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert result["status"] == "unknown"
    assert_token_absent(result, log.getvalue())


async def test_a_hanging_proxy_times_out_as_unknown(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("hang")
    onecli.serve_config(proxy.port, ca.pem)
    log = io.StringIO()
    result = await make_probe(onecli, log, timeout=0.3).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    assert_token_absent(result, log.getvalue())


async def test_a_closed_proxy_port_is_unknown(ca: Ca, onecli: FakeOneCli) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    onecli.serve_config(closed, ca.pem)
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert result["status"] == "unknown"
    assert_token_absent(result, log.getvalue())


@pytest.mark.parametrize("status", [404, 500])
async def test_a_container_config_failure_is_unknown(onecli: FakeOneCli, status: int) -> None:
    onecli.status = status
    onecli.body = json.dumps({"error": f"nope {TOKEN}"}).encode()
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    assert_token_absent(result, log.getvalue())


async def test_onecli_being_down_is_unknown() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    probe = ClaudeProbe(
        onecli_url=f"http://127.0.0.1:{port}", agent_group=GROUP, events=EventLog(io.StringIO())
    )
    assert (await probe.run())["status"] == "unknown"


@pytest.mark.parametrize(
    "overrides",
    [
        {"env": {}},
        {"env": "text"},
        {"env": {"HTTPS_PROXY": 5}},
        {"env": {"HTTPS_PROXY": "http://host.docker.internal:10255"}},  # no credentials
        {"env": {"HTTPS_PROXY": f"http://u:{TOKEN}@host.docker.internal"}},  # no port
        {"env": {"HTTPS_PROXY": f"http://u:{TOKEN}@host.docker.internal:notaport"}},
        {"caCertificate": ""},
        {"caCertificate": "not a pem"},
        {"caCertificate": 7},
    ],
)
async def test_a_config_that_is_not_usable_is_unknown(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy], overrides: dict[str, Any]
) -> None:
    proxy = proxies("tls", ca, 400)
    onecli.serve_config(proxy.port, ca.pem, **overrides)
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    assert proxy.connects == []
    assert_token_absent(result, log.getvalue())


@pytest.mark.parametrize("body", [b"not json", b"[]", b'"x"', b""])
async def test_a_config_that_is_not_an_object_is_unknown(onecli: FakeOneCli, body: bytes) -> None:
    onecli.body = body
    assert (await make_probe(onecli).run())["status"] == "unknown"


async def test_an_exception_carrying_the_token_never_surfaces(
    onecli: FakeOneCli, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    def boom(self: ClaudeProbe) -> int:
        raise RuntimeError(f"connect failed with Proxy-Authorization: Basic {BASIC} / {TOKEN}")

    monkeypatch.setattr(probe_module.ClaudeProbe, "_blocking", boom)
    log = io.StringIO()
    result = await make_probe(onecli, log).run()
    assert (result["status"], result["http_status"]) == ("unknown", None)
    events = [json.loads(line) for line in log.getvalue().splitlines()]
    assert events[-1]["event"] == "claude_probe"
    assert events[-1]["error"] == "RuntimeError"  # the type, never the message
    out = capfd.readouterr()
    assert_token_absent(result, log.getvalue(), out.out, out.err, repr(result))


async def test_the_log_records_the_outcome_without_the_token(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("tls", ca, 401)
    onecli.serve_config(proxy.port, ca.pem)
    log = io.StringIO()
    await make_probe(onecli, log).run()
    (event,) = [json.loads(line) for line in log.getvalue().splitlines()]
    assert event["event"] == "claude_probe"
    assert event["status"] == "failing"
    assert event["http_status"] == 401
    assert_token_absent(log.getvalue())


def test_the_agent_group_must_be_an_id() -> None:
    with pytest.raises(ValueError, match="agent group"):
        ClaudeProbe(onecli_url="http://127.0.0.1:1", agent_group="../x&y=1")


async def test_probe_runs_do_not_block_the_event_loop(
    ca: Ca, onecli: FakeOneCli, proxies: Callable[..., FakeProxy]
) -> None:
    proxy = proxies("hang")
    onecli.serve_config(proxy.port, ca.pem)
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    await make_probe(onecli, timeout=0.3).run()
    task.cancel()
    assert ticks > 5
