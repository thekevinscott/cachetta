import asyncio
from types import MethodType
from typing import Callable
from functools import update_wrapper, wraps
from ..read_cache import read_cache, read_stale_cache, async_read_cache, async_read_stale_cache
from ..write_cache import write_cache, async_write_cache
from .logger import logger

# In-flight asyncio task deduplication keyed by resolved cache path
_in_flight: dict[str, asyncio.Task] = {}


def _should_cache(cache, result) -> bool:
    """Check if result should be cached based on the condition callable."""
    if cache.condition is None:
        return True
    return cache.condition(result)


def _build(cache, fn: Callable) -> Callable:
    # `Callable` doesn't statically expose `__name__`; resolve it once (with a
    # safe fallback) for the log messages below.
    fn_name = getattr(fn, "__name__", repr(fn))
    if asyncio.iscoroutinefunction(fn):
        logger.debug("Decorating async function %s", fn_name)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            logger.debug("Executing async function %s with read_cache", fn_name)

            async with async_read_cache(cache, *args, **kwargs) as data:
                if data is not None:
                    logger.debug("Data is not None, returning data for %s", fn_name)
                    return data

                cache_key = str(cache._get_path(*args, **kwargs))

                # Stale-while-revalidate: return stale data and refresh in background
                if cache.stale_duration:
                    stale_data = await async_read_stale_cache(cache, *args, **kwargs)
                    if stale_data is not None:
                        if cache_key not in _in_flight:
                            async def _bg_refresh():
                                try:
                                    result = await fn(*args, **kwargs)
                                    if _should_cache(cache, result):
                                        await async_write_cache(cache, result, *args, **kwargs)
                                except Exception as e:
                                    logger.error("Background revalidation failed for %s: %s", cache_key, e)

                            task = asyncio.ensure_future(_bg_refresh())
                            _in_flight[cache_key] = task
                            task.add_done_callback(lambda _: _in_flight.pop(cache_key, None))
                        return stale_data

                # If there's already an in-flight call for this path, await it
                existing = _in_flight.get(cache_key)
                if existing is not None and not existing.done():
                    logger.debug("Deduplicating call for %s", cache_key)
                    return await asyncio.shield(existing)

                async def _execute():
                    try:
                        result = await fn(*args, **kwargs)
                        logger.debug("Executed async function %s, writing data to %s", fn_name, cache.path)
                        if _should_cache(cache, result):
                            await async_write_cache(cache, result, *args, **kwargs)
                            logger.debug("Wrote data for %s to %s", fn_name, cache.path)
                        return result
                    except Exception as e:
                        logger.error("Error executing async function %s: %s", fn_name, e)
                        raise

                task = asyncio.ensure_future(_execute())
                _in_flight[cache_key] = task
                try:
                    return await task
                finally:
                    _in_flight.pop(cache_key, None)

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
                    try:
                        data = fn(*args, **kwargs)
                        logger.debug("Executed sync function %s, writing data to %s", fn_name, cache.path)
                        if _should_cache(cache, data):
                            write_cache(cache, data, *args, **kwargs)
                            logger.debug("Wrote data for %s to %s", fn_name, cache.path)
                    except Exception as e:
                        logger.error("Error executing sync function %s: %s", fn_name, e)
                        raise
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
        # Bind fn to the instance: the bound method absorbs self/cls, so the
        # wrapper's args (and thus the cache key) exclude the receiver.
        return _Cached(self._cache, MethodType(self._fn, instance))

    def __call__(self, *args, **kwargs):
        return self._wrapped(*args, **kwargs)


def cache_fn(cache, fn: Callable) -> Callable:
    return _Cached(cache, fn)
