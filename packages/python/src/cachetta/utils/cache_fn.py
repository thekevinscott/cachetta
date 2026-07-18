import asyncio
from contextlib import contextmanager
from types import MethodType
from typing import Callable
from functools import update_wrapper, wraps
from ..read_cache import read_cache, read_stale_cache, async_read_cache, async_read_stale_cache
from ..write_cache import write_cache, async_write_cache
from .logger import logger

# In-flight asyncio task deduplication.
#
# Keyed by (id(event loop), fn identity, resolved cache path) so that:
#   - two decorated functions (or two Cachetta instances) that happen to
#     resolve to the same cache path never dedupe against each other -- the
#     fn identity component distinguishes them;
#   - tasks scheduled on one event loop are never awaited/shielded from a
#     different loop, which would raise ``RuntimeError`` (asyncio tasks and
#     locks are bound to the loop that created them).
_InFlightKey = tuple[int, tuple[int, int], str]
_in_flight: dict[_InFlightKey, asyncio.Task] = {}

# One lock per event loop, guarding the check-then-register critical section
# for that loop so concurrent coroutines on the same loop can't both observe
# "no in-flight task" and both schedule work. asyncio.Lock is itself
# loop-bound (post 3.10), so it can't be shared across loops either.
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(loop_id: int) -> asyncio.Lock:
    lock = _locks.get(loop_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[loop_id] = lock
    return lock


def _pop_if_current(key: _InFlightKey, task: asyncio.Task) -> None:
    """Remove ``key`` from the registry only if it still points at ``task``.

    Guards against a done-callback from a stale/superseded task clobbering a
    newer task that has since claimed the same key.
    """
    if _in_flight.get(key) is task:
        _in_flight.pop(key, None)


def _fn_identity(fn: Callable) -> tuple[int, int]:
    """Stable identity for the decorated callable.

    For a bound method, ``fn`` is a fresh ``MethodType`` on every descriptor
    access (see ``_Cached.__get__``), so ``id(fn)`` itself is not stable.
    ``__func__``/``__self__`` are stable across those accesses, so use those
    when present; a plain function has neither, so ``fn`` and ``None`` are
    used directly.
    """
    return (id(getattr(fn, "__func__", fn)), id(getattr(fn, "__self__", None)))


def _should_cache(cache, result) -> bool:
    """Check if result should be cached based on the condition callable."""
    if cache.condition is None:
        return True
    return cache.condition(result)


@contextmanager
def _log_errors(kind: str, fn_name: str):
    """Log and re-raise any exception raised by the wrapped function.

    ``kind`` is "sync" or "async" and reproduces the original per-flavor log
    message verbatim.
    """
    try:
        yield
    except Exception as e:
        logger.error("Error executing %s function %s: %s", kind, fn_name, e)
        raise


def _execute_and_maybe_cache_sync(cache, fn: Callable, args, kwargs, fn_name: str):
    """Run ``fn``, write the result to cache if it qualifies, and return it."""
    data = fn(*args, **kwargs)
    logger.debug("Executed sync function %s, writing data to %s", fn_name, cache.path)
    if _should_cache(cache, data):
        write_cache(cache, data, *args, **kwargs)
        logger.debug("Wrote data for %s to %s", fn_name, cache.path)
    return data


async def _execute_and_maybe_cache_async(cache, fn: Callable, args, kwargs, fn_name: str, *, log: bool = True):
    """Await ``fn``, write the result to cache if it qualifies, and return it.

    ``log`` controls whether the debug "executed"/"wrote" messages are
    emitted; the background stale-while-revalidate refresh runs silently on
    this axis (matching its pre-refactor behavior), while the foreground
    execution path logs both steps.
    """
    result = await fn(*args, **kwargs)
    if log:
        logger.debug("Executed async function %s, writing data to %s", fn_name, cache.path)
    if _should_cache(cache, result):
        await async_write_cache(cache, result, *args, **kwargs)
        if log:
            logger.debug("Wrote data for %s to %s", fn_name, cache.path)
    return result


def _build(cache, fn: Callable) -> Callable:
    # `Callable` doesn't statically expose `__name__`; resolve it once (with a
    # safe fallback) for the log messages below.
    fn_name = getattr(fn, "__name__", repr(fn))
    if asyncio.iscoroutinefunction(fn):
        logger.debug("Decorating async function %s", fn_name)
        fn_identity = _fn_identity(fn)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            logger.debug("Executing async function %s with read_cache", fn_name)

            async with async_read_cache(cache, *args, **kwargs) as data:
                if data is not None:
                    logger.debug("Data is not None, returning data for %s", fn_name)
                    return data

                cache_key = str(cache._get_path(*args, **kwargs))
                loop_id = id(asyncio.get_running_loop())
                key: _InFlightKey = (loop_id, fn_identity, cache_key)
                lock = _get_lock(loop_id)

                # Stale-while-revalidate: return stale data and refresh in background
                if cache.stale_duration:
                    stale_data = await async_read_stale_cache(cache, *args, **kwargs)
                    if stale_data is not None:
                        async with lock:
                            if key not in _in_flight:
                                async def _bg_refresh():
                                    try:
                                        await _execute_and_maybe_cache_async(cache, fn, args, kwargs, fn_name, log=False)
                                    except Exception as e:
                                        logger.error("Background revalidation failed for %s: %s", cache_key, e)

                                task = asyncio.ensure_future(_bg_refresh())
                                _in_flight[key] = task
                                task.add_done_callback(lambda t, k=key: _pop_if_current(k, t))
                        return stale_data

                # If there's already an in-flight call for this key, await it.
                # The check and the registration of a new task both happen
                # while holding `lock`, so no other coroutine on this loop can
                # observe a gap between "no in-flight task" and "task
                # registered" -- closing the check-then-act race.
                async with lock:
                    existing = _in_flight.get(key)
                    if existing is not None and not existing.done():
                        task = existing
                    else:
                        async def _execute():
                            with _log_errors("async", fn_name):
                                return await _execute_and_maybe_cache_async(cache, fn, args, kwargs, fn_name)

                        task = asyncio.ensure_future(_execute())
                        _in_flight[key] = task
                        task.add_done_callback(lambda t, k=key: _pop_if_current(k, t))

                if task is existing:
                    logger.debug("Deduplicating call for %s", cache_key)
                return await asyncio.shield(task)

        return async_wrapper
    else:
        logger.debug("Decorating sync function %s", fn_name)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            logger.debug("Executing sync function %s with read_cache", fn_name)

            with read_cache(cache, *args, **kwargs) as data:
                if data is None:
                    # Stale-while-revalidate for sync: return stale data
                    # (no background refresh possible in sync context)
                    if cache.stale_duration:
                        stale_data = read_stale_cache(cache, *args, **kwargs)
                        if stale_data is not None:
                            logger.debug("Returning stale cache for %s", fn_name)
                            return stale_data

                    logger.debug("Data is None, executing sync function %s", fn_name)
                    with _log_errors("sync", fn_name):
                        data = _execute_and_maybe_cache_sync(cache, fn, args, kwargs, fn_name)
                else:
                    logger.debug("Data is not None, returning data for %s", fn_name)
                return data

        return sync_wrapper


class _Cached:
    """Descriptor wrapper so method decorations exclude the receiver from the
    cache key. On access through an instance, Python calls ``__get__`` and we
    bind ``fn`` to that instance; the bound method absorbs ``self``/``cls``, so
    the wrapper's args — and thus the key — contain only the real arguments.
    """

    def __init__(self, cache, fn: Callable):
        self._cache = cache
        self._fn = fn
        self._wrapped = _build(cache, fn)
        update_wrapper(self, fn)

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return _Cached(self._cache, MethodType(self._fn, instance))

    def __call__(self, *args, **kwargs):
        return self._wrapped(*args, **kwargs)


def cache_fn(cache, fn: Callable) -> Callable:
    return _Cached(cache, fn)
