"""The Access check on every route (docs/architecture.md §4.2, W6's JWT matrix).

Every request but `/healthz` needs a valid JWT; every refusal is a bare 403 with no body data,
on API routes, on the web app's static files and on unknown paths alike.
"""

import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.conftest import SIGNER, AppFactory
from tests.jwt_helpers import Signer

HEADER = "Cf-Access-Jwt-Assertion"
NOW = int(time.time())

ROUTES = [
    "/api/overview",
    "/api/groups",
    "/api/tasks",
    "/api/tasks/task-1778399790530-fx0229",
    "/api/permissions",
    "/api/problems",
    "/",
    "/assets/app.js",
    "/tasks/some-client-route",
    "/api/nope",
]

BAD_TOKENS: dict[str, str | None] = {
    "wrong aud": SIGNER.token(aud=["another-access-app"]),
    "wrong iss": SIGNER.token(iss="https://other-team.cloudflareaccess.com"),
    "expired": SIGNER.token(iat=NOW - 7200, nbf=NOW - 7200, exp=NOW - 3600),
    "wrong type": SIGNER.token(type="org"),
    "alg none": jwt.encode(
        SIGNER.claims(),
        key=None,  # type: ignore[arg-type]
        algorithm="none",
        headers={"kid": SIGNER.kid},
    ),
    "unknown kid": Signer("not-in-jwks").token(),
    "email not allowlisted": SIGNER.token(email="intruder@example.com"),
    "no header": None,
}


@pytest.fixture
def spa_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html><title>NanoClaw console</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    return tmp_path


@pytest.fixture
def spa(make_client: AppFactory, spa_dir: Path) -> TestClient:
    return make_client(static_dir=spa_dir)


def assert_bare_403(response: object) -> None:
    from httpx2 import Response

    assert isinstance(response, Response)
    assert response.status_code == 403
    assert response.content == b""
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("route", ROUTES)
def test_good_token_reaches_every_route(spa: TestClient, route: str) -> None:
    response = spa.get(route, headers={HEADER: SIGNER.token()})
    assert response.status_code != 403
    expected = 404 if route == "/api/nope" else 200
    assert response.status_code == expected


@pytest.mark.parametrize("case", list(BAD_TOKENS))
@pytest.mark.parametrize("route", ROUTES)
def test_bad_token_gets_bare_403_everywhere(spa: TestClient, route: str, case: str) -> None:
    token = BAD_TOKENS[case]
    headers = {} if token is None else {HEADER: token}
    assert_bare_403(spa.get(route, headers=headers))


def test_403_carries_no_view_data(spa: TestClient) -> None:
    response = spa.get("/api/tasks", headers={HEADER: BAD_TOKENS["wrong aud"] or ""})
    assert_bare_403(response)
    assert b"task-" not in response.content


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_other_methods_refused_without_token(spa: TestClient, method: str) -> None:
    assert_bare_403(spa.request(method, "/api/tasks"))


def test_healthz_needs_no_token(spa: TestClient) -> None:
    response = spa.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_healthz_ignores_a_bad_token(spa: TestClient) -> None:
    response = spa.get("/healthz", headers={HEADER: "garbage"})
    assert response.json() == {"ok": True}


@pytest.mark.parametrize("path", ["/healthz/", "/healthz/x", "/healthzz", "/api/healthz"])
def test_only_exact_healthz_is_open(spa: TestClient, path: str) -> None:
    assert_bare_403(spa.get(path))


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_aud": ""},
        {"allowed_emails": frozenset()},
        {"access_team_domain": ""},
        {"access_team_domain": "evil.example.com"},
    ],
)
def test_missing_config_fails_closed(make_client: AppFactory, overrides: dict[str, object]) -> None:
    client = make_client(**overrides)
    assert_bare_403(client.get("/api/overview", headers={HEADER: SIGNER.token()}))
    assert client.get("/healthz").json() == {"ok": True}


def test_verified_email_is_on_the_request(make_client: AppFactory) -> None:
    from fastapi import Request

    client = make_client()
    app = client.app

    @app.get("/api/_whoami")  # type: ignore[attr-defined, untyped-decorator]
    def whoami(request: Request) -> dict[str, str]:
        return {"email": request.state.access_email}

    response = client.get("/api/_whoami", headers={HEADER: SIGNER.token()})
    assert response.json() == {"email": "admin@example.com"}


def test_an_unexpected_error_in_the_check_is_a_403(
    make_client: AppFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bug in the verifier must close the door, not open it or leak a 500 page."""
    from nanoclaw_console.access import AccessVerifier

    async def broken(self: AccessVerifier, token: str | None) -> str:
        raise RuntimeError("bug")

    monkeypatch.setattr(AccessVerifier, "verify", broken)
    client = make_client()
    assert_bare_403(client.get("/api/overview", headers={HEADER: SIGNER.token()}))


def test_a_websocket_is_refused(spa: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as info, spa.websocket_connect("/ws"):
        pass
    assert info.value.code == 1008
