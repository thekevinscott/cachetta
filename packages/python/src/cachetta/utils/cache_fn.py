import asyncio
from typing import Callable
from functools import wraps
from ..read_cache import read_cache, read_stale_cache, async_read_cache, async_read_stale_cache
from ..write_cache import write_cache, async_write_cache
from .logger import logger

# In-flight asyncio task deduplication keyed by resolved cache path
_in_flight: dict[str, asyncio.Task] = {}


def _resolve_args(cache, args, kwargs):
    """If skip_self is set, strip the first positional arg for cache path resolution
    but keep original args for function invocation."""
    if cache.skip_self and args:
        return args[1:], kwargs
    return args, kwargs


def _should_cache(cache, result) -> bool:
    """Check if result should be cached based on the condition callable."""
    if cache.condition is None:
        return True
    return cache.condition(result)


def cache_fn(cache, fn: Callable) -> Callable:
    if asyncio.iscoroutinefunction(fn):
        logger.debug("Decorating async function %s", fn.__name__)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            logger.debug("Executing async function %s with read_cache", fn.__name__)
            cache_args, cache_kwargs = _resolve_args(cache, args, kwargs)

            async with async_read_cache(cache, *cache_args, **cache_kwargs) as data:
                if data is not None:
                    logger.debug("Data is not None, returning data for %s", fn.__name__)
                    return data

                cache_key = str(cache._get_path(*cache_args, **cache_kwargs))

                # Stale-while-revalidate: return stale data and refresh in background
                if cache.stale_duration:
                    stale_data = await async_read_stale_cache(cache, *cache_args, **cache_kwargs)
                    if stale_data is not None:
                        if cache_key not in _in_flight:
                            async def _bg_refresh():
                                try:
                                    result = await fn(*args, **kwargs)
                                    if _should_cache(cache, result):
                                        await async_write_cache(cache, result, *cache_args, **cache_kwargs)
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
                        logger.debug("Executed async function %s, writing data to %s", fn.__name__, cache.path)
                        if _should_cache(cache, result):
                            await async_write_cache(cache, result, *cache_args, **cache_kwargs)
                            logger.debug("Wrote data for %s to %s", fn.__name__, cache.path)
                        return result
                    except Exception as e:
                        logger.error("Error executing async function %s: %s", fn.__name__, e)
                        raise

                task = asyncio.ensure_future(_execute())
                _in_flight[cache_key] = task
                try:
                    return await task
                finally:
                    _in_flight.pop(cache_key, None)

        return async_wrapper
    else:
        logger.debug("Decorating sync function %s", fn.__name__)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            logger.debug("Executing sync function %s with read_cache", fn.__name__)
            cache_args, cache_kwargs = _resolve_args(cache, args, kwargs)

            with read_cache(cache, *cache_args, **cache_kwargs) as data:
                if data is None:
                    # Stale-while-revalidate for sync: return stale data
                    # (no background refresh possible in sync context)
                    if cache.stale_duration:
                        stale_data = read_stale_cache(cache, *cache_args, **cache_kwargs)
                        if stale_data is not None:
                            logger.debug("Returning stale cache for %s", fn.__name__)
                            return stale_data

                    logger.debug("Data is None, executing sync function %s", fn.__name__)
                    try:
                        data = fn(*args, **kwargs)
                        logger.debug("Executed sync function %s, writing data to %s", fn.__name__, cache.path)
                        if _should_cache(cache, data):
                            write_cache(cache, data, *cache_args, **cache_kwargs)
                            logger.debug("Wrote data for %s to %s", fn.__name__, cache.path)
                    except Exception as e:
                        logger.error("Error executing sync function %s: %s", fn.__name__, e)
                        raise
                else:
                    logger.debug("Data is not None, returning data for %s", fn.__name__)
                return data

        return sync_wrapper
