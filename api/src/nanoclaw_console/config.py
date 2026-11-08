"""The console's settings, read once from the environment (docs/development.md §7).

The Access settings may be empty: the verifier then refuses every request (fail closed), which is
safer than refusing to start. A malformed `LOKI_URL`, `CONSOLE_ORIGIN` or an unknown
`NANOCLAW_TIMEZONE` is a deployment mistake and stops the console at start. An `AUDIT_DIR` that
cannot be written does not: the four actions then refuse (fail closed) and the views still work.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_BROKER_SOCKET = Path("/run/nanoclaw-console/broker.sock")
DEFAULT_STATIC_DIR = Path("/app/static")
DEFAULT_TIMEZONE = "Europe/Amsterdam"
DEFAULT_CONSOLE_ORIGIN = "https://nanoclaw.itsa-pizza.com"
DEFAULT_AUDIT_DIR = Path("/var/lib/nanoclaw-console/audit")

_EMAIL_SEPARATORS = re.compile(r"[\s,]+")


@dataclass(frozen=True)
class Settings:
    access_team_domain: str
    access_aud: str
    allowed_emails: frozenset[str]
    loki_url: str | None
    broker_socket: Path
    timezone: ZoneInfo
    static_dir: Path | None
    console_origin: str
    audit_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        return cls(
            access_team_domain=env.get("ACCESS_TEAM_DOMAIN", "").strip(),
            access_aud=env.get("ACCESS_AUD", "").strip(),
            allowed_emails=frozenset(
                e.lower() for e in _EMAIL_SEPARATORS.split(env.get("ALLOWED_EMAILS", "")) if e
            ),
            loki_url=_loki_url(env.get("LOKI_URL", "")),
            broker_socket=Path(env.get("BROKER_SOCKET", "") or DEFAULT_BROKER_SOCKET),
            timezone=_timezone(env.get("NANOCLAW_TIMEZONE", "") or DEFAULT_TIMEZONE),
            static_dir=Path(env.get("STATIC_DIR", "") or DEFAULT_STATIC_DIR),
            console_origin=_origin(env.get("CONSOLE_ORIGIN", "").strip() or DEFAULT_CONSOLE_ORIGIN),
            audit_dir=Path(env.get("AUDIT_DIR", "").strip() or DEFAULT_AUDIT_DIR),
        )


def _loki_url(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("LOKI_URL must be an http:// or https:// URL with a host")
    return value.rstrip("/")


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"NANOCLAW_TIMEZONE {name!r} is not a known IANA zone") from None


def _origin(value: str) -> str:
    """A bare origin, `scheme://host[:port]`: what a browser sends as `Origin`, compared exactly."""
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        port = None
        value = ""
    bare = f"{parts.scheme}://{parts.hostname}" + (f":{port}" if port is not None else "")
    if parts.scheme not in ("http", "https") or not parts.hostname or value != bare:
        raise ValueError(
            "CONSOLE_ORIGIN must be a bare origin, like https://nanoclaw.itsa-pizza.com"
        )
    return value
