"""Loki's query API (docs/architecture.md §4.1): log lines and counts, size- and time-bounded.

Errors carry a code only: `unavailable` (no answer, or an HTTP error), `timeout` and
`bad_response` (not the JSON Loki sends, or too large). Loki's own error text is never passed on.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx2

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


class LokiError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class LogLine:
    at: datetime
    line: str
    labels: Mapping[str, str]


def _ns(at: datetime) -> str:
    return str(int(at.timestamp()) * 1_000_000_000 + at.microsecond * 1000)


class LokiClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._max_bytes = max_bytes

    async def lines(
        self, query: str, *, start: datetime, end: datetime, limit: int
    ) -> list[LogLine]:
        """Matching lines in (start, end], newest first, at most `limit`."""
        data = await self._get(
            "/loki/api/v1/query_range",
            {
                "query": query,
                "start": _ns(start),
                "end": _ns(end),
                "limit": str(limit),
                "direction": "backward",
            },
        )
        if data.get("resultType") != "streams" or not isinstance(data.get("result"), list):
            raise LokiError("bad_response")
        out: list[LogLine] = []
        try:
            for stream in data["result"]:
                labels = stream["stream"]
                for ts, line in stream["values"]:
                    at = datetime.fromtimestamp(int(ts) / 1e9, UTC)
                    out.append(LogLine(at=at, line=str(line), labels=dict(labels)))
        except (KeyError, TypeError, ValueError):
            raise LokiError("bad_response") from None
        out.sort(key=lambda entry: entry.at, reverse=True)
        return out[:limit]

    async def count(self, query: str, *, at: datetime) -> int:
        """A `sum(...)` metric query's value at `at`; an empty vector is 0."""
        data = await self._get("/loki/api/v1/query", {"query": query, "time": _ns(at)})
        result = data.get("result")
        if data.get("resultType") != "vector" or not isinstance(result, list):
            raise LokiError("bad_response")
        try:
            return sum(int(float(sample["value"][1])) for sample in result)
        except (KeyError, IndexError, TypeError, ValueError):
            raise LokiError("bad_response") from None

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            async with (
                httpx2.AsyncClient(
                    transport=self._transport, timeout=self._timeout, follow_redirects=False
                ) as client,
                client.stream("GET", self._base + path, params=params) as response,
            ):
                if response.status_code != 200:
                    raise LokiError("unavailable")
                body = await _read_capped(response, self._max_bytes)
        except httpx2.TimeoutException:
            raise LokiError("timeout") from None
        except (httpx2.HTTPError, httpx2.InvalidURL):
            raise LokiError("unavailable") from None
        try:
            reply = json.loads(body)
        except ValueError:
            raise LokiError("bad_response") from None
        if not isinstance(reply, dict) or reply.get("status") != "success":
            raise LokiError("bad_response")
        data = reply.get("data")
        if not isinstance(data, dict):
            raise LokiError("bad_response")
        return data


async def _read_capped(response: httpx2.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise LokiError("bad_response")
        chunks.append(chunk)
    return b"".join(chunks)
