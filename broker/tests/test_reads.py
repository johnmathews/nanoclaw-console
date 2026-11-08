"""The four reads that are not ncl commands, and `usage`, through the broker's socket."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from nanoclaw_broker import probe as probe_module
from nanoclaw_broker import reads as reads_module
from nanoclaw_broker.safefs import MAX_FILE
from tests.conftest import FakeNcl, StartBroker, ask, frame_key

SERIES = "task-1778399790530-f2euaw"
GROUP = "ag-1779373702795-5wbiev"
PROMPT = "Read /workspace/agent/tasks/doc-summary.md and follow the instructions inside it."
OUTSIDE = "PLANTED-SECRET-outside-the-tasks-dir"


def ncl_says(fake: FakeNcl, command: str, args: dict[str, Any], data: object) -> None:
    fake.replies[frame_key(command, args)] = {"ok": True, "data": data}


def a_task(
    fake: FakeNcl, *, prompt: object = PROMPT, group: object = GROUP, folder: object = "main"
) -> None:
    ncl_says(fake, "tasks-get", {"id": SERIES}, {"agent_group_id": group, "prompt": prompt})
    ncl_says(fake, "groups-get", {"id": group}, {"id": group, "folder": folder, "name": "n"})


@pytest.fixture
def groups(short_dir: Path) -> Path:
    tasks = short_dir / "groups" / "main" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "doc-summary.md").write_text("# Summarise\n\nRead the docs and summarise.\n")
    return short_dir / "groups"


def refusals(run: Any) -> list[dict[str, Any]]:
    return [e for e in run.events() if e["event"] == "task_file_refused"]


# --- task-file ---------------------------------------------------------------------------------


async def test_task_file_returns_the_file_the_prompt_names(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    a_task(fake_ncl)
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {
        "ok": True,
        "data": {
            "name": "doc-summary.md",
            "content": "# Summarise\n\nRead the docs and summarise.\n",
            "truncated": False,
        },
    }
    # The broker builds both frames itself, from ids it was given or read from ncl.
    assert [(f["command"], f["args"]) for f in fake_ncl.frames] == [
        ("tasks-get", {"id": SERIES}),
        ("groups-get", {"id": GROUP}),
    ]


async def test_task_file_is_cached(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    a_task(fake_ncl)
    run = await start_broker(groups_dir=groups)
    for _ in range(2):
        await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert fake_ncl.calls() == 2
    assert [e["cache"] for e in run.events() if e["event"] == "request"] == ["miss", "hit"]


@pytest.mark.parametrize(
    "prompt",
    [
        "Do something else entirely",
        "Please Read /workspace/agent/tasks/doc-summary.md",
        " Read /workspace/agent/tasks/doc-summary.md",
        "Read /workspace/agent/tasks/../../../etc/passwd.md",
        "Read /workspace/agent/tasks/sub/x.md",
        "Read /workspace/agent/tasks//etc/x.md",
        "Read /workspace/agent/tasks/notes.txt",
        "Read /workspace/agent/tasks/" + "a" * 81 + ".md",
        "Read /workspace/other/tasks/doc-summary.md",
        "Read /workspace/agent/tasks/.md",
        "",
        None,
        42,
        ["Read /workspace/agent/tasks/doc-summary.md"],
    ],
)
async def test_a_prompt_that_does_not_name_a_task_file_gives_null_without_a_group_lookup(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path, prompt: object
) -> None:
    a_task(fake_ncl, prompt=prompt)
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert fake_ncl.calls("groups-get") == 0


async def test_a_prompt_naming_a_file_with_trailing_text_still_matches(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/doc-summary.md, then reply.")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply["data"]["name"] == "doc-summary.md"


async def test_a_missing_file_is_null_and_not_a_refusal(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/absent.md and go")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert refusals(run)[0]["reason"] == "missing"


@pytest.mark.parametrize("folder", ["../etc", "a/b", "", ".", "..", "/etc", 5, None, "x\x00y"])
async def test_a_folder_from_ncl_that_could_escape_is_refused(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path, folder: object
) -> None:
    (groups.parent / "etc" / "tasks").mkdir(parents=True)
    (groups.parent / "etc" / "tasks" / "doc-summary.md").write_text(OUTSIDE)
    a_task(fake_ncl, folder=folder)
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert OUTSIDE not in run.log.getvalue()
    assert refusals(run)[0]["reason"] == "bad_path"


async def test_a_symlinked_tasks_dir_is_refused(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    elsewhere = groups.parent / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "doc-summary.md").write_text(OUTSIDE)
    (groups / "planted").mkdir()
    (groups / "planted" / "tasks").symlink_to(elsewhere, target_is_directory=True)
    a_task(fake_ncl, folder="planted")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert refusals(run) == [
        {**refusals(run)[0], "id": SERIES, "reason": "symlink", "event": "task_file_refused"}
    ]
    assert OUTSIDE not in run.log.getvalue()


async def test_a_symlinked_group_dir_is_refused(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    (groups.parent / "elsewhere" / "tasks").mkdir(parents=True)
    (groups.parent / "elsewhere" / "tasks" / "doc-summary.md").write_text(OUTSIDE)
    (groups / "planted").symlink_to(groups.parent / "elsewhere", target_is_directory=True)
    a_task(fake_ncl, folder="planted")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert refusals(run)[0]["reason"] == "symlink"


async def test_a_symlinked_leaf_is_refused(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    secret = groups.parent / "secret.txt"
    secret.write_text(OUTSIDE)
    (groups / "main" / "tasks" / "link.md").symlink_to(secret)
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/link.md and go")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert refusals(run)[0]["reason"] == "symlink"
    assert OUTSIDE not in json.dumps(reply) + run.log.getvalue()


async def test_a_fifo_leaf_is_refused_without_hanging(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    os.mkfifo(groups / "main" / "tasks" / "pipe.md")
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/pipe.md and go")
    run = await start_broker(groups_dir=groups)
    reply = await asyncio.wait_for(
        ask(run.path, {"verb": "task-file", "params": {"id": SERIES}}), timeout=5
    )
    assert reply == {"ok": True, "data": {"file": None}}
    assert refusals(run)[0]["reason"] == "not_regular"


async def test_an_oversize_file_is_cut_at_256_kib(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    (groups / "main" / "tasks" / "big.md").write_text("x" * (MAX_FILE + 10))
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/big.md and go")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply["data"]["truncated"] is True
    assert len(reply["data"]["content"]) == MAX_FILE


async def test_file_content_is_masked_for_urls_with_userinfo_and_bearer_values(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    body = (
        "curl https://bot:PLANTED-SECRET-a@ss@api.example/x\n"
        "-H 'Authorization: Bearer PLANTED-SECRET-b'\n"
        "plain https://docs.example/page stays\n"
        "bad bytes: \xff\n"
    )
    (groups / "main" / "tasks" / "k.md").write_bytes(body.encode("latin-1"))
    a_task(fake_ncl, prompt="Read /workspace/agent/tasks/k.md and go")
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    content = reply["data"]["content"]
    assert "PLANTED-SECRET" not in content
    assert "curl https://•••@api.example/x" in content
    assert "Bearer •••" in content
    assert "https://docs.example/page stays" in content
    assert "�" in content


@pytest.mark.parametrize(
    ("tasks_get", "expect_group_lookup"),
    [
        ("not a dict", False),
        ({"prompt": PROMPT}, False),
        ({"prompt": PROMPT, "agent_group_id": "../x"}, False),
        ({"prompt": PROMPT, "agent_group_id": 7}, False),
    ],
)
async def test_a_task_record_that_is_not_usable_gives_null(
    start_broker: StartBroker,
    fake_ncl: FakeNcl,
    groups: Path,
    tasks_get: object,
    expect_group_lookup: bool,
) -> None:
    ncl_says(fake_ncl, "tasks-get", {"id": SERIES}, tasks_get)
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}
    assert (fake_ncl.calls("groups-get") > 0) is expect_group_lookup


async def test_a_group_record_that_is_not_an_object_gives_null(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    ncl_says(fake_ncl, "tasks-get", {"id": SERIES}, {"agent_group_id": GROUP, "prompt": PROMPT})
    ncl_says(fake_ncl, "groups-get", {"id": GROUP}, ["x"])
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply == {"ok": True, "data": {"file": None}}


async def test_an_unknown_task_is_the_fixed_ncl_error(
    start_broker: StartBroker, groups: Path
) -> None:
    run = await start_broker(groups_dir=groups)
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": "no-such-task"}})
    assert reply == {
        "ok": False,
        "error": {"code": "ncl_error", "message": "ncl rejected the request (handler-error)"},
    }


async def test_task_file_when_ncl_is_down_is_unavailable(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    run = await start_broker(groups_dir=groups)
    await fake_ncl.stop()
    reply = await ask(run.path, {"verb": "task-file", "params": {"id": SERIES}})
    assert reply["error"]["code"] == "unavailable"


async def test_concurrent_task_file_reads_do_not_deadlock_the_ncl_cap(
    start_broker: StartBroker, fake_ncl: FakeNcl, groups: Path
) -> None:
    """Each task-file read makes two ncl calls of its own; with 1 slot, none may hold it."""
    ids = [f"task-{n}" for n in range(4)]
    for sid in ids:
        ncl_says(fake_ncl, "tasks-get", {"id": sid}, {"agent_group_id": GROUP, "prompt": PROMPT})
    ncl_says(fake_ncl, "groups-get", {"id": GROUP}, {"id": GROUP, "folder": "main"})
    fake_ncl.delay = 0.02
    run = await start_broker(groups_dir=groups, max_inflight=1)
    replies = await asyncio.wait_for(
        asyncio.gather(*(ask(run.path, {"verb": "task-file", "params": {"id": s}}) for s in ids)),
        timeout=10,
    )
    assert all(r["ok"] and r["data"]["name"] == "doc-summary.md" for r in replies)
    assert fake_ncl.max_in_flight == 1


# --- mount-allowlist ---------------------------------------------------------------------------

ALLOWLIST = {
    "allowedRoots": [
        {"path": "~/projects", "allowReadWrite": True, "description": "Development projects"},
        {"path": "~/Documents", "description": "no allowReadWrite on this one"},
    ],
    "blockedPatterns": [".ssh", ".env"],
    "nonMainReadOnly": True,
}


async def test_mount_allowlist_is_returned_as_is(
    start_broker: StartBroker, fake_ncl: FakeNcl, short_dir: Path
) -> None:
    path = short_dir / "mount-allowlist.json"
    path.write_text(json.dumps(ALLOWLIST))
    run = await start_broker(mount_allowlist=path)
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply == {"ok": True, "data": ALLOWLIST}
    assert fake_ncl.frames == []


async def test_mount_allowlist_goes_through_the_common_redaction(
    start_broker: StartBroker, short_dir: Path
) -> None:
    path = short_dir / "m.json"
    path.write_text(json.dumps({"allowedRoots": [{"description": "https://u:p@ss@h.example/x"}]}))
    run = await start_broker(mount_allowlist=path)
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply["data"] == {"allowedRoots": [{"description": "https://•••@h.example/x"}]}


@pytest.mark.parametrize("content", [b"not json", b"[1]", b'"x"', b"", b"\xff", b"null"])
async def test_a_mount_allowlist_that_is_not_a_json_object_is_unavailable(
    start_broker: StartBroker, short_dir: Path, content: bytes
) -> None:
    path = short_dir / "m.json"
    path.write_bytes(content)
    run = await start_broker(mount_allowlist=path)
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply == {"ok": True, "data": {"available": False}}


async def test_a_missing_mount_allowlist_is_unavailable(
    start_broker: StartBroker, short_dir: Path
) -> None:
    run = await start_broker(mount_allowlist=short_dir / "absent.json")
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply == {"ok": True, "data": {"available": False}}


async def test_a_symlinked_mount_allowlist_is_refused(
    start_broker: StartBroker, short_dir: Path
) -> None:
    real = short_dir / "real.json"
    real.write_text(json.dumps(ALLOWLIST))
    link = short_dir / "link.json"
    link.symlink_to(real)
    run = await start_broker(mount_allowlist=link)
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply == {"ok": True, "data": {"available": False}}
    refused = [e for e in run.events() if e["event"] == "mount_allowlist_refused"]
    assert refused[0]["reason"] == "symlink"


async def test_an_oversize_mount_allowlist_is_unavailable(
    start_broker: StartBroker, short_dir: Path
) -> None:
    path = short_dir / "m.json"
    path.write_text(json.dumps({"allowedRoots": [], "pad": "x" * (MAX_FILE + 1)}))
    run = await start_broker(mount_allowlist=path)
    reply = await ask(run.path, {"verb": "mount-allowlist"})
    assert reply == {"ok": True, "data": {"available": False}}


# --- health, usage, claude-probe ---------------------------------------------------------------


async def test_health_uses_the_configured_port_and_is_cached_60_seconds(
    start_broker: StartBroker, fake_ncl: FakeNcl, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []

    async def fake_health(port: int, **_: Any) -> object:
        seen.append(port)
        return {"healthy": True}

    monkeypatch.setattr(reads_module, "fetch_health", fake_health)
    run = await start_broker(health_port=4321)
    for _ in range(2):
        reply = await ask(run.path, {"verb": "health"})
        assert reply == {"ok": True, "data": {"healthy": True}}
    assert seen == [4321]
    assert fake_ncl.frames == []


async def test_health_with_nothing_listening_is_unavailable_not_an_error(
    start_broker: StartBroker,
) -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    run = await start_broker(health_port=port)
    assert await ask(run.path, {"verb": "health"}) == {"ok": True, "data": {"available": False}}


async def test_usage_is_parsed_and_cached_five_minutes(
    start_broker: StartBroker, fake_ncl: FakeNcl
) -> None:
    run = await start_broker()
    first = await ask(run.path, {"verb": "usage"})
    second = await ask(run.path, {"verb": "usage"})
    assert first == second
    data = first["data"]
    assert data["weekly_pct"] == 39
    assert data["resets_text"] == "Nov 10, 9pm (Europe/Amsterdam)"
    assert data["source"] == "host ~/.claude login"
    assert set(data) == {"weekly_pct", "resets_at", "resets_text", "source"}
    assert fake_ncl.calls("usage") == 1
    assert [e["cache"] for e in run.events() if e["event"] == "request"] == ["miss", "hit"]


async def test_usage_failure_text_gives_nulls(start_broker: StartBroker, fake_ncl: FakeNcl) -> None:
    ncl_says(fake_ncl, "usage", {}, "*Usage unavailable — OAuth token expired.*")
    run = await start_broker()
    reply = await ask(run.path, {"verb": "usage"})
    assert reply["data"]["weekly_pct"] is None


async def test_claude_probe_is_passed_through_and_cached_five_minutes(
    start_broker: StartBroker, fake_ncl: FakeNcl, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def fake_run(self: Any) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"status": "ok", "http_status": 400, "checked_at": "2026-11-08T14:00:00+00:00"}

    monkeypatch.setattr(probe_module.ClaudeProbe, "run", fake_run)
    run = await start_broker(probe_agent_group="ag-test")
    for _ in range(2):
        reply = await ask(run.path, {"verb": "claude-probe"})
        assert reply["data"]["status"] == "ok"
    assert calls == 1
    assert fake_ncl.frames == []


async def test_claude_probe_with_onecli_down_is_unknown(
    start_broker: StartBroker,
) -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    run = await start_broker(onecli_url=f"http://127.0.0.1:{port}", probe_timeout=1)
    reply = await ask(run.path, {"verb": "claude-probe"})
    assert reply["ok"] is True
    assert (reply["data"]["status"], reply["data"]["http_status"]) == ("unknown", None)
