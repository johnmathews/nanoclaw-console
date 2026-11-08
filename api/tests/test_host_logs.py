"""NanoClaw's host errors and warnings (docs/architecture.md §4.5)."""

import time
from datetime import timedelta

import pytest

from nanoclaw_console.host_logs import message_of, read_host_logs, sanitize_sample
from nanoclaw_console.loki import LokiClient
from tests.conftest import NOW
from tests.fake_loki import LOKI_URL, FakeLoki


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (
            '[15:07:55.404] INFO Inserted next recurrence originalId="a-1" seriesId="b-2"',
            "Inserted next recurrence",
        ),
        (
            "[15:07:55.404] ERROR Container exited code=137 group=main-group",
            "Container exited",
        ),
        (
            '[15:07:55.404] WARN Slow query took="1.2s" in session sess-1 retry=2 of 3',
            "Slow query in session sess-1 of 3",
        ),
        ('[15:07:55.404] \x1b[31mERROR\x1b[39m Boom err="x y"\n    at foo (a.js:1)', "Boom"),
        ("no timestamp here key=value", "no timestamp here"),
        ('[15:07:55.404] ERROR msg="quoted \\" inner" Real text', "Real text"),
        ("[15:07:55.404] ERROR " + "word " * 100, ("word " * 60)[:300].strip()),
    ],
)
def test_message_drops_the_prefix_and_key_value_pairs(line: str, message: str) -> None:
    assert message_of(line) == message


@pytest.mark.parametrize(
    ("line", "absent", "present"),
    [
        (
            "[1] ERROR fetch failed url=https://u:pw@api.example.com/x/y?token=abc#f",
            ["u:pw", "/x/y", "token=abc"],
            ["https://api.example.com"],
        ),
        (
            "[1] ERROR auth header Authorization: Bearer sk-ant-123456 rejected",
            ["sk-ant-123456"],
            ["Bearer •••"],
        ),
        (
            '[1] WARN login token="abc123" apiKey=xyz password=hunter2 cookie="c=1" ok=yes',
            ["abc123", "xyz", "hunter2", "c=1"],
            ["ok=yes", 'token="•••"', "apiKey=•••"],
        ),
        ("[1] ERROR \x1b[31mred\x1b[0m\n  at stack", ["\x1b", "at stack"], ["red"]),
    ],
)
def test_sample_is_sanitised(line: str, absent: list[str], present: list[str]) -> None:
    sample = sanitize_sample(line)
    for text in absent:
        assert text not in sample
    for text in present:
        assert text in sample


def test_sample_is_capped() -> None:
    assert len(sanitize_sample("[1] ERROR " + "x" * 2000)) == 500


@pytest.mark.parametrize(
    ("line", "absent", "message"),
    [
        (
            "[1] ERROR MCP connect https://user:pw@ha.local:8123/api/webhook/mcp_abc123/ro failed",
            ["user", "pw", "mcp_abc123", "/api/webhook"],
            "MCP connect https://ha.local:8123 failed",
        ),
        (
            "[1] ERROR auth header Authorization: Bearer sk-ant-123456 rejected",
            ["sk-ant-123456"],
            "auth header Authorization: Bearer ••• rejected",
        ),
    ],
)
def test_message_is_masked_like_the_sample(line: str, absent: list[str], message: str) -> None:
    got = message_of(line)
    assert got == message
    for text in absent:
        assert text not in got


def test_lines_differing_only_in_a_url_path_group_together() -> None:
    a = message_of("[1] ERROR fetch https://api.example.com/v1/a?x=1 failed")
    b = message_of("[1] ERROR fetch https://api.example.com/v2/b failed")
    assert a == b == "fetch https://api.example.com failed"


@pytest.mark.parametrize(
    "body",
    [
        "a" * 262_144,
        "abc.def-" * 32_768,
        'a="\\' * 65_536,
        "a=" * 131_072,
        "tokenx" * 43_690,
        "a+b.c-" * 43_690 + ":/",
    ],
    ids=["letters", "words", "quotes", "kv-chain", "secret-word", "scheme-chars"],
)
def test_a_long_line_is_cheap(body: str) -> None:
    """Loki allows 256 KiB lines; sanitising one must not stall the event loop (B39)."""
    line = "[1] ERROR " + body
    start = time.perf_counter()
    message_of(line)
    sanitize_sample(line)
    assert time.perf_counter() - start < 0.5


class TestReadHostLogs:
    pytestmark = pytest.mark.anyio

    async def test_groups_by_level_and_message(self, loki: FakeLoki) -> None:
        loki.nanoclaw(50, "ERROR", 'Container exited code=1 group="a"')
        loki.nanoclaw(20, "ERROR", 'Container exited code=137 group="b"')
        loki.nanoclaw(10, "WARN", "Slow poll took=3s")
        loki.nanoclaw(5, "FATAL", "Out of memory")
        loki.nanoclaw(1, "INFO", "Not a problem")
        loki.nanoclaw(60 * 25, "ERROR", "Too old")
        logs = await read_host_logs(LokiClient(LOKI_URL, transport=loki.transport()), NOW)
        assert logs.errors == 3
        assert logs.warnings == 1
        assert not logs.truncated
        assert [(g.level, g.message, g.count) for g in logs.groups] == [
            ("ERROR", "Container exited", 2),
            ("ERROR", "Out of memory", 1),
            ("WARN", "Slow poll", 1),
        ]
        exited = logs.groups[0]
        assert exited.first_at == NOW - timedelta(minutes=50)
        assert exited.last_at == NOW - timedelta(minutes=20)
        assert 'group="b"' in exited.sample  # the newest line is the sample
        assert logs.groups[1].level == "ERROR"  # FATAL counts as an error

    async def test_truncated_at_the_line_limit(self, loki: FakeLoki) -> None:
        for i in range(5):
            loki.nanoclaw(i + 1, "WARN", f"w{i}")
        client = LokiClient(LOKI_URL, transport=loki.transport())
        logs = await read_host_logs(client, NOW, limit=3)
        assert logs.truncated
        assert logs.warnings == 3

    async def test_no_problems(self, loki: FakeLoki) -> None:
        logs = await read_host_logs(LokiClient(LOKI_URL, transport=loki.transport()), NOW)
        assert (logs.errors, logs.warnings, logs.groups, logs.truncated) == (0, 0, [], False)
