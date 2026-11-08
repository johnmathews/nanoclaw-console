"""A small async TTL cache with single-flight, for the Loki-derived signals (§4.4).

Only successes are kept: a failed read is retried on the next request, so Loki coming back shows
at once. Concurrent requests for the same key share one load.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

DEFAULT_TTL = 30.0


class TtlCache:
    def __init__(self, ttl: float, clock: Callable[[], float]) -> None:
        self._ttl = ttl
        self._clock = clock
        self._values: dict[str, tuple[float, object]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get[T](self, key: str, load: Callable[[], Awaitable[T]]) -> T:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._values.get(key)
            if cached is not None and self._clock() - cached[0] < self._ttl:
                return cast(T, cached[1])
            value = await load()
            self._values[key] = (self._clock(), value)
            return value
