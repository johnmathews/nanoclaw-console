"""The ncl client speaks NanoClaw's frame protocol: one fresh connection, one line each way."""

import asyncio
import contextlib
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from nanoclaw_broker.errors import NclError, NclProtocolError, NclTimeout, NclUnavailable
from nanoclaw_broker.ncl_client import NclClient
from tests.conftest import FakeNcl


async def test_call_sends_one_frame_and_returns_data(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    data = await client.call("groups-list", {})
    assert isinstance(data, list)
    assert len(data) == 15
    assert len(fake_ncl.frames) == 1
    frame = fake_ncl.frames[0]
    assert set(frame) == {"id", "command", "args"}
    assert frame["command"] == "groups-list"
    assert frame["args"] == {}
    assert isinstance(frame["id"], str)
    assert frame["id"]


async def test_each_call_gets_a_new_id(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    await client.call("groups-list", {})
    await client.call("groups-list", {})
    assert fake_ncl.frames[0]["id"] != fake_ncl.frames[1]["id"]


async def test_args_are_sent_as_given(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    await client.call("tasks-list", {"all": True})
    assert fake_ncl.frames[0]["args"] == {"all": True}


async def test_ok_false_raises_ncl_error_with_code(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    with pytest.raises(NclError) as exc:
        await client.call("groups-get", {"id": "no-such-group"})
    assert exc.value.code == "ncl_error"
    assert exc.value.ncl_code == "handler-error"
    assert exc.value.message == "ncl rejected the request (handler-error)"


async def _ncl_says(fake_ncl: FakeNcl, code: object, message: str) -> NclError:
    async def responder(frame: dict[str, Any]) -> bytes:
        error = {"code": code, "message": message}
        reply = {"id": frame["id"], "ok": False, "error": error}
        return (json.dumps(reply) + "\n").encode()

    fake_ncl.responder = responder
    with pytest.raises(NclError) as exc:
        await NclClient(fake_ncl.path).call("groups-list", {})
    return exc.value


async def test_ncl_free_text_never_reaches_the_client_message(fake_ncl: FakeNcl) -> None:
    """The client gets ncl's code and a fixed sentence; the free text is kept as `detail`."""
    err = await _ncl_says(fake_ncl, "invalid-args", "bad flag --token PLANTED-SECRET-ncl-text")
    assert err.message == "ncl rejected the request (invalid-args)"
    assert "PLANTED-SECRET" not in err.message
    assert "PLANTED-SECRET" not in str(err)  # str(err) is what a log or traceback would show
    assert "PLANTED-SECRET" not in repr(err)
    assert "bad flag" in err.detail  # the broker's own log still has the context


async def test_ncl_error_detail_is_redacted_and_cut(fake_ncl: FakeNcl) -> None:
    text = (
        "see https://u:PLANTED-SECRET-a@ss@host/p?k=PLANTED-SECRET-b with Bearer PLANTED-SECRET-c"
    )
    err = await _ncl_says(fake_ncl, "handler-error", text + " " + "x" * 5000)
    assert "PLANTED-SECRET" not in err.detail
    assert err.detail.startswith("see https://host with Bearer •••")
    assert len(err.detail) <= 500


@pytest.mark.parametrize(
    "code", ["Bad Code", "x" * 41, "1abc", "a\nb", "tok=PLANTED-SECRET-code", ""]
)
async def test_an_odd_ncl_code_is_reported_as_unknown(fake_ncl: FakeNcl, code: str) -> None:
    err = await _ncl_says(fake_ncl, code, "m")
    assert err.ncl_code == "unknown"
    assert err.message == "ncl rejected the request (unknown)"
    assert "PLANTED-SECRET" not in err.message


async def test_missing_socket_is_unavailable(short_dir: Path) -> None:
    client = NclClient(short_dir / "absent.sock")
    with pytest.raises(NclUnavailable) as exc:
        await client.call("groups-list", {})
    assert exc.value.code == "unavailable"


async def test_refused_socket_is_unavailable(short_dir: Path) -> None:
    """A socket file nobody listens on: what NanoClaw leaves behind when it dies."""
    path = short_dir / "dead.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(path))
    s.close()
    with pytest.raises(NclUnavailable):
        await NclClient(path).call("groups-list", {})


async def test_unreadable_socket_is_unavailable(short_dir: Path) -> None:
    path = short_dir / "not-a-socket"
    path.write_text("")
    with pytest.raises(NclUnavailable):
        await NclClient(path).call("groups-list", {})


async def test_recreated_socket_is_picked_up(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    await client.call("groups-list", {})
    # NanoClaw unlinks and rebinds ncl.sock on restart; a client holding the old socket would fail.
    await fake_ncl.restart()
    await client.call("groups-list", {})
    assert fake_ncl.calls("groups-list") == 2


async def test_down_then_up_recovers(fake_ncl: FakeNcl) -> None:
    client = NclClient(fake_ncl.path)
    await fake_ncl.stop()
    with pytest.raises(NclUnavailable):
        await client.call("groups-list", {})
    await fake_ncl.start()
    assert isinstance(await client.call("groups-list", {}), list)


async def test_no_reply_times_out(fake_ncl: FakeNcl) -> None:
    fake_ncl.delay = 5
    client = NclClient(fake_ncl.path, timeout=0.1)
    with pytest.raises(NclTimeout) as exc:
        await client.call("groups-list", {})
    assert exc.value.code == "timeout"


async def test_oversize_reply_is_refused(fake_ncl: FakeNcl) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        reply = {"id": frame["id"], "ok": True, "data": "x" * 4096}
        return (json.dumps(reply) + "\n").encode()

    fake_ncl.responder = responder
    client = NclClient(fake_ncl.path, max_reply=1024)
    with pytest.raises(NclProtocolError) as exc:
        await client.call("groups-list", {})
    assert exc.value.code == "protocol_error"
    assert "too large" in exc.value.message


async def test_oversize_reply_without_newline_is_refused(fake_ncl: FakeNcl) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        return b"x" * 4096

    fake_ncl.responder = responder
    with pytest.raises(NclProtocolError):
        await NclClient(fake_ncl.path, max_reply=1024).call("groups-list", {})


@pytest.mark.parametrize(
    "raw",
    [
        b"",  # closed without a reply
        b"not json\n",
        b"[1, 2]\n",
        b'{"ok": "yes", "data": 1}\n',
        b'{"ok": false}\n',
        b'{"ok": false, "error": "boom"}\n',
        b'{"ok": false, "error": {"code": 1, "message": "m"}}\n',
        b'{"ok": true}\n',
        b'{"partial": \n',
        b"\xff\xfe\n",
    ],
)
async def test_malformed_replies_are_protocol_errors(fake_ncl: FakeNcl, raw: bytes) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        return raw

    fake_ncl.responder = responder
    with pytest.raises(NclProtocolError):
        await NclClient(fake_ncl.path).call("groups-list", {})


async def test_reply_for_another_id_is_refused(fake_ncl: FakeNcl) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        return (json.dumps({"id": "someone-else", "ok": True, "data": []}) + "\n").encode()

    fake_ncl.responder = responder
    with pytest.raises(NclProtocolError):
        await NclClient(fake_ncl.path).call("groups-list", {})


@pytest.mark.parametrize(
    "make_reply",
    [
        lambda rid: {"id": "someone-else", "ok": False, "error": {"code": "x", "message": "m"}},
        lambda rid: {"id": rid, "ok": True},
    ],
)
async def test_error_for_another_id_or_ok_without_data_is_refused(
    fake_ncl: FakeNcl, make_reply: Any
) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        return (json.dumps(make_reply(frame["id"])) + "\n").encode()

    fake_ncl.responder = responder
    with pytest.raises(NclProtocolError):
        await NclClient(fake_ncl.path).call("groups-list", {})


async def test_transport_error_with_unknown_id_is_an_ncl_error(fake_ncl: FakeNcl) -> None:
    """socket-server.ts answers a frame it cannot parse with id "unknown"."""

    async def responder(frame: dict[str, Any]) -> bytes:
        error = {"code": "transport-error", "message": "bad"}
        reply = {"id": "unknown", "ok": False, "error": error}
        return (json.dumps(reply) + "\n").encode()

    fake_ncl.responder = responder
    with pytest.raises(NclError) as exc:
        await NclClient(fake_ncl.path).call("groups-list", {})
    assert exc.value.ncl_code == "transport-error"


async def test_human_is_never_returned(fake_ncl: FakeNcl) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        reply = {"id": frame["id"], "ok": True, "data": {"a": 1}, "human": "Bearer x"}
        return (json.dumps(reply) + "\n").encode()

    fake_ncl.responder = responder
    assert await NclClient(fake_ncl.path).call("groups-list", {}) == {"a": 1}


async def test_the_request_is_exactly_one_line(fake_ncl: FakeNcl) -> None:
    """socket-server.ts dispatches every line of a connection, so one call must be one line."""
    seen: list[bytes] = []

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        seen.append(await reader.readline())
        with contextlib.suppress(TimeoutError):
            seen.append(await asyncio.wait_for(reader.read(100), 0.2))
        writer.close()

    await fake_ncl.stop()
    server = await asyncio.start_unix_server(handler, path=str(fake_ncl.path))
    try:
        with pytest.raises(NclProtocolError):
            await NclClient(fake_ncl.path, timeout=1).call("tasks-get", {"id": "a\nb"})
    finally:
        server.close()
        await server.wait_closed()
    # One line, and nothing after it: no second frame and no half-close (EOF would read b"").
    assert len(seen) == 1
    assert seen[0].count(b"\n") == 1
    assert seen[0].endswith(b"\n")
    assert json.loads(seen[0])["args"] == {"id": "a\nb"}
