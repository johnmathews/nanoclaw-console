"""The four actions (docs/architecture.md §4.8): the CSRF guard, the broker call, the answer.

Every refusal here must leave the broker untouched: the tests assert no write verb was sent.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ORIGIN, SIGNER, AppFactory
from tests.fake_broker import FakeBroker
from tests.jwt_helpers import EMAIL

TASK = "task-1778399790530-fx0229"
GROUP = "ag-1779373702795-fx0001"
WRITES = {"tasks-pause", "tasks-resume", "tasks-run", "groups-restart"}

ACTIONS = [
    ("pause", f"/api/tasks/{TASK}/pause", "tasks-pause", TASK),
    ("resume", f"/api/tasks/{TASK}/resume", "tasks-resume", TASK),
    ("run", f"/api/tasks/{TASK}/run", "tasks-run", TASK),
    ("restart", f"/api/groups/{GROUP}/restart", "groups-restart", GROUP),
]
PATHS = [a[1] for a in ACTIONS]


def good_headers() -> dict[str, str]:
    """What the console's own page sends (src/lib/api.ts postAction)."""
    return {
        "Cf-Access-Jwt-Assertion": SIGNER.token(),
        "Content-Type": "application/json",
        "X-Console-Action": "1",
        "Origin": ORIGIN,
        "Sec-Fetch-Site": "same-origin",
        "Cf-Ray": "8c1d2e3f4a5b6c7d-AMS",
    }


def post(client: TestClient, path: str, *, body: bytes = b"{}", **headers: str | None) -> Any:
    sent = good_headers()
    for name, value in headers.items():
        key = name.replace("_", "-")
        if value is None:
            sent.pop(key, None)
        else:
            sent[key] = value
    return client.post(path, content=body, headers=sent)


def audit_lines(audit_dir: Path) -> list[dict[str, Any]]:
    path = audit_dir / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def writes_sent(broker: FakeBroker) -> list[str]:
    return [v for v in broker.verbs() if v in WRITES]


@pytest.fixture
def answering(broker: FakeBroker) -> FakeBroker:
    broker.set("tasks-pause", {"series_id": TASK, "touched": 1}, {"id": TASK})
    broker.set("tasks-resume", {"series_id": TASK, "touched": 1}, {"id": TASK})
    broker.set(
        "tasks-run",
        {"series_id": TASK, "row_id": f"{TASK}-run-ab12", "status": "pending"},
        {"id": TASK},
    )
    broker.set("groups-restart", {"restarted": 1, "rebuilt": False}, {"id": GROUP})
    broker.set("groups-list", [{"id": GROUP, "name": "main-group", "folder": "main"}])
    return broker


# --- the CSRF guard: every case refused, nothing sent -------------------------------------


REFUSALS: list[tuple[str, dict[str, Any], str]] = [
    ("no action header", {"X_Console_Action": None}, "action_header"),
    ("action header not 1", {"X_Console_Action": "true"}, "action_header"),
    ("no Origin", {"Origin": None}, "origin"),
    ("another Origin", {"Origin": "https://evil.example"}, "origin"),
    ("look-alike Origin", {"Origin": "https://nanoclaw.itsa-pizza.com.evil.example"}, "origin"),
    ("Origin with a path", {"Origin": f"{ORIGIN}/"}, "origin"),
    ("http Origin", {"Origin": "http://nanoclaw.itsa-pizza.com"}, "origin"),
    ("null Origin", {"Origin": "null"}, "origin"),
    ("cross-site", {"Sec_Fetch_Site": "cross-site"}, "fetch_site"),
    ("same-site", {"Sec_Fetch_Site": "same-site"}, "fetch_site"),
    ("no Sec-Fetch-Site", {"Sec_Fetch_Site": None}, "fetch_site"),
    ("typed by hand", {"Sec_Fetch_Site": "none"}, "fetch_site"),
    ("no Content-Type", {"Content_Type": None}, "content_type"),
    ("form-encoded", {"Content_Type": "application/x-www-form-urlencoded"}, "content_type"),
    ("multipart", {"Content_Type": "multipart/form-data; boundary=x"}, "content_type"),
    ("text/plain", {"Content_Type": "text/plain"}, "content_type"),
]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(("case", "headers", "reason"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_csrf_refusals_send_nothing_and_are_audited(
    make_client: AppFactory,
    answering: FakeBroker,
    audit_dir: Path,
    path: str,
    case: str,
    headers: dict[str, Any],
    reason: str,
) -> None:
    client = make_client()
    response = post(client, path, **headers)
    assert response.status_code == 403, case
    assert response.json() == {"result": "refused", "reason": reason}
    assert response.headers["cache-control"] == "no-store"
    assert writes_sent(answering) == []
    [line] = audit_lines(audit_dir)
    assert (line["email"], line["result"], line["reason"]) == (EMAIL, "refused", reason)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"action=pause",
        b"[]",
        b'"x"',
        b"null",
        b'{"id": "other"}',
        b'{"rebuild": true}',
        b"{",
        b"{}" + b" " * 2048,
    ],
)
def test_a_body_that_is_not_an_empty_json_object_is_refused(
    make_client: AppFactory, answering: FakeBroker, path: str, body: bytes
) -> None:
    response = post(make_client(), path, body=body)
    assert response.status_code == 403
    assert response.json() == {"result": "refused", "reason": "body"}
    assert writes_sent(answering) == []


@pytest.mark.parametrize("path", PATHS)
def test_no_jwt_is_a_bare_403_and_sends_nothing(
    make_client: AppFactory, answering: FakeBroker, audit_dir: Path, path: str
) -> None:
    response = post(make_client(), path, Cf_Access_Jwt_Assertion=None)
    assert response.status_code == 403
    assert response.content == b""
    assert writes_sent(answering) == []
    assert audit_lines(audit_dir) == []  # refused before the console knows who asked


@pytest.mark.parametrize("path", PATHS)
def test_a_jwt_for_someone_else_sends_nothing(
    make_client: AppFactory, answering: FakeBroker, path: str
) -> None:
    response = post(make_client(), path, Cf_Access_Jwt_Assertion=SIGNER.token(email="x@evil.io"))
    assert response.status_code == 403
    assert writes_sent(answering) == []


@pytest.mark.parametrize("path", PATHS)
def test_get_is_not_an_action(make_client: AppFactory, answering: FakeBroker, path: str) -> None:
    response = make_client().get(path, headers=good_headers())
    assert response.status_code in (404, 405)
    assert writes_sent(answering) == []


def test_the_origin_is_configurable(make_client: AppFactory, answering: FakeBroker) -> None:
    client = make_client(console_origin="http://localhost:5173")
    path = f"/api/tasks/{TASK}/pause"
    assert post(client, path).json()["reason"] == "origin"
    assert post(client, path, Origin="http://localhost:5173").status_code == 200


def test_content_type_with_a_charset_is_json(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    path = f"/api/tasks/{TASK}/pause"
    response = post(make_client(), path, Content_Type="application/json; charset=utf-8")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/tasks/--all/pause",
        "/api/tasks/a_b/run",
        f"/api/tasks/{'a' * 81}/resume",
        "/api/groups/-x/restart",
        "/api/groups/a.b/restart",
    ],
)
def test_an_id_that_is_not_an_id_is_404_and_sends_nothing(
    make_client: AppFactory, answering: FakeBroker, audit_dir: Path, path: str
) -> None:
    response = post(make_client(), path)
    assert response.status_code == 404
    assert response.json() == {"result": "refused", "reason": "bad_id"}
    assert writes_sent(answering) == []
    [line] = audit_lines(audit_dir)
    assert line["target"]["id"] is None  # a string that is not an id is never written down


@pytest.mark.parametrize(
    "path",
    [
        f"/api/tasks/{TASK}/delete",
        f"/api/tasks/{TASK}/update",
        f"/api/groups/{GROUP}/run",
        f"/api/groups/{GROUP}/pause",
        f"/api/tasks/{TASK}/restart",
    ],
)
def test_no_other_action_exists(make_client: AppFactory, answering: FakeBroker, path: str) -> None:
    response = post(make_client(), path)
    assert response.status_code in (404, 405)
    assert writes_sent(answering) == []


# --- what an action sends and answers ---------------------------------------------------


@pytest.mark.parametrize(("action", "path", "verb", "target"), ACTIONS)
def test_an_action_sends_its_verb_with_the_id_once_and_audits_it(
    make_client: AppFactory,
    answering: FakeBroker,
    audit_dir: Path,
    action: str,
    path: str,
    verb: str,
    target: str,
) -> None:
    response = post(make_client(), path)
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "done"
    assert body["action"] == action
    assert body["target"] == {"type": "group" if action == "restart" else "task", "id": target}
    assert body["at"].endswith("Z")
    sent = [r for r in answering.requests if r["verb"] in WRITES]
    assert sent == [{"verb": verb, "params": {"id": target}}]
    [line] = audit_lines(audit_dir)
    assert line["email"] == EMAIL
    assert line["action"] == action
    assert line["verb"] == verb
    assert line["target"] == body["target"]
    assert line["result"] == "done"
    assert line["cf_ray"] == "8c1d2e3f4a5b6c7d-AMS"
    assert line["at"] == body["at"]


def test_the_answer_carries_only_named_facts(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    answering.set(
        "tasks-run",
        {
            "series_id": TASK,
            "row_id": "r-1",
            "status": "pending",
            "prompt": "Bearer PLANTED-SECRET",
        },
        {"id": TASK},
    )
    response = post(make_client(), f"/api/tasks/{TASK}/run")
    assert response.json()["detail"] == {"row_id": "r-1"}
    assert "PLANTED-SECRET" not in response.text
    answering.set("groups-restart", {"restarted": 2, "rebuilt": False, "x": "y"}, {"id": GROUP})
    response = post(make_client(), f"/api/groups/{GROUP}/restart")
    assert response.json()["detail"] == {"restarted": 2}
    response = post(make_client(), f"/api/tasks/{TASK}/pause")
    assert response.json()["detail"] == {"touched": 1}


@pytest.mark.parametrize(
    ("code", "status", "result"),
    [
        ("already_in_state", 200, "already_in_state"),
        ("not_found", 404, "not_found"),
        ("no_live_run", 409, "no_live_run"),
        ("ncl_error", 502, "broker_error"),
        ("unavailable", 502, "broker_error"),
        ("timeout", 502, "broker_error"),
        ("unknown_verb", 502, "broker_error"),
    ],
)
def test_broker_answers_map_to_results(
    make_client: AppFactory,
    answering: FakeBroker,
    audit_dir: Path,
    code: str,
    status: int,
    result: str,
) -> None:
    answering.fail("tasks-pause", code)
    response = post(make_client(), f"/api/tasks/{TASK}/pause")
    assert response.status_code == status
    body = response.json()
    assert body["result"] == result
    assert body["code"] == (code if result == "broker_error" else None)
    assert "fake" not in response.text  # the broker's message text is never passed on
    [line] = audit_lines(audit_dir)
    assert (line["result"], line["code"]) == (result, body["code"])


def test_an_unknown_verb_is_how_an_old_broker_answers(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    """Rolling the broker back to release 1 leaves the buttons answering broker_error."""
    answering.fail("tasks-run", "unknown_verb")
    response = post(make_client(), f"/api/tasks/{TASK}/run")
    assert response.json() == {
        "result": "broker_error",
        "code": "unknown_verb",
        "action": "run",
        "target": {"type": "task", "id": TASK},
        "at": response.json()["at"],
        "detail": None,
    }


def test_restarting_a_group_that_is_not_listed_is_not_found(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    """ncl answers {restarted: 0} for any id, so the console checks the group exists first."""
    response = post(make_client(), "/api/groups/ag-not-a-group/restart")
    assert response.status_code == 404
    assert response.json()["result"] == "not_found"
    assert writes_sent(answering) == []


def test_restart_with_the_group_list_failing_sends_nothing(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    answering.fail("groups-list", "unavailable")
    response = post(make_client(), f"/api/groups/{GROUP}/restart")
    assert response.status_code == 502
    assert response.json()["code"] == "unavailable"
    assert writes_sent(answering) == []


def test_a_second_action_on_the_same_target_while_one_runs_is_busy(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    import threading

    client = make_client()
    answering.delay = 0.3
    results: list[int] = []
    path = f"/api/tasks/{TASK}/run"
    first = threading.Thread(target=lambda: results.append(post(client, path).status_code))
    first.start()
    import time

    time.sleep(0.1)
    second = post(client, path)
    first.join()
    assert second.status_code == 409
    assert second.json()["result"] == "busy"
    assert results == [200]
    assert writes_sent(answering) == ["tasks-run"]


# --- fail closed without an audit log ----------------------------------------------------


def test_an_unwritable_audit_directory_refuses_to_act(
    make_client: AppFactory, answering: FakeBroker, tmp_path: Path
) -> None:
    missing = tmp_path / "no-such-dir"
    client = make_client(audit_dir=missing)
    for path in PATHS:
        response = post(client, path)
        assert response.status_code == 503
        assert response.json()["result"] == "audit_unavailable"
    assert writes_sent(answering) == []


def test_a_read_only_audit_directory_refuses_to_act(
    make_client: AppFactory, answering: FakeBroker, tmp_path: Path
) -> None:
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        response = post(make_client(audit_dir=ro), f"/api/tasks/{TASK}/run")
    finally:
        ro.chmod(0o700)
    assert response.status_code == 503
    assert writes_sent(answering) == []


def test_every_attempt_is_also_on_stdout(
    make_client: AppFactory, answering: FakeBroker, capsys: pytest.CaptureFixture[str]
) -> None:
    client = make_client()
    post(client, f"/api/tasks/{TASK}/pause")
    post(client, f"/api/tasks/{TASK}/pause", Origin="https://evil.example")
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    audits = [x for x in lines if x.get("event") == "audit"]
    assert [a["result"] for a in audits] == ["done", "refused"]
    assert all(a["email"] == EMAIL for a in audits)


def test_an_unwritable_audit_still_reaches_stdout(
    make_client: AppFactory,
    answering: FakeBroker,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    post(make_client(audit_dir=tmp_path / "gone"), f"/api/tasks/{TASK}/run")
    out = capsys.readouterr().out
    assert '"result": "audit_unavailable"' in out


def test_a_failed_append_after_acting_says_so(
    make_client: AppFactory,
    answering: FakeBroker,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Disk full after the broker acted: the answer says the file missed it; stdout has it."""

    def full(fd: int, data: bytes) -> int:
        raise OSError(28, "No space left on device")

    client = make_client()
    monkeypatch.setattr("nanoclaw_console.audit.os.write", full)
    response = post(client, f"/api/tasks/{TASK}/pause")
    assert response.status_code == 500
    assert response.json()["result"] == "audit_failed"
    assert response.json()["acted_result"] == "done"
    assert '"result": "done"' in capsys.readouterr().out
    # A refusal that cannot be written is still refused.
    response = post(client, f"/api/tasks/{TASK}/pause", Origin="https://evil.example")
    assert response.status_code == 403


def test_a_broker_answer_that_is_not_an_object_has_no_detail(
    make_client: AppFactory, answering: FakeBroker
) -> None:
    answering.set("tasks-run", ["odd"], {"id": TASK})
    response = post(make_client(), f"/api/tasks/{TASK}/run")
    assert (response.status_code, response.json()["detail"]) == (200, None)


def test_a_refusal_without_an_audit_file_is_refused_and_on_stdout(
    make_client: AppFactory,
    answering: FakeBroker,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = make_client(audit_dir=tmp_path / "gone")
    response = post(client, f"/api/tasks/{TASK}/run", Sec_Fetch_Site="cross-site")
    assert response.status_code == 403
    assert '"reason": "fetch_site"' in capsys.readouterr().out
    assert writes_sent(answering) == []
