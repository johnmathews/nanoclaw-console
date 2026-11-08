"""A fake Loki as an httpx2 transport, with just enough LogQL to run the console's queries.

It understands stream selectors (`=`, `=~`), line filters (`|=`, `|~` with a backtick or
double-quoted pattern) and the one metric shape the console uses,
`sum(count_over_time(<log query> [<n>h]))`. So a test that plants log lines also proves the
queries select the right ones (a probe line is not an agent call, an INFO line is not a warning).
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx2

LOKI_URL = "http://loki.test:3100"

_SELECTOR = re.compile(r"^\{(?P<matchers>[^}]*)\}(?P<rest>.*)$", re.S)
_MATCHER = re.compile(r'\s*(?P<name>\w+)\s*(?P<op>=~|=)\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*,?')
_FILTER = re.compile(r'\s*(?P<op>\|=|\|~)\s*(?:`(?P<raw>[^`]*)`|"(?P<quoted>(?:[^"\\]|\\.)*)")')
_METRIC = re.compile(r"^sum\(count_over_time\((?P<query>.*)\[(?P<hours>\d+)h\]\)\)$", re.S)


@dataclass(frozen=True)
class Entry:
    at: datetime
    labels: dict[str, str]
    line: str


def _unquote(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


def _ns(at: datetime) -> int:
    return int(at.timestamp() * 1_000_000_000)


class FakeLoki:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.entries: list[Entry] = []
        self.queries: list[str] = []
        self.status = 200
        self.error: Exception | None = None
        self.body: bytes | None = None  # served as is when set

    # -- planting -------------------------------------------------------------------------------

    def add(self, minutes_ago: float, labels: dict[str, str], line: str) -> None:
        self.entries.append(Entry(self.now - timedelta(minutes=minutes_ago), labels, line))

    def onecli(
        self,
        minutes_ago: float,
        status: int,
        *,
        agent: str = "main-group",
        beta: bool = True,
        injections: int = 1,
    ) -> None:
        """A OneCLI MITM line, as in its live log: agents' calls carry `?beta=true`."""
        url = "https://api.anthropic.com:443/v1/messages" + ("?beta=true" if beta else "")
        ctype = "text/event-stream; charset=utf-8" if status == 200 else "application/json"
        line = (
            f'2026-11-08T13:37:45Z INFO agent="{agent}" request_id="r-1" '
            f"MITM method=POST url={url} status={status} content_type={ctype} "
            f"injections_applied={injections}"
        )
        labels = {"container": "onecli", "hostname": "agent", "service_name": "onecli"}
        self.add(minutes_ago, labels, line)

    def nanoclaw(self, minutes_ago: float, level: str, text: str) -> None:
        stream = "stderr" if level in ("ERROR", "FATAL") else "stdout"
        at = self.now - timedelta(minutes=minutes_ago)
        line = f"[{at:%H:%M:%S}.123] {level} {text}"
        self.add(minutes_ago, {"job": "nanoclaw", "level": level, "stream": stream}, line)

    # -- LogQL ----------------------------------------------------------------------------------

    def _select(self, query: str, start: datetime, end: datetime) -> list[Entry]:
        m = _SELECTOR.match(query.strip())
        assert m, f"fake Loki cannot parse {query!r}"
        matchers = [
            (mm["name"], mm["op"], _unquote(mm["value"])) for mm in _MATCHER.finditer(m["matchers"])
        ]
        rest = m["rest"].strip()
        filters: list[tuple[str, str]] = []
        while rest:
            fm = _FILTER.match(rest)
            assert fm, f"fake Loki cannot parse filter {rest!r}"
            pattern = fm["raw"] if fm["raw"] is not None else _unquote(fm["quoted"] or "")
            filters.append((fm["op"], pattern))
            rest = rest[fm.end() :].strip()

        def keep(e: Entry) -> bool:
            if not start < e.at <= end:
                return False
            for name, op, value in matchers:
                actual = e.labels.get(name)
                if actual is None:
                    return False
                if op == "=" and actual != value:
                    return False
                if op == "=~" and not re.fullmatch(value, actual):
                    return False
            for op, pattern in filters:
                if op == "|=" and pattern not in e.line:
                    return False
                if op == "|~" and not re.search(pattern, e.line):
                    return False
            return True

        return [e for e in self.entries if keep(e)]

    def _query_range(self, params: dict[str, str]) -> dict[str, Any]:
        start = datetime.fromtimestamp(int(params["start"]) / 1e9, UTC)
        end = datetime.fromtimestamp(int(params["end"]) / 1e9, UTC)
        found = self._select(params["query"], start, end)
        found.sort(key=lambda e: e.at, reverse=params.get("direction", "backward") == "backward")
        found = found[: int(params.get("limit", "100"))]
        streams: dict[str, dict[str, Any]] = {}
        for e in found:
            key = json.dumps(e.labels, sort_keys=True)
            stream = streams.setdefault(key, {"stream": e.labels, "values": []})
            stream["values"].append([str(_ns(e.at)), e.line])
        return {"resultType": "streams", "result": list(streams.values())}

    def _query(self, params: dict[str, str]) -> dict[str, Any]:
        m = _METRIC.match(params["query"].strip())
        assert m, f"fake Loki cannot parse metric {params['query']!r}"
        at = datetime.fromtimestamp(int(params["time"]) / 1e9, UTC)
        n = len(self._select(m["query"], at - timedelta(hours=int(m["hours"])), at))
        result = [] if n == 0 else [{"metric": {}, "value": [at.timestamp(), str(n)]}]
        return {"resultType": "vector", "result": result}

    # -- transport ------------------------------------------------------------------------------

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        params = {k: v[-1] for k, v in parse_qs(request.url.query.decode()).items()}
        self.queries.append(params.get("query", ""))
        if self.error is not None:
            raise self.error
        if self.body is not None:
            return httpx2.Response(self.status, content=self.body)
        if self.status != 200:
            return httpx2.Response(self.status, text="fake loki error")
        path = request.url.path
        if path == "/loki/api/v1/query_range":
            data = self._query_range(params)
        elif path == "/loki/api/v1/query":
            data = self._query(params)
        else:
            return httpx2.Response(404, text="404 page not found")
        return httpx2.Response(200, json={"status": "success", "data": data})

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handler)
