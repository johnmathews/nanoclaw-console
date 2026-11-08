"""The broker client (docs/architecture.md §4.3) against a fake broker on a real Unix socket."""

import json
import socket
from pathlib import Path

import anyio
import pytest

from nanoclaw_console.broker_client import BrokerClient, BrokerError
from tests.fake_broker import FakeBroker

pytestmark = pytest.mark.anyio


async def test_call_returns_data_and_sends_one_request_line(broker: FakeBroker) -> None:
    data = await BrokerClient(broker.path).call("groups-list")
    assert data == broker.data("groups-list")
    assert broker.requests == [{"verb": "groups-list", "params": {}}]


async def test_call_with_an_id(broker: FakeBroker) -> None:
    params = {"id": "task-1778399790530-fx0229"}
    data = await BrokerClient(broker.path).call("tasks-get", params)
    assert isinstance(data, dict)
    assert data["status"] == "paused"
    assert broker.requests == [{"verb": "tasks-get", "params": params}]


async def test_broker_error_keeps_the_code_only(broker: FakeBroker) -> None:
    broker.fail("groups-list", "ncl_error")
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path).call("groups-list")
    assert info.value.code == "ncl_error"
    assert "fake" not in str(info.value)


async def test_unknown_verb_is_the_brokers_code(broker: FakeBroker) -> None:
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path).call("no-such-verb")
    assert info.value.code == "unknown_verb"


async def test_an_odd_error_code_becomes_unknown(broker: FakeBroker) -> None:
    broker.raw = lambda _req: b'{"ok": false, "error": {"code": "Bearer abc.def ghi"}}\n'
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path).call("groups-list")
    assert info.value.code == "unknown"


async def test_missing_socket_is_unavailable(short_dir: Path) -> None:
    with pytest.raises(BrokerError) as info:
        await BrokerClient(short_dir / "absent.sock").call("groups-list")
    assert info.value.code == "unavailable"


async def test_refused_socket_is_unavailable(short_dir: Path) -> None:
    path = short_dir / "dead.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(path))
    s.close()  # bound, never listened: connecting is refused
    with pytest.raises(BrokerError) as info:
        await BrokerClient(path).call("groups-list")
    assert info.value.code == "unavailable"


async def test_closed_without_an_answer_is_unavailable(broker: FakeBroker) -> None:
    broker.raw = lambda _req: None
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path).call("groups-list")
    assert info.value.code == "unavailable"


@pytest.mark.parametrize(
    "raw",
    [
        b"not json\n",
        b"[1, 2]\n",
        b'{"data": 1}\n',
        b'{"ok": "yes", "data": 1}\n',
        b'{"ok": true}\n',
        b'{"ok": true, "data": 1',
        b'\xff\xfe{"ok": true}\n',
    ],
)
async def test_malformed_reply_is_protocol_error(broker: FakeBroker, raw: bytes) -> None:
    broker.raw = lambda _req: raw
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path).call("groups-list")
    assert info.value.code == "protocol_error"


async def test_oversize_reply_is_protocol_error(broker: FakeBroker) -> None:
    big = json.dumps({"ok": True, "data": "x" * 5000}).encode() + b"\n"
    broker.raw = lambda _req: big
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path, max_reply=1024).call("groups-list")
    assert info.value.code == "protocol_error"


async def test_slow_broker_times_out(broker: FakeBroker) -> None:
    broker.delay = 0.5
    with pytest.raises(BrokerError) as info:
        await BrokerClient(broker.path, timeout=0.1).call("groups-list")
    assert info.value.code == "timeout"


async def test_at_most_four_calls_in_flight(broker: FakeBroker) -> None:
    broker.delay = 0.1
    client = BrokerClient(broker.path)
    async with anyio.create_task_group() as tg:
        for _ in range(10):
            tg.start_soon(client.call, "groups-list")
    assert len(broker.requests) == 10
    assert broker.max_in_flight == 4


async def test_a_recreated_socket_is_picked_up(broker: FakeBroker) -> None:
    client = BrokerClient(broker.path)
    await client.call("groups-list")
    broker.stop()
    with pytest.raises(BrokerError):
        await client.call("groups-list")
    broker.start()
    assert await client.call("groups-list") == broker.data("groups-list")
