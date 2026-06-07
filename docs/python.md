---
title: Python
nav_order: 3
---

> Rendered docs: [thekevinscott.github.io/cachetta/python](https://thekevinscott.github.io/cachetta/python)

# Cachetta for Python

File-based caching for Python. Uses `pickle` for native binary serialization -- any file extension works, and all picklable types (sets, tuples, bytes, dataclasses, etc.) are supported natively.

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

## Per-Argument Cache Files

A `str` or `Path` `path` is used verbatim — every call writes to the same file regardless of arguments. To key cache files by argument, pass `path` as a callable that receives the wrapped function's arguments:

```python
@Cachetta(path=lambda user_id: f'./cache/users/{user_id}.json')
def get_user(user_id: int):
    return fetch_user(user_id)

get_user(1)   # cached at ./cache/users/1.json
get_user(2)   # cached at ./cache/users/2.json
```

### Hashed mode

When you want one file per arg-set *inside* a folder (the common LLM / embedding cache shape), set `hashed=True`. The path you pass is treated as a directory, and entries are written as `{path}/{hash(*args, **kwargs)}`:

```python
cache = Cachetta(path='./cache/llm', hashed=True)

@cache
def call(prompt: str):
    return llm(prompt)

call('hello')   # ./cache/llm/<hash>
call('world')   # ./cache/llm/<otherhash>
```

`hashed` is a regular field, so it works at every entrypoint:

```python
# Constructor
cache = Cachetta(path='./cache', hashed=True)

# Per-decoration override (creates an isolated copy, base cache is not mutated)
@base_cache(hashed=True)
def call(x): ...

# Copy
hashed_cache = base_cache.copy(hashed=True)
```

If `path` is callable, it picks the folder and the hash names the file within it — the "shard by one arg, hash by all" pattern:

```python
cache = Cachetta(path=lambda model, prompt: f'./cache/{model}', hashed=True)

@cache
def call_llm(model, prompt):
    return call_api(model, prompt)

call_llm('gpt', 'hi')      # ./cache/gpt/<hash('gpt', 'hi')>
call_llm('claude', 'hi')   # ./cache/claude/<hash('claude', 'hi')>
```

`hashed` composes with `condition`, `skip_self`, async functions, and the LRU.

### Public `hash` helper

The same digest the auto-keyed path uses is exposed as `cachetta.hash`. Use it when you want to construct cache paths manually (e.g. inside a `path=` lambda that keys on a subset of args) and keep them aligned with cachetta's own keying:

```python
from cachetta import Cachetta, hash

@Cachetta(path=lambda model, prompt, *, temperature: f'cache/llm/{model}/{hash(prompt)}.pkl')
def call_llm(model, prompt, *, temperature=0.7):
    return call_api(model, prompt, temperature=temperature)
```

`hash(*args, **kwargs)` accepts any inputs (non-JSON-native values fall back to `str()`) and returns a 16-char hex string. It's a pure function — no I/O, no `Cachetta` instance required.

{: .warning }
> The Python and JS `hash` exports are **not** cross-language portable. They use different stringifiers (`json.dumps(..., default=str)` vs `JSON.stringify`) and the JS variant doesn't fold in `**kwargs`, so the same logical input produces different digests in each language. Use each language's `hash` only to align with that language's own cachetta.

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

Use the `/` operator to build sub-paths from a base cache.

### Joining a static sub-path

```python
cache = Cachetta(path='./cache')

with read_cache(cache / 'my-data.json') as data:
    ...
```

### Subfolders for auto-hashed entries

When the right-hand side is a string with no file extension, the result is a real subfolder. Auto-hashed entries from a decorated function live *inside* that folder rather than as hyphenated siblings:

```python
cache = Cachetta(path='./cache') / 'llm-calls'

@cache
def call_llm(prompt):
    ...

call_llm('hello')   # cached at ./cache/llm-calls/<hash>
call_llm('world')   # cached at ./cache/llm-calls/<other-hash>
```

### Callable right-hand side (custom layouts)

Pass a callable to defer path resolution to call time. The callable receives the wrapped function's args and returns a filename or sub-path, which is joined onto the cache's base folder:

```python
cache = Cachetta(path='./cache') / (lambda kind, ident: f'{kind}/{ident}.pkl')

@cache
def download(kind, ident):
    ...

download('pdf', '2401.12345v1')   # cached at ./cache/pdf/2401.12345v1.pkl
download('html', 'abc')           # cached at ./cache/html/abc.pkl
```

This is the right tool for custom file layouts (kind-routing, id-not-hash filenames, etc.). The callable's return is validated against `..` traversal — paths that try to escape the base folder raise `InvalidPathError`.

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

## Pickle Security

Cachetta uses a restricted unpickler that only deserializes known-safe types. Raw `pickle.load()` allows arbitrary code execution from tampered cache files -- the restricted unpickler blocks this by default.

### Default safe types

Primitives (`int`, `float`, `str`, `bytes`, `bool`, `None`, `list`, `dict`, `tuple`), `set`, `frozenset`, `complex`, `bytearray`, `range`, `slice`, `datetime` (`datetime`, `date`, `time`, `timedelta`, `timezone`), `Decimal`, `UUID`, `OrderedDict`, `defaultdict`, `deque`, and `pathlib` paths.

### Extending the allowlist

If you cache custom types (dataclasses, named tuples, etc.), add them to `allowed_pickle_types`:

```python
from cachetta import Cachetta

@dataclass
class UserProfile:
    name: str
    score: float

cache = Cachetta(
    path='./cache.dat',
    allowed_pickle_types={UserProfile},
)
```

Custom types are merged with the defaults -- you don't lose the built-in safe types.

### Error behavior

When a cache file contains a blocked type, `read_cache` logs a warning and yields `None`, the same as for corrupt data. The `UnsafePickleError` exception is available if you need to catch it explicitly:

```python
from cachetta import UnsafePickleError
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
| `allowed_pickle_types` | `set[type]` | `None` | Additional types to allow during deserialization |
