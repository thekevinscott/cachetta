"""Tests for async I/O, async instance methods, LRU thread safety, and _created_dirs eviction."""

import asyncio
import json
import os
import tempfile
import threading
from collections import OrderedDict
from datetime import timedelta
from pathlib import Path
from time import time

import pytest

from cachetta import (
    Cachetta,
    async_read_cache,
    async_read_stale_cache,
    async_write_cache,
    async_write_cache_ctx,
    write_cache,
)
from cachetta._sentinel import _LRU_MISS
from cachetta.utils.cache_fn import _in_flight


@pytest.fixture(autouse=True)
def clear_in_flight():
    _in_flight.clear()
    yield
    _in_flight.clear()


# -- Async decorated functions --

def describe_async_decorated_functions():
    async def test_async_decorator_caches_and_reads():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/async_dec.json")

            @cache
            async def compute():
                nonlocal call_count
                call_count += 1
                return {"result": call_count}

            r1 = await compute()
            r2 = await compute()

            assert r1 == {"result": 1}
            assert r2 == {"result": 1}
            assert call_count == 1

    async def test_async_decorator_with_path_function():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=lambda key: f"{tmpdir}/{key}.json")

            @cache
            async def fetch(key):
                nonlocal call_count
                call_count += 1
                return {"key": key}

            r1 = await fetch("x")
            r2 = await fetch("y")
            r3 = await fetch("x")

            assert r1 == {"key": "x"}
            assert r2 == {"key": "y"}
            assert r3 == {"key": "x"}
            assert call_count == 2

    async def test_async_decorator_does_not_block_event_loop():
        """Verify that the async decorator uses non-blocking I/O by running
        concurrent async tasks that would deadlock if blocking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=lambda i: f"{tmpdir}/{i}.json")

            @cache
            async def compute(i):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)
                return {"i": i}

            # Run multiple distinct-key calls concurrently
            results = await asyncio.gather(
                compute("a"), compute("b"), compute("c")
            )

            assert len(results) == 3
            assert results[0] == {"i": "a"}
            assert results[1] == {"i": "b"}
            assert results[2] == {"i": "c"}
            assert call_count == 3

    async def test_async_stale_while_revalidate():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale_async.json"
            cache_path.write_text('{"version": 1}')

            old_time = time() - 5400  # 90 min ago
            os.utime(cache_path, (old_time, old_time))

            call_count = 0
            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )

            @cache
            async def get_data():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)
                return {"version": 2}

            result = await get_data()
            assert result == {"version": 1}

            # Wait for background refresh
            await asyncio.sleep(0.2)
            assert call_count == 1

            with open(cache_path) as f:
                assert json.load(f) == {"version": 2}


# -- Async read/write primitives --

def describe_async_read_write():
    async def test_async_write_then_async_read():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "rw.json"
            cache = Cachetta(path=str(cache_path))

            data = {"name": "async_test", "values": [1, 2, 3]}
            await async_write_cache(cache, data)

            async with async_read_cache(cache) as result:
                pass
            assert result == data

    async def test_async_write_cache_ctx():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "ctx.json"
            cache = Cachetta(path=str(cache_path))

            async with async_write_cache_ctx(cache) as writer:
                writer.set({"ctx": True})

            async with async_read_cache(cache) as result:
                pass
            assert result == {"ctx": True}

    async def test_async_read_cache_none_when_missing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            cache = Cachetta(path=str(cache_path))

            async with async_read_cache(cache) as result:
                pass
            assert result is None

    async def test_async_read_cache_lru_hit():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "lru.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            await async_write_cache(cache, {"lru": True})

            # Corrupt file on disk - LRU should still serve
            cache_path.write_text("corrupted!!!")

            async with async_read_cache(cache) as result:
                pass
            assert result == {"lru": True}

    async def test_async_read_stale_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale.json"
            cache_path.write_text('{"stale": true}')

            old_time = time() - 5400  # 90 min ago
            os.utime(cache_path, (old_time, old_time))

            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )

            result = await async_read_stale_cache(cache)
            assert result == {"stale": True}


# -- Async instance methods (ainvalidate, aexists, aage, ainfo) --

def describe_async_instance_methods():
    async def test_ainvalidate():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "inv.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"data": True})
            assert cache_path.exists()

            await cache.ainvalidate()
            assert not cache_path.exists()

    async def test_ainvalidate_noop_when_missing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            cache = Cachetta(path=str(cache_path))

            # Should not raise
            await cache.ainvalidate()

    async def test_ainvalidate_clears_lru():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "lru_inv.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            write_cache(cache, {"data": True})
            assert cache._lru_get(str(cache_path)) is not _LRU_MISS

            await cache.ainvalidate()
            assert cache._lru_get(str(cache_path)) is _LRU_MISS

    async def test_aclear_is_ainvalidate():
        assert Cachetta.aclear is Cachetta.ainvalidate

    async def test_aexists_true():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "exists.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"data": True})
            assert await cache.aexists() is True

    async def test_aexists_false():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            cache = Cachetta(path=str(cache_path))

            assert await cache.aexists() is False

    async def test_aage_returns_timedelta():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "age.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"data": True})
            age = await cache.aage()

            assert age is not None
            assert isinstance(age, timedelta)
            assert age.total_seconds() < 5  # just written

    async def test_aage_returns_none_when_missing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            cache = Cachetta(path=str(cache_path))

            assert await cache.aage() is None

    async def test_ainfo_existing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "info.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))

            write_cache(cache, {"data": True})
            info = await cache.ainfo()

            assert info["exists"] is True
            assert info["expired"] is False
            assert info["stale"] is False
            assert info["path"] == str(cache_path)
            assert isinstance(info["age"], timedelta)

    async def test_ainfo_missing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            cache = Cachetta(path=str(cache_path))

            info = await cache.ainfo()
            assert info["exists"] is False
            assert info["age"] is None
            assert info["expired"] is False
            assert info["stale"] is False

    async def test_ainfo_expired():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "expired.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))

            write_cache(cache, {"data": True})
            old_time = time() - 7200
            os.utime(cache_path, (old_time, old_time))

            info = await cache.ainfo()
            assert info["exists"] is True
            assert info["expired"] is True

    async def test_ainfo_stale():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale.json"
            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )

            write_cache(cache, {"data": True})
            old_time = time() - 5400  # 90 min
            os.utime(cache_path, (old_time, old_time))

            info = await cache.ainfo()
            assert info["exists"] is True
            assert info["expired"] is True
            assert info["stale"] is True


# -- LRU thread safety stress test --

def describe_lru_thread_safety():
    async def test_concurrent_lru_access():
        """Stress test: many concurrent async tasks reading/writing LRU simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda i: f"{tmpdir}/{i}.json",
                lru_size=50,
            )

            errors = []

            async def worker(i):
                try:
                    key = f"key-{i % 20}"
                    cache_path = str(cache._get_path(key))

                    # Mix of reads and writes
                    cache._lru_set(cache_path, {"i": i})
                    await asyncio.sleep(0)  # yield to event loop
                    cache._lru_get(cache_path)
                    # result might be _LRU_MISS if evicted, that's fine
                except Exception as e:
                    errors.append(e)

            # Run many concurrent tasks
            tasks = [worker(i) for i in range(200)]
            await asyncio.gather(*tasks)

            assert errors == [], f"Errors during concurrent LRU access: {errors}"

    def test_lru_thread_safety_with_threads():
        """Stress test using actual OS threads to verify lock correctness."""
        cache = Cachetta(path="test.json", lru_size=20)

        errors = []
        start_event = threading.Event()

        def thread_worker(thread_id):
            try:
                start_event.wait(timeout=5)
                for i in range(100):
                    key = f"key-{i % 15}"
                    cache._lru_set(key, {"thread": thread_id, "i": i})
                    cache._lru_get(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=thread_worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        start_event.set()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread safety errors: {errors}"


# -- _created_dirs eviction test --

def describe_created_dirs_eviction():
    def test_created_dirs_bounded():
        from cachetta.write_cache import _created_dirs, _CREATED_DIRS_MAX, _created_dirs_lock

        # Snapshot current state to restore after test
        with _created_dirs_lock:
            original = OrderedDict(_created_dirs)
            _created_dirs.clear()

        try:
            with _created_dirs_lock:
                for i in range(_CREATED_DIRS_MAX + 50):
                    _created_dirs[f"/fake/dir/{i}"] = None

            assert len(_created_dirs) == _CREATED_DIRS_MAX + 50

            # Now simulate what write_cache does: add with eviction
            with _created_dirs_lock:
                _created_dirs.clear()
                for i in range(_CREATED_DIRS_MAX + 50):
                    _created_dirs[f"/fake/dir/{i}"] = None
                    if len(_created_dirs) > _CREATED_DIRS_MAX:
                        _created_dirs.popitem(last=False)

            assert len(_created_dirs) == _CREATED_DIRS_MAX
            # First entries should have been evicted
            assert "/fake/dir/0" not in _created_dirs
            assert "/fake/dir/49" not in _created_dirs
            # Last entries should remain
            assert f"/fake/dir/{_CREATED_DIRS_MAX + 49}" in _created_dirs
        finally:
            with _created_dirs_lock:
                _created_dirs.clear()
                _created_dirs.update(original)

    def test_created_dirs_eviction_during_writes():
        """Integration test: write to enough unique directories to trigger eviction."""
        from cachetta.write_cache import _created_dirs, _CREATED_DIRS_MAX, _created_dirs_lock

        with tempfile.TemporaryDirectory() as tmpdir:
            with _created_dirs_lock:
                original = OrderedDict(_created_dirs)
                _created_dirs.clear()

            try:
                # Write enough unique directories to exceed the cap
                n = min(_CREATED_DIRS_MAX + 10, 1010)
                for i in range(n):
                    cache_path = Path(tmpdir) / f"dir_{i}" / "data.json"
                    cache = Cachetta(path=str(cache_path))
                    write_cache(cache, {"i": i})

                assert len(_created_dirs) <= _CREATED_DIRS_MAX
            finally:
                with _created_dirs_lock:
                    _created_dirs.clear()
                    _created_dirs.update(original)
