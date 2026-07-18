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
from cachetta.utils.cache_fn import _should_cache, _in_flight, _fn_identity, _pop_if_current


@pytest.fixture(autouse=True)
def clear_in_flight():
    _in_flight.clear()
    yield
    _in_flight.clear()


def _key_for(fn, cache, *args, **kwargs):
    """Build the same composite in-flight key the wrapper computes internally,
    for tests that need to pre-register/inspect an in-flight entry."""
    loop_id = id(asyncio.get_running_loop())
    cache_key = str(cache._get_path(*args, **kwargs))
    return (loop_id, _fn_identity(fn), cache_key)


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


def describe_descriptor_binding():
    def test_access_via_class_returns_the_wrapper_itself():
        """Accessing the decorated attribute on the class (instance is None)
        returns the unbound wrapper, so it behaves as a plain callable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/c.dat")

            class Service:
                @cache
                def get(self, x):
                    return x

            # Unbound access hits the `instance is None` branch of __get__.
            assert Service.__dict__["get"].__get__(None, Service) is Service.__dict__["get"]

    def test_bound_method_excludes_receiver_from_cache_key():
        """Two instances calling the method with equal args resolve to one
        cache file: the receiver is bound for invocation but excluded from
        the key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            calls = []
            cache = Cachetta(path=str(cache_dir), hashed=True)

            class Service:
                @cache
                def get(self, x):
                    calls.append(x)
                    return x * 2

            assert Service().get(3) == 6
            assert Service().get(3) == 6
            assert len(list(cache_dir.iterdir())) == 1
            assert calls == [3]

    def test_bound_method_passes_receiver_to_the_wrapped_fn():
        """The bound receiver is still handed to the wrapped function, so
        instance state is available inside it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=lambda x: f"{tmpdir}/{x}.dat")

            class Service:
                def __init__(self, factor):
                    self.factor = factor

                @cache
                def get(self, x):
                    return x * self.factor

            assert Service(10).get(5) == 50

    async def test_bound_async_method_excludes_receiver_from_cache_key():
        """Async methods are bound the same way: the receiver is excluded
        from the key and passed to the coroutine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            calls = []
            cache = Cachetta(path=str(cache_dir), hashed=True)

            class Service:
                @cache
                async def get(self, x):
                    calls.append(x)
                    return x * 2

            assert await Service().get(4) == 8
            assert await Service().get(4) == 8
            assert len(list(cache_dir.iterdir())) == 1
            assert calls == [4]


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

            async def _compute():
                return {"fresh": True}

            compute = cache(_compute)
            key = _key_for(_compute, cache)

            # Pre-register an in-flight task so the scheduling branch is skipped.
            async def _noop():
                await asyncio.sleep(0.05)

            sentinel_task = asyncio.ensure_future(_noop())
            _in_flight[key] = sentinel_task
            try:
                result = await compute()
            finally:
                _in_flight.pop(key, None)
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

            async def _compute():
                refreshed.set()
                return {"fresh": True}

            compute = cache(_compute)
            key = _key_for(_compute, cache)
            result = await compute()
            assert result == {"stale": True}

            # Let the background task run to completion.
            await asyncio.wait_for(refreshed.wait(), timeout=1)
            task = _in_flight.get(key)
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

            async def _compute():
                ran.set()
                raise RuntimeError("boom in refresh")

            compute = cache(_compute)
            key = _key_for(_compute, cache)
            result = await compute()
            assert result == {"stale": True}

            await asyncio.wait_for(ran.wait(), timeout=1)
            task = _in_flight.get(key)
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

            async def _compute():
                return {"computed": True}

            compute = cache(_compute)
            key = _key_for(_compute, cache)

            async def _inflight():
                await asyncio.sleep(0.05)
                return {"inflight": True}

            task = asyncio.ensure_future(_inflight())
            _in_flight[key] = task
            try:
                result = await compute()
            finally:
                _in_flight.pop(key, None)
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

            async def _compute():
                return {"refreshed": True}

            compute = cache(_compute)
            key = _key_for(_compute, cache)
            result = await compute()
            assert result == {"stale": True}

            task = _in_flight.get(key)
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


def describe_pop_if_current():
    async def test_leaves_registry_untouched_when_key_now_points_at_another_task():
        """A stale done-callback firing after the key has been claimed by a
        newer task must not evict that newer task from the registry."""
        key = (0, (0, 0), "path")

        async def _noop():
            return None

        stale_task = asyncio.ensure_future(_noop())
        current_task = asyncio.ensure_future(_noop())
        _in_flight[key] = current_task

        _pop_if_current(key, stale_task)

        assert _in_flight[key] is current_task
        await stale_task
        await current_task

    async def test_removes_entry_when_key_still_points_at_this_task():
        key = (0, (0, 0), "path")

        async def _noop():
            return None

        task = asyncio.ensure_future(_noop())
        _in_flight[key] = task

        _pop_if_current(key, task)

        assert key not in _in_flight
        await task


def describe_in_flight_scoping():
    """Regression coverage for issue #80: the in-flight dedup registry must
    not collide across unrelated decorated functions that happen to resolve
    to the same cache path, and must never hand a caller a task bound to a
    different (e.g. already-closed) event loop.
    """

    async def test_two_instances_same_path_do_not_dedupe_across_functions():
        """Two different Cachetta instances, wrapping two different
        functions, that happen to resolve to the same cache path must not
        share in-flight results. Before the fix, the registry was keyed
        purely on the resolved path string, so the second call would await
        the first function's still-running task and get back its result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/shared.json"
            cache_a = Cachetta(path=path, write=False, read=False)
            cache_b = Cachetta(path=path, write=False, read=False)
            fn_a_started = asyncio.Event()
            release_fn_a = asyncio.Event()

            @cache_a
            async def fn_a():
                fn_a_started.set()
                await release_fn_a.wait()
                return {"who": "a"}

            @cache_b
            async def fn_b():
                return {"who": "b"}

            task_a = asyncio.ensure_future(fn_a())
            await asyncio.wait_for(fn_a_started.wait(), timeout=1)

            # fn_a's call is still in-flight (registered) when fn_b is called
            # against the same resolved path via a different instance/function.
            result_b = await asyncio.wait_for(fn_b(), timeout=1)

            release_fn_a.set()
            result_a = await asyncio.wait_for(task_a, timeout=1)

            assert result_b == {"who": "b"}
            assert result_a == {"who": "a"}

    def test_cross_loop_call_does_not_raise_runtime_error():
        """A call left in-flight when its event loop is torn down must not
        crash a later call made against the same key on a fresh loop. Before
        the fix, the leftover (not-done) task from the closed loop would be
        found in the registry and handed to ``asyncio.shield`` on the new
        loop, raising a ``RuntimeError`` (a task/future bound to a foreign
        event loop can't be awaited from another loop)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/cross-loop.json", write=False, read=False)
            calls = 0

            @cache
            async def compute():
                nonlocal calls
                calls += 1
                if calls == 1:
                    # Never resolves before the first loop is torn down below.
                    await asyncio.Event().wait()
                return {"call": calls}

            async def _start_and_abandon():
                task = asyncio.ensure_future(compute())
                await asyncio.sleep(0.01)  # let it register as in-flight
                return task

            loop1 = asyncio.new_event_loop()
            try:
                abandoned_task = loop1.run_until_complete(_start_and_abandon())
                assert not abandoned_task.done()
            finally:
                loop1.close()

            # A fresh loop, same key: must run independently rather than
            # raising when it encounters the abandoned first-loop task.
            result = asyncio.run(compute())
            assert result == {"call": 2}
