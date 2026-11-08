"""The audit log (docs/architecture.md §4.9): one line per attempt, append-only, fail closed."""

import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nanoclaw_console.audit import AUDIT_FILE, AuditLog, AuditUnavailable
from tests.conftest import ORIGIN, SIGNER, AppFactory
from tests.fake_broker import FakeBroker
from tests.jwt_helpers import EMAIL

AT = datetime(2026, 11, 8, 14, 30, 0, 123000, tzinfo=UTC)


def entry(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "at": "2026-11-08T14:30:00.123Z",
        "email": EMAIL,
        "action": "pause",
        "verb": "tasks-pause",
        "target": {"type": "task", "id": "task-1"},
        "result": "done",
        "reason": None,
        "code": None,
        "detail": {"touched": 1},
        "cf_ray": None,
    }
    base.update(over)
    return base


def test_a_line_is_appended_and_echoed_to_stdout(tmp_path: Path) -> None:
    out = io.StringIO()
    log = AuditLog(tmp_path, stream=out)
    with log.open() as writer:
        writer.write(entry())
    with log.open() as writer:
        writer.write(entry(action="run", verb="tasks-run"))
    lines = (tmp_path / AUDIT_FILE).read_text().splitlines()
    assert [json.loads(x)["action"] for x in lines] == ["pause", "run"]
    echoed = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [e["event"] for e in echoed] == ["audit", "audit"]
    assert echoed[0]["email"] == EMAIL


def test_the_file_is_opened_append_only_and_private(tmp_path: Path) -> None:
    (tmp_path / AUDIT_FILE).write_text(json.dumps(entry(action="earlier")) + "\n")
    log = AuditLog(tmp_path, stream=io.StringIO())
    with log.open() as writer:
        writer.write(entry())
    lines = (tmp_path / AUDIT_FILE).read_text().splitlines()
    assert [json.loads(x)["action"] for x in lines] == ["earlier", "pause"]
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    with AuditLog(fresh, stream=io.StringIO()).open() as writer:
        writer.write(entry())
    assert (fresh / AUDIT_FILE).stat().st_mode & 0o777 == 0o600


def test_a_missing_directory_is_unavailable_and_says_so_on_stdout(tmp_path: Path) -> None:
    out = io.StringIO()
    log = AuditLog(tmp_path / "missing", stream=out)
    assert log.writable() is False
    with pytest.raises(AuditUnavailable):
        log.open()


def test_a_symlinked_audit_file_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.write_text("")
    os.symlink(target, tmp_path / AUDIT_FILE)
    with pytest.raises(AuditUnavailable):
        AuditLog(tmp_path, stream=io.StringIO()).open()
    assert target.read_text() == ""


def test_a_newline_in_a_value_cannot_forge_a_line(tmp_path: Path) -> None:
    with AuditLog(tmp_path, stream=io.StringIO()).open() as writer:
        writer.write(entry(reason='x\n{"result": "done"}'))
    assert len((tmp_path / AUDIT_FILE).read_text().splitlines()) == 1


def test_echo_without_a_file_still_reaches_stdout(tmp_path: Path) -> None:
    out = io.StringIO()
    AuditLog(tmp_path / "missing", stream=out).echo(entry(result="audit_unavailable"))
    assert json.loads(out.getvalue())["result"] == "audit_unavailable"


def test_recent_is_newest_first_capped_and_skips_broken_lines(tmp_path: Path) -> None:
    lines = [json.dumps(entry(detail={"touched": i})) for i in range(250)]
    lines.insert(240, "not json")
    lines.insert(245, json.dumps(["a", "list"]))
    (tmp_path / AUDIT_FILE).write_text("\n".join(lines) + "\n")
    recent = AuditLog(tmp_path, stream=io.StringIO()).recent(limit=200)
    assert recent.entries[0]["detail"] == {"touched": 249}
    assert len(recent.entries) == 200
    assert recent.truncated is True
    assert recent.available is True


def test_recent_reads_only_the_tail_of_a_large_file(tmp_path: Path) -> None:
    line = json.dumps(entry()) + "\n"
    (tmp_path / AUDIT_FILE).write_text(line * 20000)  # several MB
    recent = AuditLog(tmp_path, stream=io.StringIO(), max_read=64 * 1024).recent(limit=500)
    assert 0 < len(recent.entries) <= 500
    assert recent.truncated is True


def test_recent_of_no_file_is_empty_and_available(tmp_path: Path) -> None:
    recent = AuditLog(tmp_path, stream=io.StringIO()).recent()
    assert (recent.available, recent.entries, recent.truncated) == (True, [], False)


def test_a_symlink_or_a_directory_in_place_of_the_file_is_unavailable(tmp_path: Path) -> None:
    os.symlink(tmp_path / "elsewhere", tmp_path / AUDIT_FILE)
    assert AuditLog(tmp_path, stream=io.StringIO()).recent().available is False
    other = tmp_path / "other"
    (other / AUDIT_FILE).mkdir(parents=True)
    log = AuditLog(other, stream=io.StringIO())
    assert log.recent().available is False
    assert log.writable() is False


def test_recent_of_a_missing_directory_is_unavailable(tmp_path: Path) -> None:
    recent = AuditLog(tmp_path / "missing", stream=io.StringIO()).recent()
    assert (recent.available, recent.entries) == (False, [])


# --- GET /api/audit -------------------------------------------------------------------------


def act(client: TestClient, path: str, **extra: str) -> None:
    headers = {
        "Cf-Access-Jwt-Assertion": SIGNER.token(),
        "Content-Type": "application/json",
        "X-Console-Action": "1",
        "Origin": ORIGIN,
        "Sec-Fetch-Site": "same-origin",
        **extra,
    }
    client.post(path, content=b"{}", headers=headers)


def test_the_audit_view_lists_what_was_done_newest_first(
    make_client: AppFactory, broker: FakeBroker, auth: dict[str, str]
) -> None:
    task = "task-1778399790530-fx0229"
    broker.set("tasks-pause", {"series_id": task, "touched": 1}, {"id": task})
    client = make_client()
    act(client, f"/api/tasks/{task}/pause")
    act(client, f"/api/tasks/{task}/pause", Origin="https://evil.example")
    response = client.get("/api/audit", headers=auth)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["available"] is True
    assert body["writable"] is True
    assert body["generated_at"].endswith("Z")
    assert [e["result"] for e in body["entries"]] == ["refused", "done"]
    assert set(body["entries"][0]) == {
        "at",
        "email",
        "action",
        "target",
        "result",
        "reason",
        "code",
        "detail",
        "cf_ray",
    }


def test_the_audit_view_shows_only_named_fields(
    make_client: AppFactory, audit_dir: Path, auth: dict[str, str]
) -> None:
    planted = entry(
        extra="Bearer PLANTED-SECRET", detail={"touched": 1, "prompt": "PLANTED-SECRET"}
    )
    planted["target"]["note"] = "PLANTED-SECRET"
    (audit_dir / AUDIT_FILE).write_text(json.dumps(planted) + "\n")
    response = make_client().get("/api/audit", headers=auth)
    assert "PLANTED-SECRET" not in response.text
    assert response.json()["entries"][0]["detail"] == {"touched": 1}


def test_the_audit_view_says_when_the_log_cannot_be_read(
    make_client: AppFactory, tmp_path: Path, auth: dict[str, str]
) -> None:
    body = make_client(audit_dir=tmp_path / "missing").get("/api/audit", headers=auth).json()
    assert (body["available"], body["writable"], body["entries"]) == (False, False, [])


def test_the_audit_view_needs_the_jwt(make_client: AppFactory) -> None:
    response = make_client().get("/api/audit")
    assert response.status_code == 403
    assert response.content == b""
