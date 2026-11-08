"""Shared fixtures: a fake broker on a real Unix socket, a fake Loki, Access keys, and the app.

The app is built with a fixed clock (`NOW`, a few minutes after the broker fixture was captured),
so derived fields such as "overdue on resume" are deterministic.
"""

import shutil
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from nanoclaw_console.app import Services, create_app
from nanoclaw_console.config import Settings
from tests.fake_broker import FakeBroker
from tests.fake_loki import LOKI_URL, FakeLoki
from tests.jwt_helpers import AUD, EMAIL, TEAM, FakeCerts, Signer

NOW = datetime(2026, 11, 8, 14, 30, tzinfo=UTC)
SIGNER = Signer("console-k1")
ORIGIN = "https://nanoclaw.itsa-pizza.com"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def short_dir() -> Iterator[Path]:
    """A short directory: macOS caps a Unix socket path at 104 bytes, and tmp_path is long."""
    d = Path(tempfile.mkdtemp(prefix="ncc-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def broker(short_dir: Path) -> Iterator[FakeBroker]:
    fake = FakeBroker(short_dir / "broker.sock")
    fake.start()
    try:
        yield fake
    finally:
        fake.stop()


@pytest.fixture
def loki() -> FakeLoki:
    return FakeLoki(now=NOW)


@pytest.fixture
def certs() -> FakeCerts:
    return FakeCerts(SIGNER)


@pytest.fixture
def audit_dir(tmp_path: Path) -> Path:
    d = tmp_path / "audit"
    d.mkdir()
    return d


def make_settings(socket: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "access_team_domain": TEAM,
        "access_aud": AUD,
        "allowed_emails": frozenset({EMAIL}),
        "loki_url": LOKI_URL,
        "broker_socket": socket,
        "timezone": ZoneInfo("Europe/Amsterdam"),
        "static_dir": None,
        "console_origin": ORIGIN,
        "audit_dir": Path("/nonexistent/audit"),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


AppFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(
    broker: FakeBroker, loki: FakeLoki, certs: FakeCerts, audit_dir: Path
) -> Iterator[AppFactory]:
    clients: list[TestClient] = []

    def factory(**overrides: object) -> TestClient:
        settings = make_settings(broker.path, **{"audit_dir": audit_dir, **overrides})
        services = Services.build(
            settings,
            jwks_transport=certs.transport(),
            loki_transport=loki.transport(),
            clock=lambda: NOW,
        )
        client = TestClient(create_app(settings, services=services))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Cf-Access-Jwt-Assertion": SIGNER.token()}


@pytest.fixture
def client(make_client: AppFactory) -> TestClient:
    return make_client()
