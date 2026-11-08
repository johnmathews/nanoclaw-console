"""`usage`: ncl returns pre-rendered text, not fields (docs/architecture.md §3.8).

NanoClaw's `getUsageText` (src/usage.ts, 479a9510) renders one section per rate-limit bucket:

    *Current week (all models)*
    ▓▓▓…░░░ 39% used
    Resets Nov 10, 9pm (Europe/Amsterdam)

This reads the "all models" week out of that text. It is the host's `~/.claude` login, not the
token NanoClaw's agents use (decision D6), so `source` says so.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SOURCE = "host ~/.claude login"
_HEADING = "*Current week (all models)*"
_PERCENT = re.compile(r"(?<!\d)(\d{1,3})% used")
_RESETS = re.compile(r"Resets (.+)")
_WHEN = re.compile(
    r"(?:(?P<month>[A-Z][a-z]{2}) (?P<day>\d{1,2}), )?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?P<ampm>am|pm) \((?P<zone>[A-Za-z0-9_+/-]{1,40})\)"
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}


def parse_usage(data: object, *, now: datetime | None = None) -> dict[str, object]:
    """`{weekly_pct, resets_at, resets_text, source}`; fields are null when not in the text."""
    out: dict[str, object] = {
        "weekly_pct": None,
        "resets_at": None,
        "resets_text": None,
        "source": SOURCE,
    }
    if not isinstance(data, str):
        return out
    section = _section(data)
    percent = next((m for line in section if (m := _PERCENT.search(line))), None)
    if percent is None or int(percent.group(1)) > 100:
        return out
    out["weekly_pct"] = int(percent.group(1))
    resets = next((m for line in section if (m := _RESETS.fullmatch(line))), None)
    if resets is not None:
        text = resets.group(1)
        out["resets_text"] = text
        out["resets_at"] = _reset_time(text, now)
    return out


def _section(text: str) -> list[str]:
    """The lines under the "all models" heading, up to the next blank line."""
    lines = text.splitlines()
    if _HEADING not in lines:
        return []
    rest = lines[lines.index(_HEADING) + 1 :]
    return rest[: rest.index("")] if "" in rest else rest


def _reset_time(text: str, now: datetime | None) -> str | None:
    match = _WHEN.fullmatch(text)
    if match is None:
        return None
    hour = int(match["hour"])
    minute = int(match["minute"] or 0)
    if not 1 <= hour <= 12 or minute > 59:
        return None
    hour = hour % 12 + (12 if match["ampm"] == "pm" else 0)
    try:
        zone = ZoneInfo(match["zone"])
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    local_now = (now or datetime.now(zone)).astimezone(zone)
    try:
        if match["month"] is None:  # NanoClaw prints only the time when the reset is today
            when = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            month = _MONTHS.get(match["month"])
            if month is None:
                return None
            when = datetime(local_now.year, month, int(match["day"]), hour, minute, tzinfo=zone)
            if when < local_now:  # a dated reset is the next occurrence of that date
                when = when.replace(year=when.year + 1)
    except ValueError:  # Feb 30; Feb 29 in a common year
        return None
    return when.isoformat()
