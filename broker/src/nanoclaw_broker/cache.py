"""The read cache (docs/architecture.md §3.6).

Every ncl call runs on NanoClaw's one event loop (F12), so the broker bounds what it asks:

- a value is kept for `ttl` seconds per key (a call may set its own);
- concurrent requests for one key share one load (single-flight);
- at most `max_inflight` loads run at once, across all keys;
- a failed load is not stored: every waiter gets the error, and the next request loads again;
- a write drops what it may have changed (`invalidate`): the stored values of those verbs, and any
  load of them still in flight, which then answers its own waiters but is not stored or shared.

Keys are `(verb name, params)` tuples; `invalidate` matches on the verb name.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable, Iterable

Loader = Callable[[], Awaitable[object]]


class ReadCache:
    def __init__(
        self,
        ttl: float = 20.0,
        max_inflight: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl <= 0 or max_inflight <= 0:
            raise ValueError("ttl and max_inflight must be positive")
        self._ttl = ttl
        self._clock = clock
        self._slots = asyncio.Semaphore(max_inflight)
        self._entries: dict[Hashable, tuple[float, object]] = {}
        self._inflight: dict[Hashable, asyncio.Task[object]] = {}
        self._generation: dict[str, int] = {}  # verb name -> invalidations so far

    async def get(
        self, key: Hashable, loader: Loader, *, ttl: float | None = None, slot: bool = True
    ) -> tuple[object, str]:
        """The value for `key` and how it was served: `hit`, `miss` or `shared`.

        `ttl` overrides the default for this value. `slot=False` is for a loader that does not call
        ncl itself, or that makes ncl calls of its own through `get` (those take the slots):
        holding a slot across them could deadlock the cap.
        """
        entry = self._entries.get(key)
        if entry is not None and entry[0] > self._clock():
            return entry[1], "hit"
        task = self._inflight.get(key)
        how = "shared"
        if task is None:
            how = "miss"
            # The generation is taken now, not when the task first runs: a write in between
            # must still stop this answer being kept.
            generation = self._generation.get(name, 0) if (name := _name(key)) else 0
            task = asyncio.ensure_future(
                self._load(key, loader, ttl or self._ttl, slot, generation)
            )
            self._inflight[key] = task
            task.add_done_callback(lambda done: self._settle(key, done))
        # shield: a waiter that goes away (client hung up) must not cancel the shared load.
        return await asyncio.shield(task), how

    async def run_uncached(self, loader: Loader) -> object:
        """Run `loader` under the in-flight cap without storing the result (release-2 writes)."""
        async with self._slots:
            return await loader()

    def invalidate(self, names: Iterable[str]) -> None:
        """Forget every value of these verbs, and stop sharing or storing loads now in flight."""
        dropped = set(names)
        for name in dropped:
            self._generation[name] = self._generation.get(name, 0) + 1
        self._entries = {k: e for k, e in self._entries.items() if _name(k) not in dropped}
        for key in [k for k in self._inflight if _name(k) in dropped]:
            del self._inflight[key]

    def size(self) -> int:
        return len(self._entries)

    def inflight(self) -> int:
        return len(self._inflight)

    async def _load(
        self, key: Hashable, loader: Loader, ttl: float, slot: bool, generation: int
    ) -> object:
        name = _name(key)
        if slot:
            async with self._slots:
                value = await loader()
        else:
            value = await loader()
        if name is not None and self._generation.get(name, 0) != generation:
            return value  # a write ran meanwhile: this answer may predate it, so don't keep it
        now = self._clock()
        self._entries = {k: e for k, e in self._entries.items() if e[0] > now}
        self._entries[key] = (now + ttl, value)
        return value

    def _settle(self, key: Hashable, task: asyncio.Task[object]) -> None:
        if self._inflight.get(key) is task:
            del self._inflight[key]
        # Mark a failure as retrieved even when every waiter has gone, so asyncio does not log
        # "exception was never retrieved" (which could print reply text).
        if not task.cancelled():
            task.exception()


def _name(key: Hashable) -> str | None:
    """The verb name of a `(verb, params)` key; None for any other key (never invalidated)."""
    if isinstance(key, tuple) and key and isinstance(key[0], str):
        return key[0]
    return None
