"""The Loki client (docs/architecture.md §4.1) against the fake Loki transport."""

from datetime import timedelta

import httpx2
import pytest

from nanoclaw_console.loki import LokiClient, LokiError
from tests.conftest import NOW
from tests.fake_loki import LOKI_URL, FakeLoki

pytestmark = pytest.mark.anyio

DAY = timedelta(hours=24)


def client(loki: FakeLoki, **kwargs: object) -> LokiClient:
    return LokiClient(LOKI_URL, transport=loki.transport(), **kwargs)  # type: ignore[arg-type]


async def test_lines_come_newest_first_across_streams(loki: FakeLoki) -> None:
    loki.nanoclaw(30, "ERROR", "first")
    loki.nanoclaw(10, "WARN", "second")
    loki.nanoclaw(20, "ERROR", "third")
    loki.nanoclaw(5, "INFO", "not selected")
    lines = await client(loki).lines(
        '{job="nanoclaw", level=~"WARN|ERROR|FATAL"}', start=NOW - DAY, end=NOW, limit=100
    )
    assert [line.line.split()[-1] for line in lines] == ["second", "third", "first"]
    assert lines[0].labels["level"] == "WARN"
    assert lines[0].at == NOW - timedelta(minutes=10)


async def test_lines_sends_the_window_and_limit(loki: FakeLoki) -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return loki.handler(request)

    c = LokiClient(LOKI_URL, transport=httpx2.MockTransport(handler))
    await c.lines('{job="nanoclaw"}', start=NOW - DAY, end=NOW, limit=7)
    params = requests[0].url.params
    assert requests[0].url.path == "/loki/api/v1/query_range"
    assert params["limit"] == "7"
    assert params["direction"] == "backward"
    assert params["end"] == str(int(NOW.timestamp()) * 1_000_000_000)


async def test_count_sums_a_vector(loki: FakeLoki) -> None:
    for minutes in (5, 50, 90):
        loki.onecli(minutes, 401)
    query = 'sum(count_over_time({container="onecli"} |~ `status=40[13]\\b` [1h]))'
    assert await client(loki).count(query, at=NOW) == 2


async def test_count_of_an_empty_vector_is_zero(loki: FakeLoki) -> None:
    query = 'sum(count_over_time({container="onecli"} [1h]))'
    assert await client(loki).count(query, at=NOW) == 0


@pytest.mark.parametrize("status", [400, 500, 503])
async def test_http_error_is_unavailable(loki: FakeLoki, status: int) -> None:
    loki.status = status
    with pytest.raises(LokiError) as info:
        await client(loki).lines('{job="nanoclaw"}', start=NOW - DAY, end=NOW, limit=1)
    assert info.value.code == "unavailable"


async def test_network_error_is_unavailable(loki: FakeLoki) -> None:
    loki.error = httpx2.ConnectError("refused")
    with pytest.raises(LokiError) as info:
        await client(loki).count('sum(count_over_time({a="b"} [1h]))', at=NOW)
    assert info.value.code == "unavailable"


async def test_timeout_is_timeout(loki: FakeLoki) -> None:
    loki.error = httpx2.ReadTimeout("slow")
    with pytest.raises(LokiError) as info:
        await client(loki).count('sum(count_over_time({a="b"} [1h]))', at=NOW)
    assert info.value.code == "timeout"


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b'{"status": "error"}',
        b'{"status": "success", "data": {"resultType": "matrix", "result": []}}',
        b'{"status": "success", "data": {"resultType": "streams", "result": [{"values": 1}]}}',
        b'{"status": "success", "data": {"resultType": "streams",'
        b' "result": [{"stream": {}, "values": [["x", "line"]]}]}}',
    ],
)
async def test_malformed_lines_answer_is_bad_response(loki: FakeLoki, body: bytes) -> None:
    loki.body = body
    with pytest.raises(LokiError) as info:
        await client(loki).lines('{a="b"}', start=NOW - DAY, end=NOW, limit=1)
    assert info.value.code == "bad_response"


@pytest.mark.parametrize(
    "body",
    [
        b'{"status": "success", "data": {"resultType": "streams", "result": []}}',
        b'{"status": "success", "data": {"resultType": "vector",'
        b' "result": [{"metric": {}, "value": [1, "x"]}]}}',
        b'{"status": "success", "data": {"resultType": "vector", "result": [{"metric": {}}]}}',
    ],
)
async def test_malformed_count_answer_is_bad_response(loki: FakeLoki, body: bytes) -> None:
    loki.body = body
    with pytest.raises(LokiError) as info:
        await client(loki).count('sum(count_over_time({a="b"} [1h]))', at=NOW)
    assert info.value.code == "bad_response"


async def test_oversize_answer_is_bad_response(loki: FakeLoki) -> None:
    loki.body = b'{"status": "success", "pad": "' + b"x" * 4096 + b'"}'
    with pytest.raises(LokiError) as info:
        await client(loki, max_bytes=1024).lines('{a="b"}', start=NOW - DAY, end=NOW, limit=1)
    assert info.value.code == "bad_response"
