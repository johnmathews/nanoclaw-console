"""Derived task fields (docs/architecture.md §4.6) and the console's one time format.

Every time the console emits is UTC ISO 8601 with milliseconds and `Z`, whatever form NanoClaw
used (`2026-11-08T13:37:45.983Z` from JSON fields, `2026-06-12 11:53:41` from SQLite defaults).
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cronsim import CronSim, CronSimError

ALIASES = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}
# The broker's rule (architecture.md §3.8): the prompt starts by naming the instructions file.
_TASK_FILE = re.compile(r"^Read /workspace/agent/tasks/([A-Za-z0-9._-]{1,80}\.md)\b")
# NanoClaw ids are <prefix>-<epoch ms>-<random>; a series id is its first occurrence's id.
_ID_TIME = re.compile(r"(?:^|-)(\d{13})(?:-|$)")
_EARLIEST = datetime(2020, 1, 1, tzinfo=UTC)


def parse_time(value: object) -> datetime | None:
    """A NanoClaw timestamp as an aware UTC datetime; anything unreadable is None."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:  # SQLite's CURRENT_TIMESTAMP form is UTC
            parsed = parsed.replace(tzinfo=UTC)
        # A time near year 1 or 9999 with an offset overflows on conversion (OverflowError):
        # unreadable, not a reason to fail the whole view (B24).
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("iso() needs an aware datetime, not a naive one")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def describe_schedule(recurrence: str | None, tz: ZoneInfo, now: datetime) -> dict[str, Any]:
    """The cron as NanoClaw has it, in words, with its next occurrence after `now`."""
    if recurrence is None:
        return {
            "cron": None,
            "words": "Once",
            "timezone": tz.key,
            "valid": True,
            "next_fire_at": None,
        }
    expr = ALIASES.get(recurrence.strip().lower(), recurrence)
    try:
        sim = CronSim(expr, now.astimezone(tz))
        words = sim.explain()
        next_fire = next(sim)
    except (CronSimError, ValueError, StopIteration):
        return {
            "cron": recurrence,
            "words": None,
            "timezone": tz.key,
            "valid": False,
            "next_fire_at": None,
        }
    return {
        "cron": recurrence,
        "words": words,
        "timezone": tz.key,
        "valid": True,
        "next_fire_at": iso(next_fire),
    }


def overdue_on_resume(status: object, process_after: datetime | None, now: datetime) -> bool:
    """F9: a paused task whose next run is already past runs once at once when resumed."""
    return status == "paused" and process_after is not None and process_after < now


def series_started_at(series_id: object, now: datetime) -> datetime | None:
    """The creation time a NanoClaw id carries, if it carries one that makes sense."""
    if not isinstance(series_id, str):
        return None
    match = _ID_TIME.search(series_id)
    if match is None:
        return None
    at = datetime.fromtimestamp(int(match.group(1)) / 1000, UTC)
    if not _EARLIEST <= at <= now + timedelta(days=1):
        return None
    return at


def task_file_name(prompt: object) -> str | None:
    if not isinstance(prompt, str):
        return None
    match = _TASK_FILE.match(prompt)
    if match is None:
        return None
    name = match.group(1)
    return None if name.startswith(".") else name
