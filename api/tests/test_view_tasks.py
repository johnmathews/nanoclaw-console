"""`/api/tasks` and `/api/tasks/{id}` (docs/architecture.md §4.6, §4.7) against the fake broker."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.fake_broker import FakeBroker

PAUSED = ["task-1778399790530-fx0229", "task-1779373800000-fx0232"]


def tasks(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/tasks", headers=auth)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def by_id(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in body["tasks"]}


def test_every_task_is_listed(client: TestClient, auth: dict[str, str]) -> None:
    body = tasks(client, auth)
    assert body["generated_at"] == "2026-11-08T14:30:00.000Z"
    assert body["timezone"] == "Europe/Amsterdam"
    assert len(body["tasks"]) == 16
    assert body["sources"] == {"broker": {"ok": True, "errors": {}}}


def test_the_two_paused_series_are_overdue_on_resume(
    client: TestClient, auth: dict[str, str]
) -> None:
    body = tasks(client, auth)
    overdue = [t["id"] for t in body["tasks"] if t["overdue_on_resume"]]
    assert sorted(overdue) == sorted(PAUSED)
    for task in (by_id(body)[i] for i in PAUSED):
        assert task["status"] == "paused"
        assert task["next_run_at"] is None  # a paused task will not run


def test_a_paused_task_in_full(client: TestClient, auth: dict[str, str]) -> None:
    task = by_id(tasks(client, auth))[PAUSED[0]]
    assert task == {
        "id": "task-1778399790530-fx0229",
        "row_id": "task-0230-fixture",
        "group": {
            "id": "ag-0026-fixture",
            "name": "Lorem ipsum dolor sit amet 13",
            "folder": "id-0027-fixture",
        },
        "status": "paused",
        "overdue_on_resume": True,
        "prompt": (
            "Read /workspace/agent/tasks/documentation-summary.md and follow the "
            "instructions in it."
        ),
        "task_file": "documentation-summary.md",
        "has_script": True,  # the broker saw a script (planted in its fixture) and dropped it
        "schedule": {
            "cron": "3 9 * * *",
            "words": "At 09:03 every day",
            "timezone": "Europe/Amsterdam",
            "valid": True,
            "next_fire_at": "2026-11-09T08:03:00.000Z",
        },
        "next_run_at": None,
        "process_after": "2026-05-27T07:03:00.000Z",
        "last_run_at": "2026-05-26T07:03:00.000Z",
        "runs": 5,
        "failed_runs": 0,
        "tries": 0,
        "series_started_at": "2026-05-10T07:56:30.530Z",
        "series_age_days": 182,
        "occurrence_created_at": "2026-05-26T07:05:23.000Z",
        "session_id": "sess-0227-fixture",
    }


def test_a_pending_task(client: TestClient, auth: dict[str, str]) -> None:
    task = by_id(tasks(client, auth))["task-0238-fixture"]
    assert task["overdue_on_resume"] is False
    assert task["next_run_at"] == "2026-11-09T08:00:00.000Z"
    assert task["schedule"]["words"] == "At 09:00 on Monday"
    assert task["series_started_at"] is None  # a fixture id carries no time
    assert task["series_age_days"] is None
    assert task["task_file"] is None


def test_series_age_is_not_the_occurrence_age(client: TestClient, auth: dict[str, str]) -> None:
    """F20: the busy task's current occurrence is minutes old; its series is months old."""
    task = by_id(tasks(client, auth))["task-1783504800000-fx0235"]
    assert task["occurrence_created_at"] == "2026-11-08T13:22:40.667Z"
    assert task["series_started_at"] == "2026-07-08T10:00:00.000Z"
    assert task["series_age_days"] == 123


def test_sorted_by_next_run_with_paused_last(client: TestClient, auth: dict[str, str]) -> None:
    runs = [t["next_run_at"] for t in tasks(client, auth)["tasks"]]
    scheduled = [r for r in runs if r is not None]
    assert scheduled == sorted(scheduled)
    assert runs[-2:] == [None, None]


def test_no_script_text_ever(client: TestClient, auth: dict[str, str], broker: FakeBroker) -> None:
    rows = broker.data("tasks-list")
    rows[2] = {**rows[2], "script": "curl -H 'Authorization: Bearer PLANTED-SECRET-x'"}
    response = client.get("/api/tasks", headers=auth)
    assert "PLANTED-SECRET" not in response.text
    assert by_id(response.json())[rows[2]["series_id"]]["has_script"] is True


def test_broker_down_is_a_degraded_answer(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.stop()
    body = tasks(client, auth)
    assert body["tasks"] == []
    assert body["sources"]["broker"]["ok"] is False
    assert body["sources"]["broker"]["errors"] == {
        "tasks-list": "unavailable",
        "groups-list": "unavailable",
    }


def test_groups_unreadable_still_lists_tasks(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.fail("groups-list", "timeout")
    body = tasks(client, auth)
    assert len(body["tasks"]) == 16
    task = by_id(body)[PAUSED[0]]
    assert task["group"] == {"id": "ag-0026-fixture", "name": None, "folder": None}
    assert body["sources"]["broker"] == {"ok": False, "errors": {"groups-list": "timeout"}}


class TestDetail:
    def test_a_paused_task_with_its_file_and_log(
        self, client: TestClient, auth: dict[str, str]
    ) -> None:
        response = client.get(f"/api/tasks/{PAUSED[0]}", headers=auth)
        assert response.status_code == 200
        body = response.json()
        assert body["timezone"] == "Europe/Amsterdam"
        task = body["task"]
        assert task["id"] == PAUSED[0]
        assert task["overdue_on_resume"] is True
        assert task["recent_log"] == []
        assert task["completed_runs"] == 5
        assert task["runs"] == 5
        assert task["schedule"]["words"] == "At 09:03 every day"
        assert body["task_file"] == {
            "name": "documentation-summary.md",
            "content": "# Documentation summary\n\nLorem ipsum dolor sit amet, every morning.\n",
            "truncated": False,
        }
        assert body["sources"] == {"broker": {"ok": True, "errors": {}}}

    def test_the_full_prompt_comes_from_tasks_get(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        series = "weekly-0273-fixture"
        long_prompt = "Lorem ipsum " * 40
        broker.data("tasks-get", {"id": series})["prompt"] = long_prompt
        broker.set("task-file", {"file": None}, {"id": series})
        body = client.get(f"/api/tasks/{series}", headers=auth).json()
        assert body["task"]["prompt"] == long_prompt
        assert body["task"]["recent_log"] == ["Lorem ipsum dolor sit amet 187"]
        assert body["task_file"] is None
        assert body["sources"]["broker"]["ok"] is True

    def test_a_broker_without_task_file_still_answers(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        broker.fail("task-file", "unknown_verb")
        body = client.get(f"/api/tasks/{PAUSED[1]}", headers=auth).json()
        assert body["task"]["id"] == PAUSED[1]
        assert body["task_file"] is None
        assert body["sources"]["broker"] == {"ok": False, "errors": {"task-file": "unknown_verb"}}

    def test_a_task_not_in_the_list_is_built_from_tasks_get(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        series = "check-0271-fixture"
        broker.set("tasks-list", [t for t in broker.data("tasks-list") if t["series_id"] != series])
        broker.set("task-file", {"file": None}, {"id": series})
        body = client.get(f"/api/tasks/{series}", headers=auth).json()
        task = body["task"]
        assert task["id"] == series
        assert task["runs"] == 1  # completed_runs
        assert task["last_run_at"] is None
        assert task["next_run_at"] == "2026-11-09T06:01:00.000Z"

    def test_a_failed_tasks_get_still_shows_the_listed_task(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        broker.fail("tasks-get", "timeout")
        body = client.get(f"/api/tasks/{PAUSED[0]}", headers=auth).json()
        assert body["task"]["id"] == PAUSED[0]
        assert body["task"]["overdue_on_resume"] is True
        assert body["task"]["recent_log"] == []
        assert body["task"]["completed_runs"] is None
        assert body["sources"]["broker"] == {"ok": False, "errors": {"tasks-get": "timeout"}}

    def test_unknown_task_is_404(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        response = client.get("/api/tasks/task-0000-nope", headers=auth)
        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    @pytest.mark.parametrize("bad", ["-task", "a" * 81, "task_1", "task.1", "task%201"])
    def test_an_id_that_is_not_an_id_is_404_without_asking_the_broker(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker, bad: str
    ) -> None:
        response = client.get(f"/api/tasks/{bad}", headers=auth)
        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}
        assert broker.requests == []

    def test_broker_down_is_503(
        self, client: TestClient, auth: dict[str, str], broker: FakeBroker
    ) -> None:
        broker.stop()
        response = client.get(f"/api/tasks/{PAUSED[0]}", headers=auth)
        assert response.status_code == 503
        assert response.json() == {"error": "broker_unavailable", "code": "unavailable"}
