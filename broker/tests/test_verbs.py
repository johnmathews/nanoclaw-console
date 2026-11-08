"""The verb registry is the security boundary: only the release-1 reads, only id parameters."""

from typing import Any

import pytest

from nanoclaw_broker.errors import BrokerError
from nanoclaw_broker.verbs import REGISTRY, resolve
from tests.conftest import load_commands

RELEASE_1 = {
    "groups-list": ("groups-list", (), {}),
    "groups-get": ("groups-get", ("id",), {}),
    "groups-config-get": ("groups-config-get", ("id",), {}),
    "messaging-groups-list": ("messaging-groups-list", (), {}),
    "wirings-list": ("wirings-list", (), {}),
    "destinations-list": ("destinations-list", (), {}),
    "sessions-list": ("sessions-list", (), {}),
    "tasks-list": ("tasks-list", (), {"all": True}),
    "tasks-get": ("tasks-get", ("id",), {}),
    "roles-list": ("roles-list", (), {}),
    "members-list": ("members-list", (), {}),
    "policies-list": ("policies-list", (), {}),
    "approvals-list": ("approvals-list", (), {}),
    "users-list": ("users-list", (), {}),
    "dropped-messages-list": ("dropped-messages-list", (), {}),
}

# The run plan's W4 acceptance list: no registered command may contain one of these as a
# dash-separated segment (so `groups-config-set-env` is caught by `set`).
WRITE_SEGMENTS = {
    "create",
    "update",
    "delete",
    "add",
    "remove",
    "grant",
    "revoke",
    "set",
    "unset",
    "send",
    "connect",
    "pause",
    "resume",
    "run",
    "cancel",
    "restart",
    "append",
}

ALL_NCL_COMMANDS = load_commands()


def test_registry_is_exactly_release_1() -> None:
    assert set(REGISTRY) == set(RELEASE_1)
    for name, (command, params, fixed) in RELEASE_1.items():
        verb = REGISTRY[name]
        assert verb.name == name
        assert verb.command == command
        assert verb.params == params
        assert dict(verb.fixed_args) == fixed
        assert verb.cacheable


def test_registry_has_no_write_command() -> None:
    for verb in REGISTRY.values():
        segments = set(verb.command.split("-"))
        assert not segments & WRITE_SEGMENTS, verb.command


def test_every_registry_command_exists_in_ncl() -> None:
    """A rename upstream shows up here, against the captured `ncl help`."""
    for verb in REGISTRY.values():
        assert verb.command in ALL_NCL_COMMANDS, verb.command


def test_registry_is_frozen() -> None:
    with pytest.raises(TypeError):
        REGISTRY["tasks-update"] = REGISTRY["tasks-get"]  # type: ignore[index]
    with pytest.raises(AttributeError):
        REGISTRY["tasks-get"].command = "tasks-update"  # type: ignore[misc]
    with pytest.raises(TypeError):
        REGISTRY["tasks-list"].fixed_args["script"] = "x"  # type: ignore[index]


@pytest.mark.parametrize("command", [c for c in ALL_NCL_COMMANDS if c not in RELEASE_1])
def test_every_other_ncl_command_is_refused(command: str) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve(command, {})
    assert exc.value.code == "unknown_verb"
    with pytest.raises(BrokerError) as exc:
        resolve(command, {"id": "abc"})
    assert exc.value.code == "unknown_verb"


def test_the_write_verbs_of_the_plan_are_in_the_refused_set() -> None:
    """The fixture really does contain the dangerous verbs the table test refuses."""
    for command in [
        "tasks-update",
        "tasks-create",
        "tasks-pause",
        "tasks-resume",
        "tasks-run",
        "tasks-cancel",
        "tasks-append-log",
        "groups-restart",
        "groups-config-set-env",
        "groups-config-add-mount",
        "roles-grant",
        "messaging-groups-send",
        "sessions-history",
        "groups-connect",
        "usage",
        "status",
    ]:
        assert command in ALL_NCL_COMMANDS
        assert command not in REGISTRY


@pytest.mark.parametrize(
    "verb",
    [
        "groups-get-abc",  # ncl's dash-prefix fallback would read this as groups-get, id abc
        "tasks-get-task-1",
        "GROUPS-LIST",
        "groups-list ",
        " groups-list",
        "groups_list",
        "groups list",
        "groups-list\n",
        "__proto__",
        "constructor",
        "",
        "help",
    ],
)
def test_near_miss_verb_names_are_refused(verb: str) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve(verb, {})
    assert exc.value.code == "unknown_verb"


@pytest.mark.parametrize("verb", [None, 1, 1.5, True, ["groups-list"], {"name": "groups-list"}])
def test_a_verb_that_is_not_a_string_is_refused(verb: object) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve(verb, {})
    assert exc.value.code == "unknown_verb"


@pytest.mark.parametrize(
    ("verb", "params"),
    [
        # Smuggling a command, raw args or a dangerous flag through params.
        ("groups-list", {"command": "tasks-update"}),
        ("groups-list", {"args": {"script": "x"}}),
        ("groups-list", {"id": "abc"}),
        ("groups-get", {"id": "abc", "command": "tasks-update"}),
        ("tasks-get", {"id": "abc", "script": "curl evil"}),
        ("tasks-get", {"id": "abc", "prompt": "do something else"}),
        ("tasks-get", {"id": "abc", "--script": "curl evil"}),
        ("tasks-get", {"id": "abc", "help": True}),
        ("tasks-list", {"all": False}),
        ("tasks-list", {"group": "abc"}),
        ("tasks-list", {"status": "paused"}),
        ("sessions-list", {"limit": "100000"}),
        # Missing the id.
        ("groups-get", {}),
        ("tasks-get", {}),
        ("groups-config-get", {"ID": "abc"}),
    ],
)
def test_unknown_or_missing_params_are_refused(verb: str, params: dict[str, Any]) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve(verb, params)
    assert exc.value.code == "invalid_params"


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "../x",
        "..",
        "/etc/passwd",
        "a/b",
        "a" * 81,
        "é",
        "grüp",
        "a b",
        "abc\n",
        "abc\x00",
        "a_b",
        "a.b",
        "a:b",
        "--script",
        "-abc",
        "abc;rm",
        chr(0xFF21) + "bc",  # a fullwidth A
        "١٢٣",  # Arabic-Indic digits: \d would match these, [0-9] must not
    ],
)
def test_ids_failing_the_pattern_are_refused(bad_id: str) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve("groups-get", {"id": bad_id})
    assert exc.value.code == "invalid_params"


@pytest.mark.parametrize("bad_value", [None, 1, True, ["abc"], {"id": "abc"}, 1.0])
def test_ids_that_are_not_strings_are_refused(bad_value: object) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve("tasks-get", {"id": bad_value})
    assert exc.value.code == "invalid_params"


@pytest.mark.parametrize("params", [None, [], "id=abc", 1, ["id", "abc"]])
def test_params_that_are_not_an_object_are_refused(params: object) -> None:
    with pytest.raises(BrokerError) as exc:
        resolve("groups-get", params)
    assert exc.value.code == "invalid_params"


@pytest.mark.parametrize(
    "good_id",
    ["a", "A" * 80, "task-1778399790530-f2euaw", "0b6f2b8e-1d2c-4c1e-9d55-6f1d1b0f3e2a", "main"],
)
def test_good_ids_pass_and_build_the_frame_args(good_id: str) -> None:
    verb, params = resolve("tasks-get", {"id": good_id})
    assert params == {"id": good_id}
    assert verb.build_args(params) == {"id": good_id}


def test_fixed_args_are_added_by_the_broker() -> None:
    verb, params = resolve("tasks-list", {})
    assert verb.build_args(params) == {"all": True}


def test_list_verbs_take_no_params_and_send_empty_args() -> None:
    for name, (_, params, fixed) in RELEASE_1.items():
        if params:
            continue
        verb, validated = resolve(name, {})
        assert validated == {}
        assert verb.build_args(validated) == fixed


def test_build_args_returns_a_fresh_dict() -> None:
    verb, params = resolve("tasks-list", {})
    args = verb.build_args(params)
    args["script"] = "x"
    assert verb.build_args(params) == {"all": True}
