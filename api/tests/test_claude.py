"""Claude health (docs/architecture.md §4.4): OneCLI's signals in Loki and the status rule."""

from datetime import datetime, timedelta

import pytest

from nanoclaw_console.claude import (
    AgentCall,
    ClaudeSignals,
    claude_status,
    parse_onecli_line,
    read_signals,
)
from nanoclaw_console.loki import LokiClient
from tests.conftest import NOW
from tests.fake_loki import LOKI_URL, FakeLoki


def loki_client(loki: FakeLoki) -> LokiClient:
    return LokiClient(LOKI_URL, transport=loki.transport())


def ago(minutes: float) -> datetime:
    return NOW - timedelta(minutes=minutes)


LIVE_LINE = (
    'time=2026-11-08T13:37:45Z level=INFO agent="main-group" MITM method=POST '
    "url=https://api.anthropic.com:443/v1/messages?beta=true status=200 "
    "content_type=text/event-stream; charset=utf-8 injections_applied=1"
)


def test_parse_the_live_line() -> None:
    call = parse_onecli_line(NOW, LIVE_LINE)
    assert call == AgentCall(at=NOW, status=200, agent="main-group", injections_applied=1)


def test_parse_a_line_without_fields() -> None:
    assert parse_onecli_line(NOW, "garbage") == AgentCall(
        at=NOW, status=None, agent=None, injections_applied=None
    )


class TestReadSignals:
    pytestmark = pytest.mark.anyio

    async def test_probe_lines_are_not_agent_traffic(self, loki: FakeLoki) -> None:
        loki.onecli(10, 200)
        loki.onecli(2, 400, beta=False)  # the broker's probe, newer than the agent call
        signals = await read_signals(loki_client(loki), NOW)
        assert signals.last_agent_call is not None
        assert signals.last_agent_call.status == 200
        assert signals.last_agent_call.at == ago(10)
        assert signals.last_success_at == ago(10)
        assert signals.agent_calls_24h == 1
        assert signals.auth_failures_1h == 0
        assert signals.auth_failures_24h == 0

    async def test_auth_failures_count_agent_and_probe_lines(self, loki: FakeLoki) -> None:
        loki.onecli(30, 401)
        loki.onecli(50, 403, beta=False)
        loki.onecli(120, 401, beta=False)
        loki.onecli(60 * 25, 401)  # outside 24 h
        loki.onecli(5, 200)
        signals = await read_signals(loki_client(loki), NOW)
        assert signals.auth_failures_1h == 2
        assert signals.auth_failures_24h == 3
        assert signals.agent_calls_24h == 2

    async def test_last_success_is_the_last_2xx(self, loki: FakeLoki) -> None:
        loki.onecli(90, 200)
        loki.onecli(3, 529)
        signals = await read_signals(loki_client(loki), NOW)
        assert signals.last_agent_call is not None
        assert signals.last_agent_call.status == 529
        assert signals.last_success_at == ago(90)

    async def test_no_traffic(self, loki: FakeLoki) -> None:
        loki.onecli(60 * 30, 200)  # older than the window
        signals = await read_signals(loki_client(loki), NOW)
        assert signals == ClaudeSignals(
            last_agent_call=None,
            last_success_at=None,
            agent_calls_24h=0,
            auth_failures_1h=0,
            auth_failures_24h=0,
        )

    async def test_other_containers_are_ignored(self, loki: FakeLoki) -> None:
        loki.add(1, {"container": "nanoclaw-agent"}, LIVE_LINE.replace("200", "401"))
        signals = await read_signals(loki_client(loki), NOW)
        assert signals.auth_failures_24h == 0
        assert signals.last_agent_call is None


def signals(
    status: int | None = 200,
    *,
    injections: int | None = 1,
    auth_1h: int = 0,
    auth_24h: int = 0,
) -> ClaudeSignals:
    call = None
    if status is not None:
        call = AgentCall(at=NOW, status=status, agent="main-group", injections_applied=injections)
    return ClaudeSignals(
        last_agent_call=call,
        last_success_at=NOW if status is not None and 200 <= status < 300 else None,
        agent_calls_24h=0 if status is None else 1,
        auth_failures_1h=auth_1h,
        auth_failures_24h=max(auth_24h, auth_1h),
    )


def probe(status: str) -> dict[str, object]:
    return {"status": status, "http_status": {"ok": 400, "failing": 401}.get(status)}


@pytest.mark.parametrize(
    ("sig", "prb", "expected"),
    [
        # ok
        (signals(200), None, "ok"),
        (signals(200), probe("ok"), "ok"),
        (signals(None), probe("ok"), "ok"),
        (None, probe("ok"), "ok"),
        (signals(200, auth_24h=4), None, "ok"),  # old 401s, none in the last hour
        # failing
        (signals(401), None, "failing"),
        (signals(403), probe("ok"), "failing"),
        (signals(200), probe("failing"), "failing"),
        (None, probe("failing"), "failing"),
        (signals(401, auth_1h=3), None, "failing"),
        # degraded
        (signals(200, auth_1h=1), None, "degraded"),
        (signals(200, auth_1h=2), probe("ok"), "degraded"),
        (signals(429), None, "degraded"),
        (signals(529), probe("ok"), "degraded"),
        (signals(200, injections=0), None, "degraded"),
        (signals(None, auth_1h=1), None, "degraded"),
        # unknown
        (signals(None), None, "unknown"),
        (signals(None), probe("unknown"), "unknown"),
        (None, None, "unknown"),
        (None, probe("unknown"), "unknown"),
        (signals(None), {"status": "weird"}, "unknown"),
    ],
)
def test_status_rule(
    sig: ClaudeSignals | None, prb: dict[str, object] | None, expected: str
) -> None:
    status, reasons = claude_status(sig, prb)
    assert status == expected
    assert reasons, "every status explains itself"
    assert all(isinstance(r, str) and r.endswith(".") for r in reasons)


def test_reasons_name_the_auth_failures() -> None:
    _, reasons = claude_status(signals(200, auth_1h=3), None)
    assert any("3" in r and "401" in r for r in reasons)


def test_unknown_says_why_when_loki_is_missing() -> None:
    _, reasons = claude_status(None, None)
    assert any("Loki" in r for r in reasons)
