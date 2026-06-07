"""Unit tests for the pure helpers in cachetta.utils.cache_fn.

The wrapper construction in ``cache_fn`` itself is exercised end-to-end by the
integration suite; these unit tests pin the pure, side-effect-free helpers.
"""

import asyncio
import pickle
import tempfile
from datetime import timedelta
from pathlib import Path
from time import time
from types import SimpleNamespace

import pytest

from cachetta.cachetta import Cachetta  # mock-enforce-ignore: real Cachetta config object used as a plain-data fixture
from cachetta.utils.cache_fn import _resolve_args, _should_cache, _in_flight


@pytest.fixture(autouse=True)
def clear_in_flight():
    _in_flight.clear()
    yield
    _in_flight.clear()


def _write_pickle(path, data):
    with open(path, "wb") as f:
        pickle.dump(data, f)


def _make_stale_file(path, data):
    """Write a cache file and backdate its mtime so it is expired but within the
    stale window of a cache with duration=1s, stale_duration=1day."""
    _write_pickle(path, data)
    import os

    old = time() - 10  # 10s ago: past 1s duration, within 1day stale window
    os.utime(path, (old, old))


def describe_resolve_args():
    def test_strips_first_positional_arg_when_skip_self():
        cache = SimpleNamespace(skip_self=True)
        args, kwargs = _resolve_args(cache, ("self", 1, 2), {"k": "v"})
        assert args == (1, 2)
        assert kwargs == {"k": "v"}

    def test_keeps_args_when_skip_self_but_no_positional_args():
        cache = SimpleNamespace(skip_self=True)
        args, kwargs = _resolve_args(cache, (), {"k": "v"})
        assert args == ()
        assert kwargs == {"k": "v"}

    def test_keeps_all_args_when_not_skip_self():
        cache = SimpleNamespace(skip_self=False)
        args, kwargs = _resolve_args(cache, ("self", 1), {})
        assert args == ("self", 1)


def describe_should_cache():
    def test_caches_when_no_condition_is_set():
        cache = SimpleNamespace(condition=None)
        assert _should_cache(cache, "anything") is True

    def test_delegates_to_the_condition_callable():
        cache = SimpleNamespace(condition=lambda result: result > 0)
        assert _should_cache(cache, 5) is True
        assert _should_cache(cache, -1) is False


def describe_async_wrapper_stale_while_revalidate():
    async def test_falls_through_to_inflight_check_when_no_stale_data():
        """stale_duration is set but there is no stale file on disk, so the
        stale branch yields None and execution falls through to the in-flight
        check (arc 50->66)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            calls = 0
            cache = Cachetta(
                path=f"{tmpdir}/sw.json",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            @cache
            async def compute():
                nonlocal calls
                calls += 1
                return {"n": calls}

            # No cache file exists yet -> read miss, stale miss -> executes fn.
            result = await compute()
            assert result == {"n": 1}
            assert calls == 1

    async def test_returns_stale_without_scheduling_when_already_in_flight():
        """When stale data exists and an in-flight refresh is already registered
        for the key, the wrapper returns stale data without scheduling another
        background task (arc 51->63)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sw.json"
            _make_stale_file(path, {"stale": True})

            cache = Cachetta(
                path=str(path),
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            @cache
            async def compute():
                return {"fresh": True}

            cache_key = str(cache._get_path())

            # Pre-register an in-flight task so the scheduling branch is skipped.
            async def _noop():
                await asyncio.sleep(0.05)

            sentinel_task = asyncio.ensure_future(_noop())
            _in_flight[cache_key] = sentinel_task
            try:
                result = await compute()
            finally:
                _in_flight.pop(cache_key, None)
                await sentinel_task

            assert result == {"stale": True}

    async def test_background_refresh_skips_write_when_condition_false():
        """The background refresh runs the fn but _should_cache returns False,
        so async_write_cache is not awaited (arc 55->exit)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sw.json"
            _make_stale_file(path, {"stale": True})

            cache = Cachetta(
                path=str(path),
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
                condition=lambda result: False,  # never cache the refreshed value
            )

            refreshed = asyncio.Event()

            @cache
            async def compute():
                refreshed.set()
                return {"fresh": True}

            cache_key = str(cache._get_path())
            result = await compute()
            assert result == {"stale": True}

            # Let the background task run to completion.
            await asyncio.wait_for(refreshed.wait(), timeout=1)
            task = _in_flight.get(cache_key)
            if task is not None:
                await task

            # Stale file must remain unchanged (condition prevented the write).
            with open(path, "rb") as f:
                assert pickle.load(f) == {"stale": True}

    async def test_background_refresh_logs_and_swallows_exception():
        """The background refresh fn raises; the exception is caught and logged
        (lines 57-58) without bubbling up to the caller."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sw.json"
            _make_stale_file(path, {"stale": True})

            cache = Cachetta(
                path=str(path),
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            ran = asyncio.Event()

            @cache
            async def compute():
                ran.set()
                raise RuntimeError("boom in refresh")

            cache_key = str(cache._get_path())
            result = await compute()
            assert result == {"stale": True}

            await asyncio.wait_for(ran.wait(), timeout=1)
            task = _in_flight.get(cache_key)
            if task is not None:
                # Should complete without raising despite the fn error.
                await task


def describe_sync_wrapper_stale_while_revalidate():
    def test_returns_stale_data_without_executing_fn():
        """Sync wrapper: cache read misses but stale data is available, so it is
        returned without calling the wrapped fn (lines 104-107)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sw.dat"
            _make_stale_file(path, {"stale": True})

            cache = Cachetta(
                path=str(path),
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            calls = 0

            @cache
            def compute():
                nonlocal calls
                calls += 1
                return {"fresh": True}

            result = compute()
            assert result == {"stale": True}
            assert calls == 0

    def test_executes_fn_when_stale_duration_set_but_no_stale_data():
        """Sync wrapper: stale_duration is set but no stale file exists, so the
        stale branch yields None and execution falls through to running the
        wrapped fn (arc 105->109)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=f"{tmpdir}/nostale.dat",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            calls = 0

            @cache
            def compute():
                nonlocal calls
                calls += 1
                return {"fresh": True}

            result = compute()
            assert result == {"fresh": True}
            assert calls == 1

    def test_propagates_exception_from_wrapped_fn():
        """Sync wrapper: read miss with no stale data, fn raises -> exception is
        logged and re-raised (lines 116-118)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/err.dat")

            @cache
            def compute():
                raise ValueError("sync boom")

            with pytest.raises(ValueError, match="sync boom"):
                compute()

    def test_skips_write_when_condition_returns_false():
        """Sync wrapper: read miss, fn runs, but _should_cache is False so
        write_cache is not called and the result is still returned (arc
        113->121)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cond.dat"
            cache = Cachetta(path=str(path), condition=lambda result: False)

            @cache
            def compute():
                return {"value": 2}

            result = compute()
            assert result == {"value": 2}
            assert not path.exists()


def describe_async_wrapper_core():
    async def test_returns_cached_data_on_hit():
        """Async wrapper: a fresh cache file exists, so async_read_cache yields
        data and the wrapped fn is never executed (lines 42-43)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "hit.json"
            _write_pickle(path, {"cached": True})  # fresh -> read hit
            cache = Cachetta(path=str(path))

            calls = 0

            @cache
            async def compute():
                nonlocal calls
                calls += 1
                return {"fresh": True}

            result = await compute()
            assert result == {"cached": True}
            assert calls == 0

    async def test_deduplicates_concurrent_call_without_stale_duration():
        """Async wrapper with no stale_duration: read miss falls straight through
        to the in-flight check (arc 48->66); an existing in-flight task is
        awaited via asyncio.shield (lines 68-69)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/dedup.json")  # no stale_duration

            @cache
            async def compute():
                return {"computed": True}

            cache_key = str(cache._get_path())

            async def _inflight():
                await asyncio.sleep(0.05)
                return {"inflight": True}

            task = asyncio.ensure_future(_inflight())
            _in_flight[cache_key] = task
            try:
                result = await compute()
            finally:
                _in_flight.pop(cache_key, None)
                await task

            assert result == {"inflight": True}

    async def test_background_refresh_writes_when_condition_allows():
        """Async wrapper: stale data is returned and the background refresh runs
        the fn and writes the new value because _should_cache is True (line
        56)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sw.json"
            _make_stale_file(path, {"stale": True})

            cache = Cachetta(
                path=str(path),
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            )

            @cache
            async def compute():
                return {"refreshed": True}

            cache_key = str(cache._get_path())
            result = await compute()
            assert result == {"stale": True}

            task = _in_flight.get(cache_key)
            if task is not None:
                await task

            with open(path, "rb") as f:
                assert pickle.load(f) == {"refreshed": True}

    async def test_execute_skips_write_when_condition_false():
        """Async wrapper: read miss, fn runs, _should_cache is False so
        async_write_cache is not awaited (arc 75->78)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cond.json"
            cache = Cachetta(path=str(path), condition=lambda result: False)

            @cache
            async def compute():
                return {"value": 1}

            result = await compute()
            assert result == {"value": 1}
            assert not path.exists()

    async def test_execute_logs_and_reraises_exception():
        """Async wrapper: read miss, the fn raises inside _execute, so the error
        is logged and re-raised to the caller (lines 79-81)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/err.json")

            @cache
            async def compute():
                raise ValueError("async boom")

            with pytest.raises(ValueError, match="async boom"):
                await compute()
