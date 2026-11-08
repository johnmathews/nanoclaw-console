"""`/api/overview` (docs/architecture.md §4.4, §4.7) against the fake broker and fake Loki."""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import AppFactory
from tests.fake_broker import FakeBroker
from tests.fake_loki import FakeLoki


def overview(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/overview", headers=auth)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_a_healthy_overview(client: TestClient, auth: dict[str, str], loki: FakeLoki) -> None:
    loki.onecli(12, 200)
    loki.onecli(40, 200)
    loki.onecli(3, 400, beta=False)  # the probe
    body = overview(client, auth)
    assert body["generated_at"] == "2026-11-08T14:30:00.000Z"
    assert body["claude"] == {
        "status": "ok",
        "reasons": [
            "The last agent call to Claude succeeded (HTTP 200).",
            "The broker's probe through OneCLI was accepted (HTTP 400).",
        ],
        "last_agent_call": {
            "at": "2026-11-08T14:18:00.000Z",
            "status": 200,
            "agent": "main-group",
            "injections_applied": 1,
        },
        "last_success_at": "2026-11-08T14:18:00.000Z",
        "agent_calls_24h": 2,
        "auth_failures_1h": 0,
        "auth_failures_24h": 0,
        "probe": {"status": "ok", "http_status": 400, "checked_at": "2026-11-08T14:25:00.000Z"},
    }
    assert body["nanoclaw"] == {
        "available": True,
        "healthy": True,
        "uptime_seconds": 72739,
        "message_loop_running": True,
        "channels": [{"name": "cli", "connected": True}, {"name": "slack", "connected": True}],
        "queue": {"active": 1, "max": 0, "waiting": 0},
        "registered_group_count": 15,
        "active_session_count": 18,
        "last_message_at": "2026-11-08T13:37:45.983Z",
        "tasks": {
            "active_count": 14,
            "paused_count": 2,
            "next_run_at": "2026-11-08T14:22:00.000Z",
            "recent_failures": 0,
        },
    }
    assert body["counts"] == {
        "groups": 15,
        "channels": 17,
        "wirings": 14,
        "sessions": 80,
        "tasks": 16,
        "tasks_paused": 2,
        "tasks_overdue_on_resume": 2,
        "pending_approvals": 1,
        "dropped_messages": 3,
        "host_errors_24h": 0,
        "host_warnings_24h": 0,
    }
    assert body["sources"] == {
        "broker": {"ok": True, "errors": {}},
        "loki": {"ok": True, "errors": {}},
    }


def test_quota_is_labelled_as_the_host_login(client: TestClient, auth: dict[str, str]) -> None:
    """D6, F7: `ncl usage` reads the host's ~/.claude login, never NanoClaw's token."""
    quota = overview(client, auth)["quota"]
    assert quota == {
        "available": True,
        "label": "Weekly quota of the host's ~/.claude login (not NanoClaw's token)",
        "source": "host ~/.claude login",
        "weekly_pct": 39,
        "resets_at": "2026-11-10T20:00:00.000Z",
        "resets_text": "Nov 10, 9pm (Europe/Amsterdam)",
    }


def test_401s_in_the_last_hour_make_claude_degraded(
    client: TestClient, auth: dict[str, str], loki: FakeLoki
) -> None:
    """W6 acceptance: degraded when Loki shows 401s in the last hour."""
    loki.onecli(5, 200)
    loki.onecli(20, 401)
    loki.onecli(45, 401)
    claude = overview(client, auth)["claude"]
    assert claude["status"] == "degraded"
    assert claude["auth_failures_1h"] == 2
    assert any("401" in r for r in claude["reasons"])


def test_a_401_on_the_last_agent_call_is_failing(
    client: TestClient, auth: dict[str, str], loki: FakeLoki
) -> None:
    loki.onecli(30, 200)
    loki.onecli(2, 401)
    assert overview(client, auth)["claude"]["status"] == "failing"


def test_probe_failing_is_failing(
    client: TestClient, auth: dict[str, str], loki: FakeLoki, broker: FakeBroker
) -> None:
    loki.onecli(30, 200)
    broker.set("claude-probe", {"status": "failing", "http_status": 401, "checked_at": None})
    claude = overview(client, auth)["claude"]
    assert claude["status"] == "failing"
    assert claude["probe"] == {"status": "failing", "http_status": 401, "checked_at": None}


def test_no_traffic_and_no_probe_is_unknown(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.fail("claude-probe", "unknown_verb")  # a broker from before the probe existed
    body = overview(client, auth)
    assert body["claude"]["status"] == "unknown"
    assert body["claude"]["probe"] is None
    assert body["sources"]["broker"]["errors"] == {"claude-probe": "unknown_verb"}


def test_health_not_answering(client: TestClient, auth: dict[str, str], broker: FakeBroker) -> None:
    broker.set("health", {"available": False})
    body = overview(client, auth)
    assert body["nanoclaw"] == {"available": False, "reason": "not_answering"}
    assert "nanoclaw_not_answering" in [w["kind"] for w in body["warnings"]]


def test_broker_down_is_a_degraded_answer(
    client: TestClient, auth: dict[str, str], broker: FakeBroker, loki: FakeLoki
) -> None:
    loki.onecli(5, 200)
    broker.stop()
    body = overview(client, auth)
    assert body["claude"]["status"] == "ok"  # from Loki alone
    assert body["claude"]["probe"] is None
    assert body["nanoclaw"] == {"available": False, "reason": "broker_error"}
    assert body["quota"]["available"] is False
    assert body["quota"]["reason"] == "broker_error"
    assert "host" in body["quota"]["label"]
    broker_counts = {k: v for k, v in body["counts"].items() if not k.startswith("host_")}
    assert set(broker_counts.values()) == {None}
    assert body["sources"]["broker"]["ok"] is False
    assert set(body["sources"]["broker"]["errors"].values()) == {"unavailable"}
    assert body["warnings"][0]["kind"] == "source_unavailable"


def test_loki_not_configured(make_client: AppFactory, auth: dict[str, str]) -> None:
    body = overview(make_client(loki_url=None), auth)
    assert body["claude"]["status"] == "ok"  # the probe still answers
    assert body["claude"]["agent_calls_24h"] is None
    assert body["claude"]["last_agent_call"] is None
    assert body["counts"]["host_errors_24h"] is None
    assert body["sources"]["loki"] == {
        "ok": False,
        "errors": {"claude": "not_configured", "host_logs": "not_configured"},
    }


def test_loki_down(client: TestClient, auth: dict[str, str], loki: FakeLoki) -> None:
    loki.status = 502
    body = overview(client, auth)
    assert body["sources"]["loki"]["errors"] == {
        "claude": "unavailable",
        "host_logs": "unavailable",
    }
    assert body["claude"]["auth_failures_1h"] is None


def test_loki_answers_are_cached(client: TestClient, auth: dict[str, str], loki: FakeLoki) -> None:
    overview(client, auth)
    asked = len(loki.queries)
    assert asked > 0
    overview(client, auth)
    client.get("/api/problems", headers=auth)
    assert len(loki.queries) == asked


def test_warnings_strip_lists_the_problems(client: TestClient, auth: dict[str, str]) -> None:
    kinds = [w["kind"] for w in overview(client, auth)["warnings"]]
    assert kinds.count("task_paused_overdue") == 2
    assert "approval_stale" in kinds
