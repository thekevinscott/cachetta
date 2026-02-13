from pathlib import Path
from time import time
from .get_last_updated import get_last_updated
from .is_cache_expired import is_cache_expired
from .logger import logger


def should_use_read_cache(cache, cache_path: str | Path) -> bool:
    cache_length = cache.duration.total_seconds()

    if cache_length <= 0:
        return False

    cache_time = get_last_updated(cache_path)
    if cache_time is None:
        logger.debug("Cache time is None for %s", cache_path)
        return False

    now = time()

    # Handle clock skew: if cache_time is in the future, treat as valid
    if cache_time > now:
        logger.debug("Cache time %s is in the future (now=%s), treating as valid for %s", cache_time, now, cache_path)
        return cache.read

    if is_cache_expired(cache_time, now, cache_length):
        logger.debug(
            "Cache is expired (%s, expected %s) for %s", cache_time, now + cache_length, cache_path
        )
        return False
    logger.debug(
        "Cache is not expired (%s, expected %s) for %s", cache_time, now + cache_length, cache_path
    )
    logger.debug("Cache read is %s", cache.read)
    return cache.read
