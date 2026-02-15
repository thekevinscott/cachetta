---
title: Python
nav_order: 3
---

# Cachetta for Python

File-based caching for Python.

## Install

```bash
uv add cachetta
```

Requires Python 3.12+.

## Basic Usage

Create a cache object:

```python
from datetime import timedelta
from cachetta import Cachetta

cache = Cachetta(
    read=True,
    write=True,
    path='./cache.json',
    duration=timedelta(days=1),
)
```

Read and write:

```python
from cachetta import read_cache, write_cache

def get_data():
    with read_cache(cache) as cached_data:
        if cached_data:
            return cached_data
    data = fetch_data()
    write_cache(cache, data)
    return data
```

## Decorators

Use `Cachetta` as a decorator:

```python
from cachetta import Cachetta

@Cachetta(path='/my-cache.json')
def get_data():
    return compute_expensive_value()
```

With a specific cache object:

```python
cache = Cachetta(path='/my-cache.json')

@cache
def get_data():
    return compute_expensive_value()
```

With overrides:

```python
cache = Cachetta(path='/my-cache.json')

@cache(duration=timedelta(hours=1))
def get_data():
    return compute_expensive_value()
```

## Async Support

Cachetta works seamlessly with async functions. When decorating an async function, all file I/O is automatically performed in background threads via `asyncio.to_thread()`:

```python
import asyncio
from cachetta import Cachetta

@Cachetta(path='./async-cache.json')
async def get_async_data():
    await asyncio.sleep(2)
    return {"status": "success", "data": [1, 2, 3]}
```

For explicit async cache operations:

```python
from cachetta import async_read_cache, async_write_cache

async def get_data():
    async with async_read_cache(cache) as cached_data:
        if cached_data is not None:
            return cached_data
    data = await fetch_data()
    await async_write_cache(cache, data)
    return data
```

## Function Wrapper

If you're not using decorators, wrap functions manually:

```python
cache = Cachetta(path='./my-cache.json')

def get_data():
    return compute_expensive_value()

cached_get_data = cache(get_data)
result = cached_get_data()
```

With configuration:

```python
cache = Cachetta(path='./cache')

cached_get_data = cache(get_data, duration=timedelta(hours=2))
result = cached_get_data(123)
```

## Auto Cache Keys

When a decorated function receives arguments, Cachetta automatically generates unique cache paths by hashing the arguments:

```python
@Cachetta(path='./cache/users.json')
def get_user(user_id: int):
    return fetch_user(user_id)

get_user(1)   # cached at ./cache/users-<hash1>.json
get_user(2)   # cached at ./cache/users-<hash2>.json
```

## In-Memory LRU

Add an in-memory LRU layer that is checked before hitting disk:

```python
cache = Cachetta(
    path='./cache.json',
    lru_size=100,
)
```

LRU entries respect the same `duration` as disk entries. The LRU is thread-safe for concurrent async access.

## Conditional Caching

Cache results only when a condition function returns `True`:

```python
cache = Cachetta(
    path='./cache.json',
    condition=lambda result: result is not None,
)
```

## Stale-While-Revalidate

Return expired data immediately while refreshing in the background:

```python
cache = Cachetta(
    path='./cache.json',
    duration=timedelta(hours=1),
    stale_duration=timedelta(minutes=30),
)
```

## Cache Invalidation

```python
cache = Cachetta(path='./cache.json')

cache.invalidate()  # or cache.clear()

# With arguments
cache.invalidate(user_id=123)

# Async variants
await cache.ainvalidate()
await cache.aclear()
```

## Cache Inspection

Query cache state without reading the cached data:

```python
cache = Cachetta(path='./cache.json')

cache.exists()   # True if the cache file exists
cache.age()      # timedelta or None
cache.info()     # {"exists": True, "age": timedelta(...), "expired": False, ...}

# Async variants
await cache.aexists()
await cache.aage()
await cache.ainfo()
```

## Path Operator

Use the `/` operator to build sub-paths:

```python
cache = Cachetta(path='./cache')

with read_cache(cache / 'my-data.json') as data:
    ...
```

## Dynamic Cache Paths

Specify a function for defining the path:

```python
def get_cache_path(n: int):
    return f"./cache/{n}.json"

@Cachetta(path=get_cache_path)
def foo(n: int):
    return compute_expensive_value(n)
```

## Specifying Paths

Use `copy` to create variations of a cache configuration:

```python
cache = Cachetta(path='./cache')

new_cache = cache.copy(
    read=False,
    duration=timedelta(days=2),
)
```

## Method Decorators

Use `skip_self=True` when decorating instance methods to exclude `self` from cache key hashing:

```python
class DataService:
    @Cachetta(path='./cache.json', skip_self=True)
    def get_data(self, user_id):
        return fetch_user(user_id)
```

## Error Handling

Cachetta gracefully handles corrupt cache files by yielding `None`:

```python
cache = Cachetta(path='./cache.json')

with read_cache(cache) as data:
    if data is None:
        data = fetch_fresh_data()
        write_cache(cache, data)
```

## Logging

```python
import logging

# Enable debug logging
logging.getLogger("cachetta").setLevel(logging.DEBUG)
```

## Configuration Reference

| Option | Type | Default | Description |
|---|---|---|---|
| `path` | `str \| Callable` | required | Cache file path or path function |
| `read` | `bool` | `True` | Allow reading from cache |
| `write` | `bool` | `True` | Allow writing to cache |
| `duration` | `timedelta` | 7 days | Cache TTL |
| `lru_size` | `int` | `None` | Max in-memory LRU entries |
| `condition` | `Callable` | `None` | Predicate to decide whether to cache |
| `stale_duration` | `timedelta` | `None` | Time past expiry to serve stale data |
| `skip_self` | `bool` | `False` | Exclude `self` from cache key hashing |
