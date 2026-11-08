"""The read cache: TTL per key, single-flight, a cap on calls in flight, no cached errors."""

import asyncio
import gc

import pytest

from nanoclaw_broker.cache import ReadCache


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_second_read_is_a_hit_within_ttl() -> None:
    clock = Clock()
    cache = ReadCache(ttl=20, clock=clock)
    calls = 0

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return f"v{calls}"

    assert await cache.get("k", loader) == ("v1", "miss")
    clock.now += 19.9
    assert await cache.get("k", loader) == ("v1", "hit")
    assert calls == 1


async def test_entry_expires_after_ttl() -> None:
    clock = Clock()
    cache = ReadCache(ttl=20, clock=clock)
    calls = 0

    async def loader() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get("k", loader)
    clock.now += 20
    assert await cache.get("k", loader) == (2, "miss")


async def test_keys_are_independent() -> None:
    cache = ReadCache(ttl=20, clock=Clock())

    async def a() -> str:
        return "a"

    async def b() -> str:
        return "b"

    assert await cache.get(("v", "1"), a) == ("a", "miss")
    assert await cache.get(("v", "2"), b) == ("b", "miss")
    assert await cache.get(("v", "1"), b) == ("a", "hit")


async def test_concurrent_identical_reads_share_one_call() -> None:
    cache = ReadCache(ttl=20, clock=Clock())
    calls = 0
    gate = asyncio.Event()

    async def loader() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "v"

    tasks = [asyncio.create_task(cache.get("k", loader)) for _ in range(10)]
    await asyncio.sleep(0.01)
    gate.set()
    results = await asyncio.gather(*tasks)
    assert calls == 1
    assert [r[0] for r in results] == ["v"] * 10
    assert sorted(r[1] for r in results) == ["miss"] + ["shared"] * 9


async def test_at_most_two_loads_in_flight() -> None:
    cache = ReadCache(ttl=20, max_inflight=2, clock=Clock())
    in_flight = 0
    peak = 0

    async def loader() -> None:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1

    await asyncio.gather(*(cache.get(i, loader) for i in range(8)))
    assert peak == 2


async def test_errors_are_not_cached_and_reach_every_waiter() -> None:
    cache = ReadCache(ttl=20, clock=Clock())
    calls = 0
    gate = asyncio.Event()

    async def failing() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        raise RuntimeError("down")

    tasks = [asyncio.create_task(cache.get("k", failing)) for _ in range(3)]
    await asyncio.sleep(0.01)
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, RuntimeError) for r in results)
    assert calls == 1

    async def ok() -> str:
        return "up"

    assert await cache.get("k", ok) == ("up", "miss")


async def test_a_cancelled_waiter_does_not_cancel_the_shared_load() -> None:
    cache = ReadCache(ttl=20, clock=Clock())
    gate = asyncio.Event()

    async def loader() -> str:
        await gate.wait()
        return "v"

    first = asyncio.create_task(cache.get("k", loader))
    second = asyncio.create_task(cache.get("k", loader))
    await asyncio.sleep(0.01)
    first.cancel()
    gate.set()
    assert await second == ("v", "shared")
    with pytest.raises(asyncio.CancelledError):
        await first


async def test_a_failed_load_nobody_awaits_is_not_reported_as_unretrieved() -> None:
    loop = asyncio.get_running_loop()
    reported: list[dict[str, object]] = []
    loop.set_exception_handler(lambda _loop, context: reported.append(context))
    cache = ReadCache(ttl=20, clock=Clock())
    gate = asyncio.Event()

    async def failing() -> str:
        await gate.wait()
        raise RuntimeError("down")

    waiter = asyncio.create_task(cache.get("k", failing))
    await asyncio.sleep(0.01)
    waiter.cancel()
    gate.set()
    await asyncio.sleep(0.01)
    gc.collect()
    assert cache.inflight() == 0
    assert reported == []


async def test_expired_entries_are_pruned_on_insert() -> None:
    clock = Clock()
    cache = ReadCache(ttl=20, clock=clock)

    async def loader() -> int:
        return 1

    for i in range(5):
        await cache.get(i, loader)
    assert cache.size() == 5
    clock.now += 21
    await cache.get("new", loader)
    assert cache.size() == 1


async def test_run_uncached_respects_the_cap_and_never_stores() -> None:
    cache = ReadCache(ttl=20, max_inflight=1, clock=Clock())
    in_flight = 0
    peak = 0

    async def loader() -> str:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return "w"

    results = await asyncio.gather(*(cache.run_uncached(loader) for _ in range(3)))
    assert results == ["w", "w", "w"]
    assert peak == 1
    assert cache.size() == 0


@pytest.mark.parametrize(("ttl", "cap"), [(0, 2), (-1, 2), (20, 0)])
def test_bad_settings_are_refused(ttl: float, cap: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ReadCache(ttl=ttl, max_inflight=cap)
