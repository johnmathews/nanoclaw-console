"""The scaffold's routes: the healthcheck, the overview placeholder and the built SPA."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nanoclaw_console.app import create_app, create_app_from_env


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(static_dir=None)) as c:
        yield c


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html><title>NanoClaw console</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    return tmp_path


@pytest.fixture
def spa(static_dir: Path) -> Iterator[TestClient]:
    with TestClient(create_app(static_dir=static_dir)) as c:
        yield c


def test_healthz_returns_only_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_overview_is_a_placeholder(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    assert response.json() == {"status": "scaffold"}


def test_unknown_api_path_is_404_without_static(client: TestClient) -> None:
    assert client.get("/api/nope").status_code == 404


def test_no_static_dir_serves_no_root(client: TestClient) -> None:
    assert client.get("/").status_code == 404


def test_spa_serves_index_at_root(spa: TestClient) -> None:
    response = spa.get("/")
    assert response.status_code == 200
    assert "NanoClaw console" in response.text


def test_spa_serves_built_files(spa: TestClient) -> None:
    response = spa.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_spa_falls_back_to_index_for_client_routes(spa: TestClient) -> None:
    response = spa.get("/tasks/some-task")
    assert response.status_code == 200
    assert "NanoClaw console" in response.text


def test_spa_does_not_hide_unknown_api_paths(spa: TestClient) -> None:
    """A typo in an API path is a 404, not the SPA's HTML with a 200."""
    assert spa.get("/api/nope").status_code == 404


def test_spa_keeps_healthz(spa: TestClient) -> None:
    assert spa.get("/healthz").json() == {"ok": True}


def test_spa_refuses_traversal(spa: TestClient, static_dir: Path) -> None:
    (static_dir.parent / "secret.txt").write_text("not for you")
    response = spa.get("/..%2Fsecret.txt")
    assert "not for you" not in response.text


def test_missing_static_dir_is_ignored(tmp_path: Path) -> None:
    with TestClient(create_app(static_dir=tmp_path / "absent")) as c:
        assert c.get("/healthz").json() == {"ok": True}
        assert c.get("/").status_code == 404


def test_create_app_from_env_reads_static_dir(
    monkeypatch: pytest.MonkeyPatch, static_dir: Path
) -> None:
    monkeypatch.setenv("STATIC_DIR", str(static_dir))
    with TestClient(create_app_from_env()) as c:
        assert "NanoClaw console" in c.get("/").text


def test_create_app_from_env_defaults_to_app_static(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATIC_DIR", raising=False)
    with TestClient(create_app_from_env()) as c:
        # /app/static does not exist on a developer machine, so only the API routes exist.
        assert c.get("/healthz").json() == {"ok": True}
