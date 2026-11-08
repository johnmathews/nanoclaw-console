"""Claude health (docs/architecture.md §4.4): OneCLI's traffic in Loki, the broker's probe, and
the rule that turns them into ok, degraded, failing or unknown.

NanoClaw's agents reach Claude through OneCLI, which logs every call as
`... agent="<group>" ... MITM method=POST url=https://api.anthropic.com:443/v1/messages?beta=true
status=200 ... injections_applied=1`. The broker's probe calls `/v1/messages` with no query
string and gets 400 when the token is good, so only `?beta=true` lines are agent traffic; 401
and 403 count from every line.
"""

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from .loki import LokiClient

WINDOW = timedelta(hours=24)
ONECLI = '{container="onecli"} |= "api.anthropic.com" |= "/v1/messages"'
AGENT = ONECLI + ' |= "/v1/messages?beta=true"'
SUCCESS = AGENT + r" |~ `status=2[0-9]{2}\b`"
AUTH_FAILURE = ONECLI + r" |~ `status=40[13]\b`"

_STATUS = re.compile(r"\bstatus=(\d{3})\b")
_AGENT = re.compile(r'\bagent="([^"]+)"')
_INJECTIONS = re.compile(r"\binjections_applied=(\d+)\b")


@dataclass(frozen=True)
class AgentCall:
    at: datetime
    status: int | None
    agent: str | None
    injections_applied: int | None


@dataclass(frozen=True)
class ClaudeSignals:
    last_agent_call: AgentCall | None
    last_success_at: datetime | None
    agent_calls_24h: int
    auth_failures_1h: int
    auth_failures_24h: int


def parse_onecli_line(at: datetime, line: str) -> AgentCall:
    status = _STATUS.search(line)
    agent = _AGENT.search(line)
    injections = _INJECTIONS.search(line)
    return AgentCall(
        at=at,
        status=int(status.group(1)) if status else None,
        agent=agent.group(1)[:80] if agent else None,
        injections_applied=int(injections.group(1)) if injections else None,
    )


def _count(query: str, hours: int) -> str:
    return f"sum(count_over_time({query} [{hours}h]))"


async def read_signals(loki: LokiClient, now: datetime) -> ClaudeSignals:
    """OneCLI's Claude signals over the last 24 h. Raises `LokiError` if Loki fails."""
    start = now - WINDOW
    last, success, calls, auth_1h, auth_24h = await asyncio.gather(
        loki.lines(AGENT, start=start, end=now, limit=1),
        loki.lines(SUCCESS, start=start, end=now, limit=1),
        loki.count(_count(AGENT, 24), at=now),
        loki.count(_count(AUTH_FAILURE, 1), at=now),
        loki.count(_count(AUTH_FAILURE, 24), at=now),
    )
    return ClaudeSignals(
        last_agent_call=parse_onecli_line(last[0].at, last[0].line) if last else None,
        last_success_at=success[0].at if success else None,
        agent_calls_24h=calls,
        auth_failures_1h=auth_1h,
        auth_failures_24h=auth_24h,
    )


def claude_status(
    signals: ClaudeSignals | None, probe: Mapping[str, object] | None
) -> tuple[str, list[str]]:
    """The status and the sentences behind it; first match wins (failing, degraded, ok)."""
    call = signals.last_agent_call if signals else None
    probe_status = probe.get("status") if probe else None
    probe_http = probe.get("http_status") if probe else None

    failing: list[str] = []
    if call is not None and call.status in (401, 403):
        failing.append(f"The last agent call to Claude was refused (HTTP {call.status}).")
    if probe_status == "failing":
        failing.append(f"The broker's probe through OneCLI was refused (HTTP {probe_http}).")
    if failing:
        return "failing", failing

    degraded: list[str] = []
    if signals is not None and signals.auth_failures_1h:
        degraded.append(
            f"{signals.auth_failures_1h} call(s) got 401 or 403 from Anthropic in the last hour."
        )
    if call is not None and call.status is not None and not 200 <= call.status < 300:
        degraded.append(f"The last agent call to Claude failed (HTTP {call.status}).")
    if call is not None and call.injections_applied == 0:
        degraded.append("OneCLI did not inject the token into the last agent call.")
    if degraded:
        return "degraded", degraded

    ok: list[str] = []
    if call is not None and call.status is not None and 200 <= call.status < 300:
        ok.append(f"The last agent call to Claude succeeded (HTTP {call.status}).")
    if probe_status == "ok":
        ok.append(f"The broker's probe through OneCLI was accepted (HTTP {probe_http}).")
    if ok:
        return "ok", ok

    unknown: list[str] = []
    if signals is None:
        unknown.append("Loki did not answer, so OneCLI's traffic is not visible.")
    else:
        unknown.append("No agent called Claude in the last 24 hours.")
    if probe is None:
        unknown.append("The broker's probe did not answer.")
    else:
        unknown.append("The broker's probe could not tell.")
    return "unknown", unknown
