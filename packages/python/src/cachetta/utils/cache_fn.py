import asyncio
import functools
from typing import Callable
from ..read_cache import read_cache, read_stale_cache, async_read_cache, async_read_stale_cache
from ..write_cache import write_cache, async_write_cache
from .logger import logger

# In-flight asyncio task deduplication keyed by resolved cache path
_in_flight: dict[str, asyncio.Task] = {}

# Sentinel marking a wrapper that has not been bound to a receiver. A plain
# function decoration stays unbound; a method decoration is bound to its
# instance via the descriptor protocol (see _CachedFunction.__get__).
_UNBOUND = object()


def _should_cache(cache, result) -> bool:
    """Check if result should be cached based on the condition callable."""
    if cache.condition is None:
        return True
    return cache.condition(result)


class _CachedFunction:
    """Callable wrapper returned by :func:`cache_fn`.

    Implements the descriptor protocol so method decorations are handled
    automatically: when the wrapper is defined on a class and accessed
    through an instance, Python calls ``__get__`` and we bind the receiver
    (``self``/``cls``). A bound wrapper *prepends* the receiver when calling
    the wrapped function but *excludes* it from cache-key/path resolution —
    so the key depends only on the real arguments. A plain function is never
    bound, so all of its positional arguments contribute to the key.
    """

    def __init__(self, cache, fn: Callable, receiver=_UNBOUND):
        self._cache = cache
        self._fn = fn
        self._receiver = receiver
        self._is_async = asyncio.iscoroutinefunction(fn)
        # `Callable` doesn't statically expose `__name__`; resolve a safe
        # fallback once for the log messages below.
        self._fn_name = getattr(fn, "__name__", repr(fn))
        functools.update_wrapper(self, fn)

    def __get__(self, instance, owner=None):
        """Descriptor hook for method decorations.

        ``instance is None`` means access via the class itself (e.g.
        ``Service.method``); behave as a plain callable. Access via an
        instance binds the receiver so it stays out of the cache key.
        """
        if instance is None:
            return self
        return _CachedFunction(self._cache, self._fn, receiver=instance)

    def _invoke(self, args, kwargs):
        """Call the wrapped function, prepending a bound receiver if present."""
        if self._receiver is _UNBOUND:
            return self._fn(*args, **kwargs)
        return self._fn(self._receiver, *args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self._is_async:
            return self._async_call(args, kwargs)
        return self._sync_call(args, kwargs)

    async def _async_call(self, args, kwargs):
        cache = self._cache
        fn_name = self._fn_name
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
                                result = await self._invoke(args, kwargs)
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
                    result = await self._invoke(args, kwargs)
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

    def _sync_call(self, args, kwargs):
        cache = self._cache
        fn_name = self._fn_name
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
                    data = self._invoke(args, kwargs)
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


def cache_fn(cache, fn: Callable) -> Callable:
    """Wrap ``fn`` with caching behavior.

    Returns a :class:`_CachedFunction` descriptor. Decorating a plain
    function keys the cache on all of its arguments; decorating an
    instance/class method automatically excludes the receiver
    (``self``/``cls``) from the key while still passing it to the function.
    """
    logger.debug("Decorating function %s", getattr(fn, "__name__", repr(fn)))
    return _CachedFunction(cache, fn)
