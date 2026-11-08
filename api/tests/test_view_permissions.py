"""`/api/permissions` (docs/architecture.md §4.7) against the fake broker."""

from typing import Any

from fastapi.testclient import TestClient

from tests.fake_broker import FakeBroker


def permissions(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/permissions", headers=auth)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_roles_and_members_with_names(client: TestClient, auth: dict[str, str]) -> None:
    body = permissions(client, auth)
    assert body["roles"][0] == {
        "user_id": "slack-0277-fixture",
        "user_name": "Lorem ipsum dolor sit amet 115",
        "user_kind": "slack",
        "role": "owner",
        "scope": "global",
        "group": None,
        "granted_at": "2026-05-26T11:50:07.000Z",
        "granted_by": None,
    }
    assert body["members"][0] == {
        "user_id": "slack-0280-fixture",
        "user_name": "Lorem ipsum dolor sit amet 112",
        "user_kind": "slack",
        "group": {"id": "ag-0010-fixture", "name": "Lorem ipsum dolor sit amet 5"},
        "added_at": "2026-11-07T14:21:00.890Z",
        "added_by": "Lorem ipsum dolor sit amet 107",
    }
    assert body["policies"] == []
    assert body["sources"] == {"broker": {"ok": True, "errors": {}}}


def test_destinations_name_both_ends(client: TestClient, auth: dict[str, str]) -> None:
    dests = permissions(client, auth)["destinations"]
    assert len(dests) == 16
    first = dests[0]
    assert first["group"]["id"] == "id-0004-fixture"
    assert first["group"]["name"] is not None
    assert first["target_type"] == "channel"
    assert first["target_name"] is not None
    assert first["created_at"] == "2026-06-12T11:53:41.000Z"


def test_the_old_approval_is_stale(client: TestClient, auth: dict[str, str]) -> None:
    """F19: a pending approval from 2026-06-14 that nobody will act on."""
    [approval] = permissions(client, auth)["approvals"]
    assert approval == {
        "id": "appr-0283-fixture",
        "action": "cli_command",
        "title": "Lorem ipsum dolor sit amet 110",
        "status": "pending",
        "created_at": "2026-06-14T13:39:50.906Z",
        "expires_at": None,
        "age_days": 147,
        "stale": True,
        "group": None,
        "session_id": "sess-0100-fixture",
    }


def test_mount_allowlist(client: TestClient, auth: dict[str, str]) -> None:
    assert permissions(client, auth)["mount_allowlist"] == {
        "available": True,
        "allowed_roots": [
            {"path": "/srv/media/lorem", "read_write": False, "description": "Lorem ipsum 1"},
            {"path": "/srv/notes/ipsum", "read_write": True, "description": "Lorem ipsum 2"},
            {"path": "/srv/docs/dolor", "read_write": False, "description": "Lorem ipsum 3"},
        ],
        "blocked_patterns": [".ssh", ".env"],
        "non_main_read_only": True,
    }


def test_mount_allowlist_not_readable(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.set("mount-allowlist", {"available": False})
    assert permissions(client, auth)["mount_allowlist"] == {
        "available": False,
        "reason": "not_readable",
    }


def test_mount_allowlist_read_failed(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.fail("mount-allowlist", "unknown_verb")
    body = permissions(client, auth)
    assert body["mount_allowlist"] == {"available": False, "reason": "broker_error"}
    assert body["sources"]["broker"]["errors"] == {"mount-allowlist": "unknown_verb"}


def test_what_the_console_cannot_see(client: TestClient, auth: dict[str, str]) -> None:
    hidden = permissions(client, auth)["not_visible"]
    assert [h["what"] for h in hidden] == [
        "Per-group environment variables",
        "OneCLI secret assignments",
        "Egress lockdown",
    ]
    assert all(h["why"] for h in hidden)


def test_broker_down_is_a_degraded_answer(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.stop()
    body = permissions(client, auth)
    assert body["roles"] == body["members"] == body["approvals"] == body["destinations"] == []
    assert body["mount_allowlist"] == {"available": False, "reason": "broker_error"}
    assert len(body["not_visible"]) == 3
    assert body["sources"]["broker"]["ok"] is False
