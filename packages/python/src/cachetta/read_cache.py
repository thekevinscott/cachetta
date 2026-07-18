import asyncio
from time import time
from typing import Any, Generator
from contextlib import asynccontextmanager, contextmanager
from .safe_pickle import safe_load, UnsafePickleError
from .utils import should_use_read_cache, get_last_updated, logger


@contextmanager
def read_cache(cache=None, *args, **kwargs) -> Generator[Any, None, None]:
    if cache is None:
        logger.debug("cache is null")
        yield None
    else:
        cache_path = cache._get_path(*args, **kwargs)

        if should_use_read_cache(cache, cache_path):
            logger.debug("Using cache at %s", cache_path)
            try:
                with open(cache_path, "rb") as f:
                    data = safe_load(f, cache.allowed_pickle_types)
                yield data
                logger.debug("Used cache at %s", cache_path)
            except FileNotFoundError:
                logger.debug("cache at %s does not exist", cache_path)
                yield None
            except UnsafePickleError:
                logger.warning("Blocked unsafe pickle type at %s", cache_path)
                yield None
            except Exception:
                logger.error("Corrupt cache data at %s", cache_path)
                yield None
        else:
            logger.debug("cache.read is false, skipping cache")
            yield None


def _read_cache_file(cache_path, allowed_types=None) -> Any:
    """Read raw data from a cache file, ignoring expiry. Returns None on any failure."""
    try:
        with open(cache_path, "rb") as f:
            return safe_load(f, allowed_types)
    except UnsafePickleError:
        logger.warning("Blocked unsafe pickle type at %s", cache_path)
        return None
    except (FileNotFoundError, Exception):
        return None


def read_stale_cache(cache, *args, **kwargs) -> Any:
    """Reads stale cache data: returns data only if the file exists and is within
    the stale_duration window (expired but not yet past duration + stale_duration).
    """
    if not cache.stale_duration or not cache.read:
        return None

    cache_path = cache._get_path(*args, **kwargs)
    mtime = get_last_updated(cache_path)
    if mtime is None:
        return None

    age_seconds = time() - mtime
    duration_seconds = cache.duration.total_seconds()
    stale_seconds = cache.stale_duration.total_seconds()
    is_expired = age_seconds >= duration_seconds
    is_within_stale = age_seconds < (duration_seconds + stale_seconds)

    if is_expired and is_within_stale:
        logger.debug("Returning stale cache for %s (age: %.1fs)", cache_path, age_seconds)
        return _read_cache_file(cache_path, cache.allowed_pickle_types)

    return None


def _blocking_read_impl(cache, cache_path):
    """Extracted blocking disk I/O for thread delegation in async_read_cache."""
    logger.debug("Using cache at %s", cache_path)
    try:
        with open(cache_path, "rb") as f:
            data = safe_load(f, cache.allowed_pickle_types)
        return data
    except FileNotFoundError:
        logger.debug("cache at %s does not exist", cache_path)
        return None
    except UnsafePickleError:
        logger.warning("Blocked unsafe pickle type at %s", cache_path)
        return None
    except Exception:
        logger.error("Corrupt cache data at %s", cache_path)
        return None


@asynccontextmanager
async def async_read_cache(cache=None, *args, **kwargs):
    """Async version of read_cache. Blocking disk I/O is delegated to
    asyncio.to_thread().
    """
    if cache is None:
        logger.debug("cache is null")
        yield None
    else:
        cache_path = cache._get_path(*args, **kwargs)

        if should_use_read_cache(cache, cache_path):
            data = await asyncio.to_thread(_blocking_read_impl, cache, cache_path)
            yield data
        else:
            logger.debug("cache.read is false, skipping cache")
            yield None


async def async_read_stale_cache(cache, *args, **kwargs) -> Any:
    """Async version of read_stale_cache. Delegates blocking I/O to a thread."""
    return await asyncio.to_thread(read_stale_cache, cache, *args, **kwargs)
