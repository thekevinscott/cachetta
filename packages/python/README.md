# Cachetta for Python

File-based JSON caching for Python. Part of the [Cachetta](../../README.md) project, which provides the same caching API in both Python and JS/TS -- learn it once, use it in either language.

## Install

```bash
uv add cachetta
```

## Features

- **Local File Storage**: Supports local files with automatic directory creation
- **JSON Serialization**: JSON-based caching for portable, human-readable data
- **Async Support**: Non-blocking async I/O for async functions, sync support for sync functions
- **Automatic Expiration**: Cache expiration based on file modification time
- **In-Memory LRU**: Optional in-memory LRU layer for fast repeated access
- **Stale-While-Revalidate**: Serve stale data while refreshing in the background
- **Conditional Caching**: Cache only when a condition is met
- **Cache Inspection**: Check existence, age, and expiry state of cache entries
- **Auto Cache Keys**: Automatic unique paths based on function arguments
- **Flexible Paths**: Dynamic cache paths using callable functions
- **Error Handling**: Graceful handling of corrupt cache files
- **Logging**: Built-in logging for debugging

## Usage

### Basic Usage

Create a cache object:

```python
from datetime import timedelta
from cachetta import Cachetta

cache = Cachetta(
  read=True, # allow reading from local caches
  write=True, # allow writing to local caches
  path='./cache.json', # specify path to cache file
  duration=timedelta(days=1), # specify length of cache. Uses modified date on local file
)
```

Read and write to a cache object:

```python
from cachetta import read_cache, write_cache

def get_data():
  with read_cache(cache) as cached_data:
    if cached_data:
      return cached_data
    else:
      data = fetch_data() # some long running process
      write_cache(cache, data)
      return data
```

### Specifying paths

You can specify a base path for your cache folder and then quickly specify cache paths within that folder:

```python
from cachetta import read_cache, write_cache, Cachetta

cache = Cachetta(
  path='./cache', # our base cache folder
)

def get_data():
  # Use the / operator to specify sub-paths
  with read_cache(cache / 'my-data.json') as cached_data:
    ...
```

For modifying other attributes of a base `cache` object, use `copy`:

```python
cache = Cachetta(
  path='./cache', # our base cache folder
)
new_cache = cache.copy(
  read=False,
  write=False,
  duration=timedelta(days=2),
)
```

**Note**: The `copy` method is the intended public API for creating variations of cache configurations. It creates a new `Cachetta` instance with the specified overrides while preserving the original configuration.

### Decorators

You can use `Cachetta` as a decorator:

```python
import time
from cachetta import Cachetta

@Cachetta(path='/my-cache.json')
def get_data():
  parts = []
  for i in range(10):
    parts.append(i)
    time.sleep(1)

  return parts
```

You can also use a specific cache object as a decorator:

```python
import time
from cachetta import Cachetta

cache = Cachetta(path='/my-cache.json')

@cache
def get_data():
  parts = []
  for i in range(10):
    parts.append(i)
    time.sleep(1)

  return parts
```

Or with arguments:

```python
import time
from cachetta import Cachetta

cache = Cachetta(path='/my-cache.json')

@cache(duration=timedelta(hours=1))
def get_data():
  parts = []
  for i in range(10):
    parts.append(i)
    time.sleep(1)

  return parts
```

### Async Function Support

Cachetta works seamlessly with async functions. When decorating an async function, all file I/O is automatically performed in background threads via `asyncio.to_thread()`, so the event loop is never blocked:

```python
import asyncio
from cachetta import Cachetta

@Cachetta(path='./async-cache.json')
async def get_async_data():
    await asyncio.sleep(2)
    return {"status": "success", "data": [1, 2, 3]}

async def main():
    result = await get_async_data()
    print(result)
```

For explicit async cache operations outside of decorators, use the async primitives:

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

### Auto Cache Keys

When a decorated function receives arguments, Cachetta automatically generates unique cache paths by hashing the arguments:

```python
@Cachetta(path='./cache/users.json')
def get_user(user_id: int):
    return fetch_user(user_id)

get_user(1)   # cached at ./cache/users-<hash1>.json
get_user(2)   # cached at ./cache/users-<hash2>.json
```

### In-Memory LRU

Add an in-memory LRU layer that is checked before hitting disk:

```python
cache = Cachetta(
    path='./cache.json',
    lru_size=100,  # keep up to 100 entries in memory
)
```

LRU entries respect the same `duration` as disk entries. The LRU is thread-safe for concurrent async access.

### Conditional Caching

Cache results only when a condition function returns `True`:

```python
cache = Cachetta(
    path='./cache.json',
    condition=lambda result: result is not None,  # don't cache None
)
```

### Stale-While-Revalidate

Return expired (stale) data immediately while refreshing the cache in the background:

```python
cache = Cachetta(
    path='./cache.json',
    duration=timedelta(hours=1),
    stale_duration=timedelta(minutes=30),  # serve stale data up to 30min past expiry
)
```

### Cache Invalidation

Delete cache files on disk:

```python
cache = Cachetta(path='./cache.json')

cache.invalidate()  # or cache.clear()

# With arguments (when using auto cache keys or path functions)
cache.invalidate(user_id=123)

# Async variant
await cache.ainvalidate()
await cache.aclear()
```

### Cache Inspection

Query cache state without reading the cached data:

```python
cache = Cachetta(path='./cache.json')

cache.exists()          # True if the cache file exists
cache.age()             # timedelta or None
cache.info()            # {"exists": True, "age": timedelta(...), "expired": False, "stale": False, "path": "..."}

# Async variants
await cache.aexists()
await cache.aage()
await cache.ainfo()
```

### Dynamic Cache Paths

You can specify a function for defining the path as well:

```python
def get_cache_path(n: int):
  return f"./cache/{n}.json"

@Cachetta(path=get_cache_path)
def foo(n: int):
  parts = []
  for i in range(n):
    parts.append(i)
    time.sleep(1)

  return parts
```

Or, using a pre-existing cache object:

```python
cache = Cachetta(path='./cache')
def get_cache_path(n: int):
  return cache.path / f"{n}.json"

@cache.copy(path=get_cache_path)
def foo(n: int):
  parts = []
  for i in range(n):
    parts.append(i)
    time.sleep(1)

  return parts
```

### Function Wrapper (Alternative to Decorators)

If you're not using decorators, you can wrap functions manually:

```python
from cachetta import Cachetta

cache = Cachetta(path='./my-cache.json')

def get_data():
  parts = []
  for i in range(10):
    parts.append(i)
    time.sleep(1)
  return parts

# Wrap the function with caching
cached_get_data = cache(get_data)

# Usage
result = cached_get_data()
```

You can also pass configuration when wrapping:

```python
cache = Cachetta(path='./cache')

def get_data(id):
  return {"id": id, "data": "some data"}

# Wrap with specific configuration
cached_get_data = cache(get_data, duration=timedelta(hours=2))

# Usage
result = cached_get_data(123)
```

### Error Handling

Cachetta gracefully handles corrupt cache files:

```python
from cachetta import read_cache, Cachetta

cache = Cachetta(path='./corrupt-cache.json')

# If the cache file is corrupt, read_cache will yield None
with read_cache(cache) as data:
    if data is None:
        # Cache is missing or corrupt, regenerate data
        data = fetch_fresh_data()
        write_cache(cache, data)
    return data
```

### Logging

Cachetta provides detailed logging for debugging:

```python
import logging

# Enable debug logging
logging.getLogger("cachetta").setLevel(logging.DEBUG)

# Now you'll see detailed cache operations in your logs
```

### Default Configuration

- **Default duration**: 7 days (`timedelta(days=7)`)
- **Default read**: `True`
- **Default write**: `True`
- **Supported format**: JSON (`.json`)
