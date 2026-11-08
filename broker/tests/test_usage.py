"""`usage` text -> fields (docs/architecture.md §3.8). Strings are as NanoClaw 479a9510 renders."""

from datetime import UTC, datetime

import pytest

from nanoclaw_broker.usage import SOURCE, parse_usage

# Captured from `ncl usage` on the agent host, 2026-11-08.
LIVE = (
    "*Current week (all models)*\n"
    "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 39% used\n"
    "Resets Nov 10, 9pm (Europe/Amsterdam)\n"
    "\n"
    "*Extra usage credits*\n"
    "Disabled (no reason given)"
)
NOW = datetime(2026, 11, 8, 14, 0, tzinfo=UTC)
NONE = {"weekly_pct": None, "resets_at": None, "resets_text": None, "source": SOURCE}


def test_the_live_string() -> None:
    assert parse_usage(LIVE, now=NOW) == {
        "weekly_pct": 39,
        "resets_at": "2026-11-10T21:00:00+01:00",
        "resets_text": "Nov 10, 9pm (Europe/Amsterdam)",
        "source": "host ~/.claude login",
    }


def test_the_default_clock_is_used_without_now() -> None:
    out = parse_usage(LIVE)
    assert isinstance(out, dict)
    assert out["weekly_pct"] == 39  # the date depends on today; the percentage does not


def test_other_buckets_do_not_stand_in_for_the_week() -> None:
    text = (
        "*Current session*\n▓░ 12% used\nResets 5pm (Europe/Amsterdam)\n\n"
        "*Current week (Opus only)*\n▓░ 80% used\nResets Nov 9, 1am (Europe/Amsterdam)\n\n"
        "*Current week (all models)*\n▓░ 7% used\nResets Nov 12, 6:30am (Europe/Amsterdam)"
    )
    out = parse_usage(text, now=NOW)
    assert isinstance(out, dict)
    assert out["weekly_pct"] == 7
    assert out["resets_at"] == "2026-11-12T06:30:00+01:00"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Resets 9pm (Europe/Amsterdam)", "2026-11-08T21:00:00+01:00"),  # a time alone is today
        ("Resets 9:30am (Europe/Amsterdam)", "2026-11-08T09:30:00+01:00"),
        ("Resets 12am (UTC)", "2026-11-08T00:00:00+00:00"),
        ("Resets 12pm (UTC)", "2026-11-08T12:00:00+00:00"),
        ("Resets Jan 3, 1am (UTC)", "2027-01-03T01:00:00+00:00"),  # already past this year
        ("Resets Dec 31, 11:59pm (America/New_York)", "2026-12-31T23:59:00-05:00"),
        ("Resets Nov 8, 11pm (UTC)", "2026-11-08T23:00:00+00:00"),
    ],
)
def test_reset_forms(line: str, expected: str) -> None:
    text = f"*Current week (all models)*\n▓░ 1% used\n{line}"
    out = parse_usage(text, now=NOW)
    assert isinstance(out, dict)
    assert out["resets_at"] == expected
    assert out["resets_text"] == line.removeprefix("Resets ")


@pytest.mark.parametrize(
    "line",
    [
        "Resets Nov 10, 9pm (Mars/Olympus)",  # zone the image does not know
        "Resets Nov 10, 9pm (../../etc/passwd)",
        "Resets Feb 30, 9pm (UTC)",
        "Resets Nov 10, 13pm (UTC)",
        "Resets Nov 10, 0am (UTC)",
        "Resets Nov 10, 9:61pm (UTC)",
        "Resets Foo 10, 9pm (UTC)",
        "Resets soon",
        "Resets tomorrow at nine (UTC)",
    ],
)
def test_a_reset_line_that_cannot_be_read_gives_null_but_keeps_the_text(line: str) -> None:
    text = f"*Current week (all models)*\n▓░ 39% used\n{line}"
    out = parse_usage(text, now=NOW)
    assert isinstance(out, dict)
    assert out["weekly_pct"] == 39
    assert out["resets_at"] is None
    assert out["resets_text"] == line.removeprefix("Resets ")


def test_a_week_with_no_reset_line() -> None:
    out = parse_usage("*Current week (all models)*\n▓░ 39% used", now=NOW)
    assert out == {**NONE, "weekly_pct": 39}


@pytest.mark.parametrize(
    "text",
    [
        "No usage data available.",
        "*Usage unavailable — OAuth token expired and refresh failed.*\n\nRun `claude setup-token`",
        "*Extra usage credits*\nDisabled (no reason given)",
        "*Current week (all models)*\nno percentage here",
        "*Current week (all models)*\n▓░ 140000% used",
        "",
    ],
)
def test_text_without_a_week_percentage_gives_nulls(text: str) -> None:
    assert parse_usage(text, now=NOW) == NONE


@pytest.mark.parametrize("data", [None, 39, {"weekly": 39}, ["x"], b"bytes"])
def test_data_that_is_not_text_gives_nulls(data: object) -> None:
    assert parse_usage(data, now=NOW) == NONE


def test_the_source_label_is_fixed() -> None:
    assert SOURCE == "host ~/.claude login"
