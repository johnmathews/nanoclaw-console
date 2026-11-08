"""`claude-probe`: does OneCLI's injected Claude credential work? (docs/architecture.md §3.8)

W2 proved that Anthropic checks the credential before the request body. `POST /v1/messages` with
`{}` through OneCLI therefore answers 400 (`model: Field required`) when the injected token is
accepted and 401 when it is not, and spends no tokens.

The proxy credential is the secret here. It is read from OneCLI's container-config, used for one
`Proxy-Authorization` header on a connection to 127.0.0.1, and goes nowhere else. Nothing on this
path formats an exception, a URL or a header into a result or a log line: every failure is reduced
to `unknown`, and the log gets the exception's type name only.
"""

import asyncio
import base64
import http.client
import json
import ssl
from datetime import UTC, datetime
from urllib.parse import quote, unquote, urlsplit

from .events import EventLog
from .verbs import ID_PATTERN

ANTHROPIC_HOST = "api.anthropic.com"
MAX_CONFIG = 1024 * 1024
MAX_BODY = 64 * 1024
DEFAULT_TIMEOUT = 10.0


class _Unusable(Exception):
    """The container-config was not what the probe needs. Carries no data."""


class ClaudeProbe:
    def __init__(
        self,
        *,
        onecli_url: str,
        agent_group: str,
        timeout: float = DEFAULT_TIMEOUT,
        events: EventLog | None = None,
    ) -> None:
        if ID_PATTERN.fullmatch(agent_group) is None:
            raise ValueError("agent group must be an id")
        self._onecli = urlsplit(onecli_url)
        self._group = agent_group
        self._timeout = timeout
        self._events = events or EventLog()

    async def run(self) -> dict[str, object]:
        """`{status: ok|failing|unknown, http_status, checked_at}`. Never raises."""
        http_status: int | None = None
        error: str | None = None
        try:
            async with asyncio.timeout(self._timeout * 3):
                http_status = await asyncio.to_thread(self._blocking)
        except Exception as exc:
            error = type(exc).__name__
        status = {400: "ok", 401: "failing", 403: "failing"}.get(http_status or 0, "unknown")
        self._events.emit("claude_probe", status=status, http_status=http_status, error=error)
        return {
            "status": status,
            "http_status": http_status,
            "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

    def _blocking(self) -> int:
        proxy, authorization, ca = self._container_config()
        context = ssl.create_default_context(cadata=ca)
        # Always loopback: the host in the config (host.docker.internal) is for containers.
        conn = http.client.HTTPSConnection(
            "127.0.0.1", proxy, context=context, timeout=self._timeout
        )
        conn.set_tunnel(ANTHROPIC_HOST, 443, headers={"Proxy-Authorization": authorization})
        try:
            conn.request(
                "POST",
                "/v1/messages",
                body=b"{}",
                headers={
                    "Authorization": "Bearer placeholder",
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            response = conn.getresponse()
            response.read(MAX_BODY)
            return response.status
        finally:
            conn.close()

    def _container_config(self) -> tuple[int, str, str]:
        """(proxy port, Proxy-Authorization value, CA PEM) from OneCLI's container-config."""
        conn = http.client.HTTPConnection(
            self._onecli.hostname or "127.0.0.1", self._onecli.port or 80, timeout=self._timeout
        )
        try:
            conn.request("GET", f"/v1/container-config?identifier={quote(self._group, safe='')}")
            response = conn.getresponse()
            body = response.read(MAX_CONFIG + 1)
            if response.status != 200 or len(body) > MAX_CONFIG:
                raise _Unusable
        finally:
            conn.close()
        config = json.loads(body)
        env = config.get("env") if isinstance(config, dict) else None
        proxy_url = env.get("HTTPS_PROXY") if isinstance(env, dict) else None
        ca = config.get("caCertificate") if isinstance(config, dict) else None
        if not isinstance(proxy_url, str) or not isinstance(ca, str) or not ca:
            raise _Unusable
        parts = urlsplit(proxy_url)
        port = parts.port
        if not parts.username or port is None:
            raise _Unusable
        credentials = f"{unquote(parts.username)}:{unquote(parts.password or '')}"
        return port, "Basic " + base64.b64encode(credentials.encode()).decode(), ca
