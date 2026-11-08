"""The console's settings, read once from the environment (docs/development.md §7).

The Access settings may be empty: the verifier then refuses every request (fail closed), which is
safer than refusing to start. A malformed `LOKI_URL` or an unknown `NANOCLAW_TIMEZONE` is a
deployment mistake and stops the console at start.
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
