import asyncio
import os
import pickle
import tempfile
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path  # noqa: F401 (used by tests via mock patching)
from typing import Any, Generator

# Track directories already created in this process to skip redundant mkdir calls.
# Bounded OrderedDict with LRU eviction to prevent unbounded memory growth.
_CREATED_DIRS_MAX = 1000
_created_dirs: OrderedDict[str, None] = OrderedDict()
_created_dirs_lock = threading.Lock()


def write_cache(cache, data: Any, *args, **kwargs) -> None:
    if not cache:
        return

    if not cache.write:
        # Disk persistence is disabled, but the in-memory LRU is independent
        # of it: still populate it so lru_size continues to short-circuit
        # recomputation. `_lru_set` is a no-op when the LRU itself is disabled.
        if cache.lru_size:
            cache._lru_set(str(cache._get_path(*args, **kwargs)), data)
        return

    cache_path = cache._get_path(*args, **kwargs)

    # Ensure directory exists (skip if already created in this process)
    parent = str(cache_path.parent.resolve())
    with _created_dirs_lock:
        if parent in _created_dirs:
            _created_dirs.move_to_end(parent)
        else:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            _created_dirs[parent] = None
            if len(_created_dirs) > _CREATED_DIRS_MAX:
                _created_dirs.popitem(last=False)

    fd, tmp_path = tempfile.mkstemp(
        dir=cache_path.parent, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(data, f)
        os.replace(tmp_path, cache_path)
        # Populate LRU on successful write
        cache._lru_set(str(cache_path), data)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class _WriteCacheCollector:
    """Collects a value yielded back into the context manager to be written on exit."""
    def __init__(self):
        self.data = None

    def set(self, data: Any) -> None:
        self.data = data


@contextmanager
def write_cache_ctx(cache=None, *args, **kwargs) -> Generator[_WriteCacheCollector, None, None]:
    """Context manager for writing to cache, symmetric with read_cache.

    Usage::

        with write_cache_ctx(cache) as writer:
            result = do_work()
            writer.set(result)
        # Data is written to cache on exit
    """
    collector = _WriteCacheCollector()
    yield collector
    if collector.data is not None:
        write_cache(cache, collector.data, *args, **kwargs)


async def async_write_cache(cache, data: Any, *args, **kwargs) -> None:
    """Async version of write_cache. Delegates blocking I/O to a thread."""
    await asyncio.to_thread(write_cache, cache, data, *args, **kwargs)


@asynccontextmanager
async def async_write_cache_ctx(cache=None, *args, **kwargs):
    """Async version of write_cache_ctx."""
    collector = _WriteCacheCollector()
    yield collector
    if collector.data is not None:
        await async_write_cache(cache, collector.data, *args, **kwargs)
