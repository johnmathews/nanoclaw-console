"""Derived task fields (docs/architecture.md §4.6) and the console's one time format."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nanoclaw_console.schedule import (
    describe_schedule,
    iso,
    overdue_on_resume,
    parse_time,
    series_started_at,
    task_file_name,
)
from tests.conftest import NOW

AMS = ZoneInfo("Europe/Amsterdam")


@pytest.mark.parametrize(
    ("cron", "words", "next_fire"),
    [
        ("3 9 * * *", "At 09:03 every day", "2026-11-09T08:03:00.000Z"),
        ("0 17 * * *", "At 17:00 every day", "2026-11-08T16:00:00.000Z"),
        (
            "7,22,37,52 * * * *",
            "At minutes 7, 22, 37, and 52 of every hour",
            "2026-11-08T14:37:00.000Z",
        ),
        ("0 9 * * 1", "At 09:00 on Monday", "2026-11-09T08:00:00.000Z"),
        ("10 7 * * 0,3", "At 07:10 on Sunday and Wednesday", "2026-11-11T06:10:00.000Z"),
        ("@daily", "At 00:00 every day", "2026-11-08T23:00:00.000Z"),
        ("@hourly", "At the start of every hour", "2026-11-08T15:00:00.000Z"),
    ],
)
def test_cron_in_words_and_next_fire(cron: str, words: str, next_fire: str) -> None:
    schedule = describe_schedule(cron, AMS, NOW)
    assert schedule == {
        "cron": cron,
        "words": words,
        "timezone": "Europe/Amsterdam",
        "valid": True,
        "next_fire_at": next_fire,
    }


def test_next_fire_matches_nanoclaws_process_after() -> None:
    """The fixture's `0 9 * * 1` task has process_after 2026-11-09T08:00Z (09:00 CET)."""
    assert describe_schedule("0 9 * * 1", AMS, NOW)["next_fire_at"] == "2026-11-09T08:00:00.000Z"


def test_next_fire_across_the_dst_change() -> None:
    """09:03 Amsterdam is 07:03 UTC in summer and 08:03 UTC in winter."""
    before_change = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    assert describe_schedule("3 9 * * *", AMS, before_change)["next_fire_at"] == (
        "2026-10-25T08:03:00.000Z"
    )
    assert (
        describe_schedule("3 9 * * *", AMS, datetime(2026, 7, 1, tzinfo=UTC))["next_fire_at"]
        == "2026-07-01T07:03:00.000Z"
    )


@pytest.mark.parametrize("cron", ["bad", "61 * * * *", "* * *", "@reboot", ""])
def test_unreadable_cron_is_invalid(cron: str) -> None:
    schedule = describe_schedule(cron, AMS, NOW)
    assert schedule == {
        "cron": cron,
        "words": None,
        "timezone": "Europe/Amsterdam",
        "valid": False,
        "next_fire_at": None,
    }


def test_no_recurrence_is_once() -> None:
    assert describe_schedule(None, AMS, NOW) == {
        "cron": None,
        "words": "Once",
        "timezone": "Europe/Amsterdam",
        "valid": True,
        "next_fire_at": None,
    }


@pytest.mark.parametrize(
    ("status", "process_after", "expected"),
    [
        ("paused", NOW - timedelta(days=166), True),
        ("paused", NOW - timedelta(seconds=1), True),
        ("paused", NOW + timedelta(hours=1), False),
        ("paused", None, False),
        ("pending", NOW - timedelta(days=1), False),
        ("active", NOW - timedelta(days=1), False),
    ],
)
def test_overdue_on_resume(status: str, process_after: datetime | None, expected: bool) -> None:
    assert overdue_on_resume(status, process_after, NOW) is expected


@pytest.mark.parametrize(
    ("series_id", "expected"),
    [
        ("task-1778399790530-f2euaw", datetime(2026, 5, 10, 7, 56, 30, 530000, tzinfo=UTC)),
        ("ag-1779373702795-5wbiev", datetime(2026, 5, 21, 14, 28, 22, 795000, tzinfo=UTC)),
        ("check-0271-fixture", None),
        ("weekly-report", None),
        ("task-9999999999999-xx", None),  # in the future: not a creation time
        ("task-0000000000001-xx", None),  # 1970: not a NanoClaw id
        ("task-17783997905301-xx", None),  # 14 digits
    ],
)
def test_series_started_at_from_the_id(series_id: str, expected: datetime | None) -> None:
    assert series_started_at(series_id, NOW) == expected


@pytest.mark.parametrize(
    ("prompt", "name"),
    [
        (
            "Read /workspace/agent/tasks/documentation-summary.md and follow it.",
            "documentation-summary.md",
        ),
        ("Read /workspace/agent/tasks/morning_report.v2.md", "morning_report.v2.md"),
        ("Please Read /workspace/agent/tasks/x.md", None),  # must start the prompt
        ("Read /workspace/agent/tasks/../secret.md", None),
        ("Read /workspace/agent/tasks/notes.txt", None),
        ("Lorem ipsum", None),
        (None, None),
    ],
)
def test_task_file_name(prompt: str | None, name: str | None) -> None:
    assert task_file_name(prompt) == name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-08T13:37:45.983Z", "2026-11-08T13:37:45.983Z"),
        ("2026-06-12 11:53:41", "2026-06-12T11:53:41.000Z"),  # SQLite: UTC without a zone
        ("2026-11-10T21:00:00+01:00", "2026-11-10T20:00:00.000Z"),
        ("garbage", None),
        ("", None),
        (None, None),
        (17, None),
    ],
)
def test_times_are_normalised(value: object, expected: str | None) -> None:
    assert iso(parse_time(value)) == expected


def test_iso_of_a_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError, match="naive"):
        iso(datetime(2026, 1, 1))
