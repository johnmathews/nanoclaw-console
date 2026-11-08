"""NanoClaw's host errors and warnings from Loki, grouped by message (docs/architecture.md §4.5).

NanoClaw's host log lines look like `[15:07:55.404] ERROR Container exited code=137 group="b"`,
with a stack trace joined on after a newline. A group is the level plus the message with every
`key=value` pair removed and the same masking as the sample. Each group keeps one sanitised
sample line.

Every pattern here runs in linear time, on a line already cut to `MAX_INPUT`: these run inside the
async handler, so one long log line must not stall every request (B39).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .loki import LokiClient

WINDOW_HOURS = 24
QUERY = '{job="nanoclaw", level=~"WARN|ERROR|FATAL"}'
DEFAULT_LIMIT = 2000
MAX_MESSAGE = 300
MAX_SAMPLE = 500
# A line is cut to this before any pattern runs, so their cost is bounded whatever Loki sends.
MAX_INPUT = 4096
MASK = "•••"

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_PREFIX = re.compile(r"^\[[^\]]*\]\s+(?P<level>[A-Z]+)\b\s*")
_KV = re.compile(r'(?<![\w.-])[A-Za-z_][\w.-]*=(?:"(?:[^"\\]|\\.)*"|\S*)')
_SPACE = re.compile(r"\s+")
# A scheme starts at the beginning of its run of scheme characters: without the lookbehind the
# pattern retries from every letter of a long word and is quadratic (the broker's B16).
_URL = re.compile(
    r"(?<![A-Za-z0-9+.-])(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?:[^\s/?#@]*@)?(?P<host>[^\s/?#\"'<>]+)"
    r"[^\s\"'<>]*"
)
_BEARER = re.compile(r"\b(Bearer|bearer|BEARER|Basic|basic)\s+\S+")
# Any key=value; the replacement decides whether the key looks secret. A key pattern with the
# secret words inside it (`[\w.-]*?(?:token|…)[\w.-]*`) backtracks quadratically on a long word.
_ANY_KV = re.compile(r'(?<![\w.-])(?P<key>[\w.-]+)=(?P<value>"(?:[^"\\]|\\.)*"|\S*)')
_SECRET_KEY = re.compile(r"token|secret|password|passwd|key|auth|cookie", re.IGNORECASE)


@dataclass(frozen=True)
class LogGroup:
    level: str
    message: str
    count: int
    first_at: datetime
    last_at: datetime
    sample: str


@dataclass(frozen=True)
class HostLogs:
    groups: list[LogGroup]
    errors: int
    warnings: int
    truncated: bool


def _first_line(line: str) -> str:
    return _ANSI.sub("", line[:MAX_INPUT]).split("\n", 1)[0]


def _mask_kv(match: re.Match[str]) -> str:
    if _SECRET_KEY.search(match.group("key")) is None:
        return match.group(0)
    value = match.group("value")
    masked = f'"{MASK}"' if value.startswith('"') else MASK
    return f"{match.group('key')}={masked}"


def _mask(text: str) -> str:
    """URLs cut to scheme://host[:port], Bearer and Basic values and secret-looking keys masked."""
    text = _URL.sub(lambda m: f"{m.group('scheme')}://{m.group('host')}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {MASK}", text)
    return _ANY_KV.sub(_mask_kv, text)


def message_of(line: str) -> str:
    """The message: no timestamp, no level, masked as the sample is, no key=value pairs.

    Masking first means a URL's userinfo or path, or a Bearer value, never reaches the message,
    and lines that differ only there group together.
    """
    text = _mask(_PREFIX.sub("", _first_line(line), count=1))
    text = _SPACE.sub(" ", _KV.sub(" ", text)).strip()
    return text[:MAX_MESSAGE].rstrip()


def sanitize_sample(line: str) -> str:
    """One log line fit to show: first line only, URLs to scheme://host, secrets masked."""
    return _mask(_first_line(line))[:MAX_SAMPLE]


def _level(label: str | None) -> str:
    """The query selects WARN, ERROR and FATAL only; FATAL counts as an error."""
    return "WARN" if label == "WARN" else "ERROR"


async def read_host_logs(
    loki: LokiClient, now: datetime, *, limit: int = DEFAULT_LIMIT
) -> HostLogs:
    """Errors and warnings over the last 24 h. Raises `LokiError` if Loki fails."""
    lines = await loki.lines(QUERY, start=now - timedelta(hours=WINDOW_HOURS), end=now, limit=limit)
    groups: dict[tuple[str, str], LogGroup] = {}
    errors = warnings = 0
    for entry in lines:  # newest first
        level = _level(entry.labels.get("level"))
        if level == "ERROR":
            errors += 1
        else:
            warnings += 1
        key = (level, message_of(entry.line))
        group = groups.get(key)
        if group is None:
            groups[key] = LogGroup(
                level=level,
                message=key[1],
                count=1,
                first_at=entry.at,
                last_at=entry.at,
                sample=sanitize_sample(entry.line),
            )
        else:
            groups[key] = LogGroup(
                level=level,
                message=key[1],
                count=group.count + 1,
                first_at=min(group.first_at, entry.at),
                last_at=max(group.last_at, entry.at),
                sample=group.sample,
            )
    ordered = sorted(
        groups.values(),
        key=lambda g: (g.level != "ERROR", -g.count, -g.last_at.timestamp()),
    )
    return HostLogs(groups=ordered, errors=errors, warnings=warnings, truncated=len(lines) >= limit)
