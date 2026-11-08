"""`/api/groups` (docs/architecture.md §4.7) against the fake broker."""

from typing import Any

from fastapi.testclient import TestClient

from tests.fake_broker import FakeBroker


def groups(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/groups", headers=auth)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def by_id(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in body["groups"]}


def test_every_group_is_listed(client: TestClient, auth: dict[str, str]) -> None:
    body = groups(client, auth)
    assert len(body["groups"]) == 15
    assert body["sources"] == {"broker": {"ok": True, "errors": {}}}
    assert [g["id"] for g in body["unwired_channels"]] == [
        "mg-0039-fixture",
        "mg-0057-fixture",
        "mg-0061-fixture",
    ]


def test_a_group_with_its_channel_tasks_and_sessions(
    client: TestClient, auth: dict[str, str]
) -> None:
    group = by_id(groups(client, auth))["ag-0026-fixture"]
    assert group["name"] == "Lorem ipsum dolor sit amet 13"
    assert group["folder"] == "id-0027-fixture"
    assert group["created_at"] == "2026-05-21T14:28:22.795Z"
    assert group["sessions"] == {"total": 28, "running": 3}
    assert group["tasks"] == {"total": 4, "paused": 2, "overdue_on_resume": 2}
    [channel] = group["channels"]
    assert channel["messaging_group_id"] == "mg-0047-fixture"
    assert channel["channel_type"] == "slack"
    assert channel["engage_mode"] == "pattern"
    assert channel["sender_scope"] == "all"
    assert channel["is_group"] is True
    assert set(channel) == {
        "wiring_id",
        "messaging_group_id",
        "name",
        "channel_type",
        "instance",
        "platform_id",
        "is_group",
        "engage_mode",
        "engage_pattern",
        "sender_scope",
        "ignored_message_policy",
        "unknown_sender_policy",
        "session_mode",
        "priority",
        "threads",
        "denied_at",
    }
    [dest] = group["destinations"]
    assert dest["target_type"] == "channel"
    assert dest["target_id"] == "mg-0047-fixture"
    assert dest["target_name"] is not None


def test_config_mcp_servers_show_names_never_values(
    client: TestClient, auth: dict[str, str]
) -> None:
    config = by_id(groups(client, auth))["ag-0022-fixture"]["config"]
    assert config["model"] == "claude-opus-4-7"
    servers = {s["name"]: s for s in config["mcp_servers"]}
    assert list(servers) == sorted(servers)
    assert servers["journal"] == {
        "name": "journal",
        "type": "http",
        "transport": None,
        "url": "https://mcp.example.internal:8443",
        "command": None,
        "header_names": ["Authorization", "X-Api-Key"],
        "env_names": [],
        "arg_count": 0,
    }
    assert servers["gmail"]["env_names"] == ["GMAIL_CREDENTIALS_PATH", "GMAIL_OAUTH_PATH"]
    assert servers["gmail"]["arg_count"] == 2
    assert servers["gmail"]["command"] == "•••"  # masked by the broker
    assert servers["calendar"]["command"] == "fixture-mcp-command"
    assert config["mounts"][0] == {
        "host_path": "Lorem ipsum dolor sit amet 150",
        "container_path": "Lorem ipsum dolor sit amet 151",
        "read_only": False,
    }


def test_secret_values_never_leave_the_console_even_unredacted(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    """Defence in depth: if the broker ever sent values, the console's field list drops them."""
    config = broker.data("groups-config-get", {"id": "ag-0022-fixture"})
    config["mcp_servers"]["journal"]["headers"]["Authorization"] = "Bearer PLANTED-SECRET-1"
    config["mcp_servers"]["gmail"]["env"]["GMAIL_OAUTH_PATH"] = "PLANTED-SECRET-2"
    config["mcp_servers"]["gmail"]["args"] = ["--key=PLANTED-SECRET-3"]
    config["mcp_servers"]["parallel-task"]["token"] = "PLANTED-SECRET-4"
    config["env"] = {"API_KEY": "PLANTED-SECRET-5"}
    response = client.get("/api/groups", headers=auth)
    assert "PLANTED-SECRET" not in response.text


def test_one_config_failing_spoils_only_that_group(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    del broker.replies['groups-config-get {"id": "ag-0010-fixture"}']
    body = groups(client, auth)
    assert by_id(body)["ag-0010-fixture"]["config"] is None
    assert by_id(body)["ag-0012-fixture"]["config"] is not None
    assert body["sources"]["broker"] == {"ok": False, "errors": {"groups-config-get": "ncl_error"}}


def test_broker_down_is_a_degraded_answer(
    client: TestClient, auth: dict[str, str], broker: FakeBroker
) -> None:
    broker.stop()
    body = groups(client, auth)
    assert body["groups"] == []
    assert body["unwired_channels"] == []
    assert body["sources"]["broker"]["ok"] is False
    assert body["sources"]["broker"]["errors"]["groups-list"] == "unavailable"
