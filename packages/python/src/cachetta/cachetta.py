import asyncio
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import timedelta
from time import time
from typing import Any, Callable, Optional
from pathlib import Path
from .exceptions import CachettaError, InvalidPathError
from ._sentinel import _LRU_MISS
from .hash import hash as _hash
from .utils import logger, cache_fn, get_last_updated
from .utils.get_last_updated import async_get_last_updated


_SENTINEL = object()


@dataclass
class Cachetta:
    """A file-based cache with optional in-memory LRU, conditional caching,
    and stale-while-revalidate support.

    Args:
        path: Cache file path (str/Path) or callable returning a path.
        write: Whether to write results to cache. Default True.
        read: Whether to read from cache. Default True.
        duration: How long cache entries are considered fresh. Default 7 days.
        lru_size: Optional in-memory LRU cache size. When set, checks memory before disk.
        condition: Optional callable that receives the result and returns True to cache it.
        stale_duration: Optional duration after expiry during which stale data is returned
            while a background refresh runs.
    """
    path: str | Path | Callable[..., str | Path]
    write: bool = True
    read: bool = True
    duration: timedelta = timedelta(days=7)
    lru_size: int | None = None
    condition: Callable[[Any], bool] | None = None
    stale_duration: timedelta | None = None
    allowed_pickle_types: set[type] | None = None
    hashed: bool = False
    _lru: OrderedDict | None = field(default=None, repr=False, compare=False)
    _lru_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self):
        if self.lru_size and self._lru is None:
            self._lru = OrderedDict()

    def _lru_get(self, key: str):
        """Get a value from the in-memory LRU cache.
        Returns _LRU_MISS if LRU is disabled, key not found, or entry is expired.
        """
        if self._lru is None:
            return _LRU_MISS
        with self._lru_lock:
            entry = self._lru.get(key)
            if entry is None:
                return _LRU_MISS
            value, timestamp = entry
            age = time() - timestamp
            if age > self.duration.total_seconds():
                del self._lru[key]
                return _LRU_MISS
            # Move to end (most recently used)
            self._lru.move_to_end(key)
            return value

    def _lru_set(self, key: str, value) -> None:
        """Set a value in the in-memory LRU cache.
        No-op if LRU is disabled.
        """
        if self._lru is None or not self.lru_size:
            return
        with self._lru_lock:
            # Evict oldest if at capacity
            if len(self._lru) >= self.lru_size and key not in self._lru:
                self._lru.popitem(last=False)
            self._lru[key] = (value, time())

    def _get_path(self, *args, **kwargs) -> Path:
        """Resolve the cache path.

        When path is a callable, it is invoked with the same args/kwargs as
        the wrapped function. When path is a str/Path, it is used verbatim —
        arguments do not affect the resolved path. Use a callable path to
        vary cache files by argument, or set ``hashed=True`` to write one
        file per arg-set under ``path``.
        """
        path = self.path
        # A callable path is resolved dynamically at call time with the
        # wrapped function's args; str/Path values are used verbatim,
        # regardless of args. The `not isinstance` check narrows the
        # `str | Path | Callable[...]` union to the callable arm here, and to
        # `str | Path` after the block.
        if not isinstance(path, (str, Path)):
            resolved = Path(path(*args, **kwargs))
        else:
            resolved = Path(path)

        # `hashed=True` treats `resolved` as a folder and appends
        # `hash(*args, **kwargs)` as the child filename. The callable and the
        # hash see the same args, so the callable picks the bucket and the
        # hash names the file within it.
        if self.hashed and (args or kwargs):
            resolved = resolved / _hash(*args, **kwargs)

        if ".." in resolved.parts:
            raise InvalidPathError(
                "Path traversal detected: %s" % resolved
            )

        return resolved

    def __truediv__(self, other) -> "Cachetta":
        """Support for path-like operations using the / operator.

        Two modes:

        - ``cache / 'sub'`` returns a cache whose path is the literal
          ``base/sub`` join, used verbatim regardless of args.
        - ``cache / fn`` accepts a callable that returns a filename or
          subpath. The callable is invoked at call time with the wrapped
          function's args and joined onto the cache's base folder. Returned
          paths are validated against ``..`` traversal via the existing
          ``InvalidPathError`` check in ``_get_path``.
        """
        if callable(other):
            base = self._get_path()

            def composed(*args, **kwargs):
                return base / other(*args, **kwargs)

            logger.debug("Cache copy with callable suffix from base: %s", base)
            return replace(self, path=composed)

        new_path = self._get_path() / other
        logger.debug("Cache copy: %s", new_path)
        return replace(self, path=new_path)

    def __call__(self, fn: Optional[Callable] = None, **kwargs) -> Callable:
        """Use as a decorator or to create a configured copy.

        Usage::

            # As decorator (direct)
            @Cachetta(path="cache.json")
            def my_fn(): ...

            # As decorator with overrides
            @cache(write=False)
            def my_fn(): ...

            # As decorator with fn + overrides simultaneously
            @cache(path=lambda x: f"cache/{x}.json")
            def my_fn(x): ...
        """
        logger.debug("Cache call: %s", self)
        if not fn and len(kwargs) == 0:
            raise CachettaError("No function or kwargs provided")
        if len(kwargs) > 0:
            cache = replace(self, **kwargs)
            if fn:
                # fn + kwargs: apply overrides and wrap immediately
                return cache_fn(cache, fn)
            return lambda fn: cache(fn)
        # Reachable only when kwargs is empty and the guard above didn't fire,
        # so fn is truthy here. Assert it so the type checker can narrow
        # `Callable | None` to `Callable` for the cache_fn call.
        assert fn is not None
        return cache_fn(self, fn)

    def wrap(self, fn: Callable) -> Callable:
        """Wraps a function with caching behavior. Alias for calling the cache directly.

        Args:
            fn: The function to wrap.

        Returns:
            A cached version of the function.
        """
        return cache_fn(self, fn)

    def copy(self, **kwargs) -> "Cachetta":
        """Creates a copy of this Cachetta instance with overridden configuration.

        Args:
            **kwargs: Partial configuration to override.

        Returns:
            A new Cachetta instance with the specified overrides.
        """
        logger.debug("Cache copy: %s", kwargs)
        return replace(self, **kwargs)

    def invalidate(self, *args, **kwargs) -> None:
        """Deletes the cache file on disk and clears LRU entries for this path.
        No-op if the cache file does not exist.

        Args:
            *args, **kwargs: Arguments to resolve the cache path (when using a path function).
        """
        cache_path = self._get_path(*args, **kwargs)

        # Remove from LRU
        if self._lru is not None:
            self._lru.pop(str(cache_path), None)

        # Delete from disk
        try:
            os.unlink(cache_path)
        except FileNotFoundError:
            pass

    # Alias
    clear = invalidate

    def exists(self, *args, **kwargs) -> bool:
        """Checks whether the cache file exists on disk.

        Args:
            *args, **kwargs: Arguments to resolve the cache path.

        Returns:
            True if the cache file exists.
        """
        cache_path = self._get_path(*args, **kwargs)
        return get_last_updated(cache_path) is not None

    def age(self, *args, **kwargs) -> timedelta | None:
        """Returns the age of the cache file, or None if it does not exist.

        Args:
            *args, **kwargs: Arguments to resolve the cache path.

        Returns:
            timedelta representing age, or None.
        """
        cache_path = self._get_path(*args, **kwargs)
        mtime = get_last_updated(cache_path)
        if mtime is None:
            return None
        return timedelta(seconds=time() - mtime)

    def info(self, *args, **kwargs) -> dict:
        """Returns detailed information about the cache state.

        Args:
            *args, **kwargs: Arguments to resolve the cache path.

        Returns:
            Dict with keys: exists, age, expired, stale, path.
        """
        cache_path = self._get_path(*args, **kwargs)
        mtime = get_last_updated(cache_path)
        if mtime is None:
            return {
                "exists": False,
                "age": None,
                "expired": False,
                "stale": False,
                "path": str(cache_path),
            }
        age_seconds = time() - mtime
        duration_seconds = self.duration.total_seconds()
        expired = age_seconds >= duration_seconds
        stale = (
            expired
            and self.stale_duration is not None
            and age_seconds < (duration_seconds + self.stale_duration.total_seconds())
        )
        return {
            "exists": True,
            "age": timedelta(seconds=age_seconds),
            "expired": expired,
            "stale": stale,
            "path": str(cache_path),
        }

    async def ainvalidate(self, *args, **kwargs) -> None:
        """Async version of invalidate. Delegates disk I/O to a thread."""
        cache_path = self._get_path(*args, **kwargs)

        # Remove from LRU (synchronous, fast)
        if self._lru is not None:
            with self._lru_lock:
                self._lru.pop(str(cache_path), None)

        # Delete from disk in a thread
        try:
            await asyncio.to_thread(os.unlink, cache_path)
        except FileNotFoundError:
            pass

    aclear = ainvalidate

    async def aexists(self, *args, **kwargs) -> bool:
        """Async version of exists."""
        cache_path = self._get_path(*args, **kwargs)
        mtime = await async_get_last_updated(cache_path)
        return mtime is not None

    async def aage(self, *args, **kwargs) -> timedelta | None:
        """Async version of age."""
        cache_path = self._get_path(*args, **kwargs)
        mtime = await async_get_last_updated(cache_path)
        if mtime is None:
            return None
        return timedelta(seconds=time() - mtime)

    async def ainfo(self, *args, **kwargs) -> dict:
        """Async version of info."""
        cache_path = self._get_path(*args, **kwargs)
        mtime = await async_get_last_updated(cache_path)
        if mtime is None:
            return {
                "exists": False,
                "age": None,
                "expired": False,
                "stale": False,
                "path": str(cache_path),
            }
        age_seconds = time() - mtime
        duration_seconds = self.duration.total_seconds()
        expired = age_seconds >= duration_seconds
        stale = (
            expired
            and self.stale_duration is not None
            and age_seconds < (duration_seconds + self.stale_duration.total_seconds())
        )
        return {
            "exists": True,
            "age": timedelta(seconds=age_seconds),
            "expired": expired,
            "stale": stale,
            "path": str(cache_path),
        }
