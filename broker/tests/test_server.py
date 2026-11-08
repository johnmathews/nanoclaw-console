"""The broker end to end, through its own Unix socket, against the fake ncl server."""

import asyncio
import io
import json
import os
import socket
import stat
from pathlib import Path
from typing import Any

import pytest

from nanoclaw_broker import server as server_module
from nanoclaw_broker.events import EventLog
from nanoclaw_broker.redact import MASK
from nanoclaw_broker.server import BrokerConfig, serve
from nanoclaw_broker.verbs import REGISTRY, Verb
from tests.conftest import FakeNcl, StartBroker, ask, load_commands

# Every planted value contains one of these; the captured fakes contain the others.
FORBIDDEN = ["PLANTED-SECRET", "FAKE-TOKEN", "FAKE-ENV-VALUE", "Bearer", "user:", "bob:"]


def all_requests(frames: dict[str, Any]) -> list[dict[str, Any]]:
    """One request per allowlisted verb, and one per id for the verbs that take one."""
    requests: list[dict[str, Any]] = []
    for name, verb in REGISTRY.items():
        if not verb.params:
            requests.append({"verb": name, "params": {}})
            continue
        for e in frames["entries"]:
            if e["command"] == verb.command:
                requests.append({"verb": name, "params": {"id": e["args"]["id"]}})
    return requests


# --- redaction, end to end ---------------------------------------------------------------------


async def test_golden_no_planted_secret_in_any_response_or_log(
    start_broker: StartBroker, frames: dict[str, Any], fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    requests = all_requests(frames)
    assert len(requests) == 12 + 15 + 15 + 17
    replies = [await ask(run.path, r) for r in requests]
    assert all(r["ok"] for r in replies), [r for r in replies if not r["ok"]][:1]
    # Ask everything again: the cached copies must be just as clean.
    replies += [await ask(run.path, r) for r in requests]
    out = json.dumps(replies, ensure_ascii=False) + run.log.getvalue()
    for needle in FORBIDDEN:
        assert needle not in out, needle
    # The secrets were really there to leak: the fixture carries every one of them.
    raw = json.dumps(frames)
    for needle in FORBIDDEN:
        assert needle in raw, needle
    assert len(fake_ncl.frames) == len(requests)


async def test_planted_group_config_is_redacted_as_documented(
    start_broker: StartBroker, frames: dict[str, Any]
) -> None:
    run = await start_broker()
    request = {"verb": "groups-config-get", "params": {"id": frames["planted_group"]}}
    reply = await ask(run.path, request)
    cfg = reply["data"]
    assert "env" not in cfg
    assert "future_secret_field" not in cfg
    journal = cfg["mcp_servers"]["journal"]
    assert journal == {
        "headers": {"Authorization": MASK, "X-Api-Key": MASK},
        "type": "http",
        "url": "https://mcp.example.internal:8443",
    }
    gmail = cfg["mcp_servers"]["gmail"]
    assert gmail["env"] == {"GMAIL_CREDENTIALS_PATH": MASK, "GMAIL_OAUTH_PATH": MASK}
    assert gmail["args"] == [MASK, MASK]
    assert gmail["command"] == MASK
    assert cfg["mcp_servers"]["parallel-task"]["token"] == MASK


async def test_planted_task_shows_has_script_not_script(
    start_broker: StartBroker, frames: dict[str, Any]
) -> None:
    run = await start_broker()
    got = await ask(run.path, {"verb": "tasks-get", "params": {"id": frames["planted_task"]}})
    assert "script" not in got["data"]
    assert got["data"]["has_script"] is True
    listed = await ask(run.path, {"verb": "tasks-list"})
    assert all("script" not in row for row in listed["data"])
    assert all(isinstance(row["has_script"], bool) for row in listed["data"])
    assert listed["data"][0]["has_script"] is True


async def test_approvals_have_no_payload(start_broker: StartBroker) -> None:
    run = await start_broker()
    reply = await ask(run.path, {"verb": "approvals-list", "params": {}})
    assert reply["data"]
    assert all("payload" not in row for row in reply["data"])
    assert all("approval_id" in row for row in reply["data"])


async def test_unredacted_replies_match_ncl_exactly(
    start_broker: StartBroker, frames: dict[str, Any]
) -> None:
    """Data matching `ncl <verb> --json`, minus the redacted fields (W4 acceptance)."""
    run = await start_broker()
    by_command = {e["command"]: e for e in frames["entries"] if not e["args"].get("id")}
    for name in [
        "groups-list",
        "wirings-list",
        "destinations-list",
        "sessions-list",
        "roles-list",
        "members-list",
        "policies-list",
        "users-list",
        "dropped-messages-list",
    ]:
        reply = await ask(run.path, {"verb": name, "params": {}})
        assert reply == {"ok": True, "data": by_command[name]["reply"]["data"]}, name
    tasks = await ask(run.path, {"verb": "tasks-list", "params": {}})
    expected = by_command["tasks-list"]["reply"]["data"]
    assert len(tasks["data"]) == len(expected)
    for got, want in zip(tasks["data"], expected, strict=True):
        assert {k: v for k, v in got.items() if k != "has_script"} == {
            k: v for k, v in want.items() if k not in {"has_script", "script"}
        }


# --- the allowlist, end to end -----------------------------------------------------------------


async def test_every_non_allowlisted_command_is_refused_and_never_reaches_ncl(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    refused = [c for c in load_commands() if c not in REGISTRY]
    assert len(refused) == 64 - 16
    for command in refused:
        for params in ({}, {"id": "abc"}):
            reply = await ask(run.path, {"verb": command, "params": params})
            assert reply["ok"] is False
            assert reply["error"]["code"] == "unknown_verb"
    assert fake_ncl.frames == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"not json\n", "bad_request"),
        (b"[]\n", "bad_request"),
        (b'"groups-list"\n', "bad_request"),
        (b"\xff\xfe\n", "bad_request"),
        (b"{}\n", "bad_request"),
        (b'{"params": {}}\n', "bad_request"),
        (b'{"verb": "groups-list", "params": {}, "command": "tasks-update"}\n', "bad_request"),
        (b'{"verb": "groups-list", "args": {"script": "x"}}\n', "bad_request"),
        (b'{"command": "tasks-update", "args": {}}\n', "bad_request"),
        (b'{"id": "1", "command": "tasks-update", "args": {}}\n', "bad_request"),
        (b'{"verb": "tasks-update", "params": {"id": "abc"}}\n', "unknown_verb"),
        (b'{"verb": "groups-get", "params": null}\n', "invalid_params"),
        (b'{"verb": "groups-get", "params": {"id": "../etc"}}\n', "invalid_params"),
        (b'{"verb": "tasks-get", "params": {"id": "a", "script": "curl"}}\n', "invalid_params"),
        (b'{"verb": "tasks-get", "params": {"id": "--script"}}\n', "invalid_params"),
        (b'{"verb": "groups-list", "params": {}}{"verb": "tasks-update"}\n', "bad_request"),
    ],
)
async def test_malformed_and_smuggling_requests_are_refused(
    start_broker: StartBroker, fake_ncl: FakeNcl, payload: bytes, code: str
) -> None:
    run = await start_broker()
    reply = await ask(run.path, payload)
    assert reply["ok"] is False
    assert reply["error"]["code"] == code
    assert set(reply) == {"ok", "error"}
    assert set(reply["error"]) == {"code", "message"}
    assert fake_ncl.frames == []


async def test_params_may_be_left_out_for_a_verb_without_params(start_broker: StartBroker) -> None:
    run = await start_broker()
    reply = await ask(run.path, {"verb": "roles-list"})
    assert reply["ok"] is True


async def test_only_the_first_line_is_read(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    run = await start_broker()
    payload = b'{"verb": "roles-list"}\n{"verb": "tasks-update", "params": {"id": "x"}}\n'
    reply = await ask(run.path, payload)
    assert reply["ok"] is True
    await asyncio.sleep(0.05)
    assert [f["command"] for f in fake_ncl.frames] == ["roles-list"]


async def test_a_request_without_a_newline_is_read_at_eof(start_broker: StartBroker) -> None:
    run = await start_broker()
    reader, writer = await asyncio.open_unix_connection(str(run.path))
    writer.write(b'{"verb": "roles-list"}')
    writer.write_eof()
    reply = json.loads(await reader.readline())
    writer.close()
    assert reply["ok"] is True


async def test_an_empty_connection_gets_bad_request(start_broker: StartBroker) -> None:
    run = await start_broker()
    reader, writer = await asyncio.open_unix_connection(str(run.path))
    writer.write_eof()
    reply = json.loads(await reader.readline())
    writer.close()
    assert reply == {"ok": False, "error": {"code": "bad_request", "message": "empty request"}}


async def test_an_oversize_request_is_refused(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    run = await start_broker()
    big = json.dumps({"verb": "groups-get", "params": {"id": "a" * (70 * 1024)}}).encode() + b"\n"
    reply = await ask(run.path, big)
    assert reply["error"]["code"] == "request_too_large"
    assert fake_ncl.frames == []


async def test_a_request_just_under_the_cap_is_parsed(start_broker: StartBroker) -> None:
    run = await start_broker()
    pad = " " * (64 * 1024 - 100)
    reply = await ask(run.path, (pad + '{"verb": "roles-list"}\n').encode())
    assert reply["ok"] is True


async def test_a_slow_client_times_out(start_broker: StartBroker) -> None:
    run = await start_broker(read_timeout=0.05)
    reader, writer = await asyncio.open_unix_connection(str(run.path))
    writer.write(b'{"verb": ')
    await writer.drain()
    reply = json.loads(await reader.readline())
    writer.close()
    assert reply["error"]["code"] == "bad_request"


# --- ncl failures --------------------------------------------------------------------------------


async def test_ncl_down_is_unavailable(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    run = await start_broker()
    await fake_ncl.stop()
    reply = await ask(run.path, {"verb": "groups-list"})
    assert reply["error"]["code"] == "unavailable"
    await fake_ncl.start()
    assert (await ask(run.path, {"verb": "groups-list"}))["ok"] is True


async def test_ncl_restart_on_a_new_inode_is_picked_up(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    assert (await ask(run.path, {"verb": "roles-list"}))["ok"] is True
    await fake_ncl.restart()
    assert (await ask(run.path, {"verb": "users-list"}))["ok"] is True
    assert fake_ncl.calls() == 2


async def test_ncl_timeout(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    run = await start_broker(ncl_timeout=0.05)
    fake_ncl.delay = 2
    reply = await ask(run.path, {"verb": "groups-list"})
    assert reply["error"]["code"] == "timeout"


async def test_request_deadline_covers_queueing(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker(ncl_timeout=5, request_deadline=0.1)
    fake_ncl.delay = 1
    reply = await ask(run.path, {"verb": "groups-list"})
    assert reply["error"]["code"] == "timeout"


async def test_ncl_error_is_passed_on_with_its_code(start_broker: StartBroker) -> None:
    run = await start_broker()
    reply = await ask(run.path, {"verb": "groups-get", "params": {"id": "no-such-group"}})
    assert reply["error"]["code"] == "ncl_error"
    assert reply["error"]["message"] == "ncl rejected the request (handler-error)"


async def test_ncl_error_text_stays_out_of_the_reply_and_is_redacted_in_the_log(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        message = "boom https://u:PLANTED-SECRET-p@ss@h.example/x Bearer PLANTED-SECRET-b"
        error = {"code": "handler-error", "message": message}
        return (json.dumps({"id": frame["id"], "ok": False, "error": error}) + "\n").encode()

    fake_ncl.responder = responder
    run = await start_broker()
    reply = await ask(run.path, {"verb": "groups-get", "params": {"id": "abc"}})
    assert reply == {
        "ok": False,
        "error": {"code": "ncl_error", "message": "ncl rejected the request (handler-error)"},
    }
    event = run.events()[-1]
    assert event["outcome"] == "ncl_error"
    assert event["ncl_code"] == "handler-error"
    assert event["detail"] == "boom https://h.example Bearer •••"
    assert "PLANTED-SECRET" not in run.log.getvalue()


async def test_errors_are_not_cached(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    run = await start_broker()
    for _ in range(2):
        await ask(run.path, {"verb": "groups-get", "params": {"id": "no-such-group"}})
    assert fake_ncl.calls("groups-get") == 2


async def test_malformed_ncl_reply_is_protocol_error(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    async def responder(frame: dict[str, Any]) -> bytes:
        return b"garbage\n"

    fake_ncl.responder = responder
    run = await start_broker()
    reply = await ask(run.path, {"verb": "groups-list"})
    assert reply["error"]["code"] == "protocol_error"


async def test_oversize_ncl_reply_is_protocol_error(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker(max_reply=1024)
    reply = await ask(run.path, {"verb": "sessions-list"})
    assert reply["error"]["code"] == "protocol_error"


async def test_an_unexpected_failure_is_internal_and_logged_without_detail(
    start_broker: StartBroker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(verb: object, params: object) -> Any:
        raise RuntimeError("PLANTED-SECRET-in-exception")

    monkeypatch.setattr(server_module, "resolve", boom)
    run = await start_broker()
    reply = await ask(run.path, {"verb": "groups-list"})
    assert reply == {"ok": False, "error": {"code": "internal", "message": "internal error"}}
    assert "PLANTED-SECRET" not in run.log.getvalue()
    assert run.events()[-1]["error"] == "RuntimeError"


# --- cache and load, end to end -----------------------------------------------------------------


async def test_concurrent_identical_requests_share_one_ncl_call(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    fake_ncl.delay = 0.1
    replies = await asyncio.gather(*(ask(run.path, {"verb": "groups-list"}) for _ in range(10)))
    assert all(r["ok"] for r in replies)
    assert fake_ncl.calls("groups-list") == 1
    caches = sorted(e["cache"] for e in run.events() if e["event"] == "request")
    assert caches == ["miss"] + ["shared"] * 9


async def test_never_more_than_two_ncl_calls_in_flight(
    start_broker: StartBroker, fake_ncl: FakeNcl, frames: dict[str, Any]
) -> None:
    run = await start_broker()
    fake_ncl.delay = 0.05
    ids = [e["args"]["id"] for e in frames["entries"] if e["command"] == "groups-get"][:6]
    replies = await asyncio.gather(
        *(ask(run.path, {"verb": "groups-get", "params": {"id": i}}) for i in ids),
        *(ask(run.path, {"verb": n}) for n in ["roles-list", "users-list", "wirings-list"]),
    )
    assert all(r["ok"] for r in replies)
    assert fake_ncl.calls() == 9
    assert fake_ncl.max_in_flight == 2


async def test_repeat_within_ttl_is_a_hit_and_after_ttl_a_miss(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker(ttl=0.1)
    await ask(run.path, {"verb": "roles-list"})
    await ask(run.path, {"verb": "roles-list"})
    assert fake_ncl.calls() == 1
    await asyncio.sleep(0.15)
    await ask(run.path, {"verb": "roles-list"})
    assert fake_ncl.calls() == 2
    caches = [e["cache"] for e in run.events() if e["event"] == "request"]
    assert caches == ["miss", "hit", "miss"]


# --- the log ------------------------------------------------------------------------------------


async def test_request_events_carry_verb_ids_cache_outcome_and_duration(
    start_broker: StartBroker, frames: dict[str, Any]
) -> None:
    run = await start_broker()
    await ask(run.path, {"verb": "tasks-get", "params": {"id": frames["planted_task"]}})
    event = run.events()[-1]
    assert event["event"] == "request"
    assert event["verb"] == "tasks-get"
    assert event["params"] == {"id": frames["planted_task"]}
    assert event["cache"] == "miss"
    assert event["outcome"] == "ok"
    assert isinstance(event["duration_ms"], float)
    assert "data" not in event
    assert isinstance(event["ts"], str)


async def test_client_supplied_verb_names_are_not_logged(start_broker: StartBroker) -> None:
    run = await start_broker()
    await ask(run.path, {"verb": "PLANTED-SECRET-verb", "params": {"x": "PLANTED-SECRET-param"}})
    await ask(run.path, {"verb": "groups-get", "params": {"id": "PLANTED-SECRET-bad/id"}})
    log = run.log.getvalue()
    assert "PLANTED-SECRET" not in log
    events = run.events()
    assert events[-2]["verb"] is None
    assert events[-2]["outcome"] == "unknown_verb"
    assert events[-1]["verb"] == "groups-get"
    assert events[-1]["params"] is None
    assert events[-1]["outcome"] == "invalid_params"


async def test_start_and_stop_are_logged(start_broker: StartBroker) -> None:
    run = await start_broker()
    assert run.events()[0]["event"] == "listening"
    await run.broker.close()
    assert run.events()[-1]["event"] == "stopped"


# --- the socket ---------------------------------------------------------------------------------


async def test_socket_mode_and_group_are_applied(start_broker: StartBroker) -> None:
    run = await start_broker(socket_mode=0o660, socket_group=os.getgid())
    st = run.path.stat()
    assert stat.S_ISSOCK(st.st_mode)
    assert stat.S_IMODE(st.st_mode) == 0o660
    assert st.st_gid == os.getgid()


async def test_default_mode_is_0660_and_group_left_alone(start_broker: StartBroker) -> None:
    run = await start_broker()
    assert stat.S_IMODE(run.path.stat().st_mode) == 0o660


async def test_a_custom_mode_is_applied(start_broker: StartBroker) -> None:
    run = await start_broker(socket_mode=0o600)
    assert stat.S_IMODE(run.path.stat().st_mode) == 0o600


async def test_umask_is_restored_after_bind(start_broker: StartBroker) -> None:
    before = os.umask(0o022)
    os.umask(before)
    await start_broker()
    after = os.umask(0o022)
    os.umask(after)
    assert after == before


async def test_a_stale_socket_is_replaced(start_broker: StartBroker, short_dir: Path) -> None:
    stale = short_dir / "broker.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(stale))
    s.close()
    run = await start_broker()
    assert (await ask(run.path, {"verb": "roles-list"}))["ok"] is True


async def test_a_file_that_is_not_a_socket_is_refused(
    start_broker: StartBroker, short_dir: Path
) -> None:
    (short_dir / "broker.sock").write_text("keep me")
    with pytest.raises(FileExistsError):
        await start_broker()
    assert (short_dir / "broker.sock").read_text() == "keep me"


async def test_close_removes_the_socket(start_broker: StartBroker) -> None:
    run = await start_broker()
    await run.broker.close()
    assert not run.path.exists()
    await run.broker.close()  # idempotent


async def test_serve_runs_until_stopped(short_dir: Path, fake_ncl: FakeNcl) -> None:
    config = BrokerConfig(socket_path=short_dir / "b.sock", ncl_socket=fake_ncl.path)
    stop = asyncio.Event()
    log = io.StringIO()
    task = asyncio.create_task(serve(config, stop, events=EventLog(log)))
    for _ in range(100):
        if config.socket_path.exists():
            break
        await asyncio.sleep(0.01)
    assert (await ask(config.socket_path, {"verb": "roles-list"}))["ok"] is True
    stop.set()
    await asyncio.wait_for(task, 2)
    assert not config.socket_path.exists()


async def test_an_uncacheable_verb_is_never_stored(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    """The seam release 2's write verbs use (cacheable=False); no such verb exists in release 1."""
    run = await start_broker()
    verb = Verb(name="roles-list", command="roles-list", cacheable=False)
    for _ in range(2):
        data, cache = await run.broker._fetch(verb, {})
        assert cache == "none"
        assert isinstance(data, list)
    assert fake_ncl.calls("roles-list") == 2


def test_event_log_defaults_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    EventLog().emit("hello", n=1)
    line = json.loads(capsys.readouterr().out)
    assert line["event"] == "hello"
    assert line["n"] == 1
