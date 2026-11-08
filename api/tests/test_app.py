"""The app's shape: the healthcheck, the built SPA behind the Access check, and the env factory."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nanoclaw_console.app import create_app_from_env
from tests.conftest import AppFactory


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html><title>NanoClaw console</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    return tmp_path


@pytest.fixture
def spa(make_client: AppFactory, static_dir: Path) -> TestClient:
    return make_client(static_dir=static_dir)


def test_healthz_returns_only_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unknown_api_path_is_404_without_static(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/api/nope", headers=auth).status_code == 404


def test_no_static_dir_serves_no_root(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/", headers=auth).status_code == 404


def test_no_interactive_docs(client: TestClient, auth: dict[str, str]) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=auth).status_code == 404


def test_spa_serves_index_at_root(spa: TestClient, auth: dict[str, str]) -> None:
    response = spa.get("/", headers=auth)
    assert response.status_code == 200
    assert "NanoClaw console" in response.text


def test_spa_serves_built_files(spa: TestClient, auth: dict[str, str]) -> None:
    response = spa.get("/assets/app.js", headers=auth)
    assert response.status_code == 200
    assert "console.log" in response.text


def test_spa_falls_back_to_index_for_client_routes(spa: TestClient, auth: dict[str, str]) -> None:
    response = spa.get("/tasks/some-task", headers=auth)
    assert response.status_code == 200
    assert "NanoClaw console" in response.text


def test_spa_does_not_hide_unknown_api_paths(spa: TestClient, auth: dict[str, str]) -> None:
    """A typo in an API path is a 404, not the SPA's HTML with a 200."""
    assert spa.get("/api/nope", headers=auth).status_code == 404
    assert spa.get("/api", headers=auth).status_code == 404


def test_spa_keeps_healthz(spa: TestClient) -> None:
    assert spa.get("/healthz").json() == {"ok": True}


def test_spa_refuses_traversal(spa: TestClient, static_dir: Path, auth: dict[str, str]) -> None:
    (static_dir.parent / "secret.txt").write_text("not for you")
    response = spa.get("/..%2Fsecret.txt", headers=auth)
    assert "not for you" not in response.text


def test_missing_static_dir_is_ignored(
    make_client: AppFactory, tmp_path: Path, auth: dict[str, str]
) -> None:
    c = make_client(static_dir=tmp_path / "absent")
    assert c.get("/healthz").json() == {"ok": True}
    assert c.get("/", headers=auth).status_code == 404


def test_create_app_from_env_reads_static_dir_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, static_dir: Path
) -> None:
    for name in ("ACCESS_TEAM_DOMAIN", "ACCESS_AUD", "ALLOWED_EMAILS", "LOKI_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STATIC_DIR", str(static_dir))
    with TestClient(create_app_from_env()) as c:
        assert c.get("/healthz").json() == {"ok": True}
        assert c.get("/").status_code == 403  # no Access settings: everything is refused


def test_create_app_from_env_defaults_to_app_static(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATIC_DIR", raising=False)
    with TestClient(create_app_from_env()) as c:
        assert c.get("/healthz").json() == {"ok": True}


def test_create_app_from_env_stops_on_a_bad_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NANOCLAW_TIMEZONE", "Mars/Olympus")
    with pytest.raises(ValueError, match="NANOCLAW_TIMEZONE"):
        create_app_from_env()
