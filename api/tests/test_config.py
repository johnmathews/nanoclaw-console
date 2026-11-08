"""Settings from the environment (docs/development.md §7)."""

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from nanoclaw_console.config import DEFAULT_BROKER_SOCKET, DEFAULT_STATIC_DIR, Settings


def test_defaults_with_an_empty_environment() -> None:
    s = Settings.from_env({})
    assert s.access_team_domain == ""
    assert s.access_aud == ""
    assert s.allowed_emails == frozenset()
    assert s.loki_url is None
    assert s.broker_socket == DEFAULT_BROKER_SOCKET == Path("/run/nanoclaw-console/broker.sock")
    assert s.timezone == ZoneInfo("Europe/Amsterdam")
    assert s.static_dir == DEFAULT_STATIC_DIR == Path("/app/static")


def test_every_variable_is_read() -> None:
    s = Settings.from_env(
        {
            "ACCESS_TEAM_DOMAIN": " team.cloudflareaccess.com ",
            "ACCESS_AUD": " abc123 ",
            "ALLOWED_EMAILS": "John@Example.com, other@example.com\nthird@example.com,,",
            "LOKI_URL": "http://192.168.2.106:3100/",
            "BROKER_SOCKET": "/run/x/b.sock",
            "NANOCLAW_TIMEZONE": "UTC",
            "STATIC_DIR": "/srv/web",
        }
    )
    assert s.access_team_domain == "team.cloudflareaccess.com"
    assert s.access_aud == "abc123"
    assert s.allowed_emails == frozenset(
        {"john@example.com", "other@example.com", "third@example.com"}
    )
    assert s.loki_url == "http://192.168.2.106:3100"
    assert s.broker_socket == Path("/run/x/b.sock")
    assert s.timezone == ZoneInfo("UTC")
    assert s.static_dir == Path("/srv/web")


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_loki_url_is_unset(value: str) -> None:
    assert Settings.from_env({"LOKI_URL": value}).loki_url is None


@pytest.mark.parametrize("value", ["192.168.2.106:3100", "ftp://loki", "http://", "loki"])
def test_bad_loki_url_stops_the_console(value: str) -> None:
    with pytest.raises(ValueError, match="LOKI_URL"):
        Settings.from_env({"LOKI_URL": value})


@pytest.mark.parametrize("value", ["Mars/Olympus", "../etc/passwd", "not a zone"])
def test_bad_timezone_stops_the_console(value: str) -> None:
    with pytest.raises(ValueError, match="NANOCLAW_TIMEZONE"):
        Settings.from_env({"NANOCLAW_TIMEZONE": value})
