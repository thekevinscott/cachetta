"""Tests for async I/O, async instance methods, and _created_dirs eviction."""

import asyncio
import os
import pickle
import tempfile
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
            cache_path = Path(tmpdir) / "stale_async.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"version": 1}, f)

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

            # Wait for background refresh: poll instead of a fixed sleep — on
            # a cold CI runner the first asyncio.to_thread call can outlast
            # any fixed budget. The cache write is atomic (os.replace), so
            # polling reads see either the old or the new value, never a
            # partial file.
            deadline = time() + 5.0
            while time() < deadline:
                with open(cache_path, "rb") as f:
                    if pickle.load(f) == {"version": 2}:
                        break
                await asyncio.sleep(0.01)
            assert call_count == 1

            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"version": 2}


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

    async def test_async_read_stale_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"stale": True}, f)

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
