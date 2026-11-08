"""`/api/problems` (docs/architecture.md §4.5, §4.7) against the fake broker and fake Loki."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.fake_broker import FakeBroker
from tests.fake_loki import FakeLoki

ROUTES = ["/api/overview", "/api/groups", "/api/tasks", "/api/permissions", "/api/problems"]
SEVERITY = {"error": 0, "warning": 1, "info": 2}


def problems(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/problems", headers=auth)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def kinds(body: dict[str, Any]) -> list[str]:
    return [item["kind"] for item in body["items"]]


def test_the_fixtures_problems(client: TestClient, auth: dict[str, str], loki: FakeLoki) -> None:
    loki.onecli(10, 200)
    body = problems(client, auth)
    assert sorted(kinds(body)) == sorted(
        ["task_paused_overdue"] * 2 + ["approval_stale"] + ["dropped_messages"] * 3
    )
    overdue = next(i for i in body["items"] if i["ref"]["id"] == "task-1778399790530-fx0229")
    assert overdue == {
        "kind": "task_paused_overdue",
        "severity": "warning",
        "title": "documentation-summary.md is paused and overdue",
        "detail": "Resuming it runs it once straight away, then at 09:03 every day.",
        "at": "2026-05-27T07:03:00.000Z",
        "count": None,
        "ref": {"type": "task", "id": "task-1778399790530-fx0229"},
    }
    stale = next(i for i in body["items"] if i["kind"] == "approval_stale")
    assert stale["ref"] == {"type": "approval", "id": "appr-0283-fixture"}
    assert "147 days" in stale["title"]
    dropped = [i for i in body["items"] if i["kind"] == "dropped_messages"]
    assert {d["count"] for d in dropped} == {1, 4}
    assert all(d["severity"] == "info" for d in dropped)
    assert body["host_logs"] == {
        "window_hours": 24,
        "errors": 0,
        "warnings": 0,
        "truncated": False,
        "groups": [],
    }


def test_items_are_sorted_by_severity(
    client: TestClient, auth: dict[str, str], loki: FakeLoki, broker: FakeBroker
) -> None:
    loki.onecli(10, 401)
    loki.nanoclaw(30, "ERROR", "Boom")
    loki.nanoclaw(20, "WARN", "Hmm")
    rows = broker.data("tasks-list")
    rows[5] = {**rows[5], "failed_runs": 2}
    items = problems(client, auth)["items"]
    ranks = [SEVERITY[i["severity"]] for i in items]
    assert ranks == sorted(ranks)
    found = kinds({"items": items})
    for kind in (
        "claude_failing",
        "claude_auth_failures",
        "host_log_errors",
        "host_log_warnings",
        "task_failures",
    ):
        assert kind in found


def test_host_log_groups(client: TestClient, auth: dict[str, str], loki: FakeLoki) -> None:
    loki.nanoclaw(30, "ERROR", 'Container exited code=1 group="a"')
    loki.nanoclaw(10, "ERROR", 'Container exited code=137 group="b"')
    body = problems(client, auth)
    logs = body["host_logs"]
    assert logs["errors"] == 2
    assert logs["groups"] == [
        {
            "level": "ERROR",
            "message": "Container exited",
            "count": 2,
            "first_at": "2026-11-08T14:00:00.000Z",
            "last_at": "2026-11-08T14:20:00.000Z",
            "sample": '[14:20:00.123] ERROR Container exited code=137 group="b"',
        }
    ]
    item = next(i for i in body["items"] if i["kind"] == "host_log_errors")
    assert item["count"] == 2
    assert item["severity"] == "error"
    assert item["at"] == "2026-11-08T14:20:00.000Z"


@pytest.mark.parametrize(("minutes_ago", "severity"), [(20, "error"), (300, "warning")])
def test_auth_failures_severity_depends_on_the_last_hour(
    client: TestClient, auth: dict[str, str], loki: FakeLoki, minutes_ago: int, severity: str
) -> None:
    loki.onecli(5, 200)
    loki.onecli(minutes_ago, 401, beta=False)
    item = next(i for i in problems(client, auth)["items"] if i["kind"] == "claude_auth_failures")
    assert item["severity"] == severity
    assert item["count"] == 1


def test_nanoclaw_health_problems(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    health = broker.data("health")
    health["channels"][1]["connected"] = False
    health["messageLoopRunning"] = False
    health["healthy"] = False
    found = kinds(problems(client, auth))
    assert "channel_disconnected" in found
    assert "message_loop_stopped" in found
    assert "nanoclaw_unhealthy" in found


def test_sources_unavailable(
    client: TestClient, auth: dict[str, str], broker: FakeBroker, loki: FakeLoki
) -> None:
    broker.stop()
    loki.status = 500
    body = problems(client, auth)
    assert body["host_logs"] is None
    sources = [i for i in body["items"] if i["kind"] == "source_unavailable"]
    assert [s["ref"] for s in sources] == [
        {"type": "source", "id": "broker"},
        {"type": "source", "id": "loki"},
    ]
    assert body["items"][:2] == sources


@pytest.mark.parametrize("route", ROUTES)
def test_no_planted_secret_in_any_view(
    client: TestClient, auth: dict[str, str], broker: FakeBroker, route: str
) -> None:
    """The broker redacts; the console must not bring back what it removed."""
    broker.data("tasks-list")[0]["script"] = "PLANTED-SECRET-script"
    broker.data("approvals-list")[0]["payload"] = "PLANTED-SECRET-payload"
    config = broker.data("groups-config-get", {"id": "ag-0022-fixture"})
    config["mcp_servers"]["journal"]["headers"]["Authorization"] = "Bearer PLANTED-SECRET-hdr"
    response = client.get(route, headers=auth)
    assert response.status_code == 200
    assert "PLANTED-SECRET" not in response.text
