"""Redaction rules, unit by unit. The end-to-end golden test lives in test_server.py."""

import json
from typing import Any

import pytest

from nanoclaw_broker.redact import (
    GROUP_CONFIG_KEYS,
    MASK,
    redact_group_config,
    redact_reply,
    reduce_url,
    strip_userinfo,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://mcp.example.com/path/x?token=abc#frag", "https://mcp.example.com"),
        ("http://172.17.0.1:8931/mcp", "http://172.17.0.1:8931"),
        ("https://user:pass@host.example:8443/a?b=c", "https://host.example:8443"),
        ("https://token@host.example", "https://host.example"),
        ("HTTPS://Host.Example.COM/A", "https://host.example.com"),
        ("http://[::1]:8080/x", "http://[::1]:8080"),
        ("http://[fe80::1]/x", "http://[fe80::1]"),
        ("ws://relay.local:9000/socket?key=1", "ws://relay.local:9000"),
        (
            "https://homeassistant.local/api/webhook/mcp_abc123/readonly",
            "https://homeassistant.local",
        ),
    ],
)
def test_reduce_url_keeps_scheme_host_and_port(url: str, expected: str) -> None:
    assert reduce_url(url) == expected


@pytest.mark.parametrize(
    "value",
    [
        "not a url",
        "/relative/path?token=x",
        "mailto:someone@example.com",
        "http://",
        "https://host:notaport/x",
        "https://host:99999/x",
        "",
        None,
        42,
        ["https://a.example"],
        {"url": "https://a.example"},
    ],
)
def test_reduce_url_masks_anything_without_a_usable_host(value: object) -> None:
    assert reduce_url(value) == MASK


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("see https://bob:secret@chat.example.com/room", "see https://•••@chat.example.com/room"),
        ("git+ssh://tok@github.com/x", "git+ssh://•••@github.com/x"),
        ("a http://u@h b https://v:w@i c", "a http://•••@h b https://•••@i c"),
        ("no userinfo https://host/x?y=z", "no userinfo https://host/x?y=z"),
        ("email bob@example.com stays", "email bob@example.com stays"),
    ],
)
def test_strip_userinfo(text: str, expected: str) -> None:
    assert strip_userinfo(text) == expected


def test_headers_and_env_values_are_masked_anywhere_keys_kept() -> None:
    data = {
        "a": {"headers": {"Authorization": "Bearer abc", "X-Key": "k"}},
        "rows": [{"env": {"TOKEN": "t", "PATH_X": "/p"}}],
    }
    out = redact_reply(data)
    assert out == {
        "a": {"headers": {"Authorization": MASK, "X-Key": MASK}},
        "rows": [{"env": {"TOKEN": MASK, "PATH_X": MASK}}],
    }


@pytest.mark.parametrize("value", ["Bearer abc", ["Bearer abc"], 5, None])
def test_headers_or_env_that_are_not_objects_are_masked_whole(value: object) -> None:
    assert redact_reply({"headers": value, "env": value}) == {"headers": MASK, "env": MASK}


def test_mcp_server_entries_keep_only_safe_fields() -> None:
    data: dict[str, Any] = {
        "mcp_servers": {
            "http-one": {
                "type": "http",
                "url": "https://u:p@mcp.example:8443/hook/secret?token=x",
                "headers": {"Authorization": "Bearer abc"},
                "token": "unknown-field-secret",
            },
            "stdio-one": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@pkg/server", "--api-key=abc"],
                "env": {"KEY": "v"},
            },
            "stdio-shell": {"command": "sh -c 'TOKEN=abc server'", "args": "not-a-list"},
            "weird": "not-an-object",
        }
    }
    out = redact_reply(data)
    assert out == {
        "mcp_servers": {
            "http-one": {
                "type": "http",
                "url": "https://mcp.example:8443",
                "headers": {"Authorization": MASK},
                "token": MASK,
            },
            "stdio-one": {
                "transport": "stdio",
                "command": "npx",
                "args": [MASK, MASK, MASK],
                "env": {"KEY": MASK},
            },
            "stdio-shell": {"command": MASK, "args": MASK},
            "weird": MASK,
        }
    }


def test_mcp_servers_that_is_not_an_object_is_masked() -> None:
    assert redact_reply({"mcp_servers": ["x"]}) == {"mcp_servers": MASK}


def test_mcp_type_that_is_not_a_string_is_masked() -> None:
    out = redact_reply({"mcp_servers": {"s": {"type": {"nested": "x"}}}})
    assert out == {"mcp_servers": {"s": {"type": MASK}}}


def test_url_keys_are_reduced_anywhere() -> None:
    data = {"url": "https://h.example/a?b", "webhook_url": "https://k.example/x?sig=1", "n": 1}
    assert redact_reply(data) == {
        "url": "https://h.example",
        "webhook_url": "https://k.example",
        "n": 1,
    }


def test_script_becomes_has_script() -> None:
    rows = [
        {"series_id": "a", "script": "curl x", "has_script": 1},
        {"series_id": "b", "script": None, "has_script": 0},
        {"series_id": "c", "script": ""},
        {"series_id": "d", "has_script": 1},
        {"series_id": "e", "has_script": 0},
    ]
    assert redact_reply(rows) == [
        {"series_id": "a", "has_script": True},
        {"series_id": "b", "has_script": False},
        {"series_id": "c", "has_script": False},
        {"series_id": "d", "has_script": True},
        {"series_id": "e", "has_script": False},
    ]


def test_payload_is_dropped() -> None:
    rows = [{"approval_id": "x", "payload": json.dumps({"frame": {"args": {"script": "s"}}})}]
    assert redact_reply(rows) == [{"approval_id": "x"}]


def test_userinfo_is_stripped_from_any_string() -> None:
    out = redact_reply({"name": "see https://bob:pw@chat.example/room", "list": ["http://t@h"]})
    assert out == {"name": "see https://•••@chat.example/room", "list": ["http://•••@h"]}


def test_scalars_pass_through() -> None:
    assert redact_reply([1, 2.5, True, None, "plain"]) == [1, 2.5, True, None, "plain"]


def test_redact_reply_does_not_mutate_its_input() -> None:
    data = {"headers": {"A": "b"}, "rows": [{"script": "x"}]}
    before = json.dumps(data)
    redact_reply(data)
    assert json.dumps(data) == before


def test_group_config_keeps_only_present_config_keys() -> None:
    cfg: dict[str, object] = dict.fromkeys(GROUP_CONFIG_KEYS)
    cfg["mcp_servers"] = {"s": {"type": "http", "headers": {"A": "secret"}}}
    cfg["env"] = {"ANTHROPIC_API_KEY": "secret"}
    cfg["something_new"] = "secret"
    out = redact_group_config(cfg)
    assert isinstance(out, dict)
    assert set(out) == set(GROUP_CONFIG_KEYS)
    assert "env" not in out
    assert out["mcp_servers"] == {"s": {"type": "http", "headers": {"A": MASK}}}


def test_group_config_keys_match_present_config() -> None:
    """NanoClaw 479a9510 src/cli/resources/groups.ts:74-94, presentConfig's keys."""
    assert (
        frozenset(
            {
                "agent_group_id",
                "provider",
                "model",
                "effort",
                "speed",
                "image_tag",
                "assistant_name",
                "max_messages_per_prompt",
                "skills",
                "mcp_servers",
                "packages_apt",
                "packages_npm",
                "additional_mounts",
                "cli_scope",
                "timezone",
                "updated_at",
            }
        )
        == GROUP_CONFIG_KEYS
    )


@pytest.mark.parametrize("value", [[], "x", None, 3])
def test_group_config_that_is_not_an_object_is_masked(value: object) -> None:
    assert redact_group_config(value) == MASK
