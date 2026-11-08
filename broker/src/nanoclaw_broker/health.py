"""`health`: NanoClaw's loopback /health endpoint (docs/architecture.md §3.8).

`healthy` there covers channels and the message loop only, never Claude (F8). Anything that is not
a JSON object from a 200 or 503 (503 is how NanoClaw says `healthy: false`) is reported as
`{"available": false}`, so a stopped NanoClaw is a state, not an error.
"""

import asyncio
import http.client
import json

from .redact import redact_reply

MAX_BODY = 64 * 1024
DEFAULT_TIMEOUT = 3.0
UNAVAILABLE: dict[str, object] = {"available": False}


async def fetch_health(port: int, *, timeout: float = DEFAULT_TIMEOUT) -> object:
    try:
        async with asyncio.timeout(timeout + 1):
            return await asyncio.to_thread(_get, port, timeout)
    except TimeoutError:
        return dict(UNAVAILABLE)


def _get(port: int, timeout: float) -> object:
    # http.client, not urllib: no proxy settings from the environment, loopback only.
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", "/health")
        response = conn.getresponse()
        body = response.read(MAX_BODY + 1)
        if response.status not in (200, 503) or len(body) > MAX_BODY:
            return dict(UNAVAILABLE)
        data = json.loads(body)
    except (OSError, http.client.HTTPException, ValueError):
        return dict(UNAVAILABLE)
    finally:
        conn.close()
    return redact_reply(data) if isinstance(data, dict) else dict(UNAVAILABLE)
