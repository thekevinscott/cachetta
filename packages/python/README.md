# Cachetta for Python

File-based caching for Python. Part of the [Cachetta](https://github.com/thekevinscott/cachetta) project, which provides the same caching API in Python and TypeScript -- learn it once, use it in either language.

Three doc layers: this README (overview), the [`docs/`](./docs/) folder bundled with this package, and the [hosted docs site](https://thekevinscott.github.io/cachetta/python). Each `##` below mirrors a section in [`docs/python.md`](./docs/python.md).

Requires Python 3.10+.

## Install

```bash
uv add cachetta
```

## Basic Usage

```python
from datetime import timedelta
from cachetta import Cachetta, read_cache, write_cache

cache = Cachetta(path='./cache.json', duration=timedelta(days=1))

with read_cache(cache) as data:
    if data is None:
        data = fetch_data()
        write_cache(cache, data)
```

[→ Basic Usage](./docs/python.md#basic-usage)

## Decorators

```python
@Cachetta(path='/my-cache.json')
def get_data():
    return compute_expensive_value()
```

[→ Decorators](./docs/python.md#decorators)

## Async Support

```python
@Cachetta(path='./async-cache.json')
async def get_async_data():
    return await fetch_data()
```

I/O for decorated async functions runs via `asyncio.to_thread()`. Explicit primitives are `async_read_cache` / `async_write_cache`.

[→ Async Support](./docs/python.md#async-support)

## Function Wrapper

```python
cache = Cachetta(path='./my-cache.json')
cached_get_data = cache(get_data)
result = cached_get_data()
```

[→ Function Wrapper](./docs/python.md#function-wrapper)

## Per-Argument Cache Files

Pass a callable `path` to vary the cache file by argument. A `str`/`Path` `path` is used verbatim regardless of arguments.

[→ Per-Argument Cache Files](./docs/python.md#per-argument-cache-files)

## Conditional Caching

```python
cache = Cachetta(path='./cache.json', condition=lambda r: r is not None)
```

[→ Conditional Caching](./docs/python.md#conditional-caching)

## Stale-While-Revalidate

```python
cache = Cachetta(
    path='./cache.json',
    duration=timedelta(hours=1),
    stale_duration=timedelta(minutes=30),
)
```

[→ Stale-While-Revalidate](./docs/python.md#stale-while-revalidate)

## Cache Invalidation

```python
cache.invalidate()       # or cache.clear()
await cache.ainvalidate()
```

[→ Cache Invalidation](./docs/python.md#cache-invalidation)

## Cache Inspection

```python
cache.exists()  # bool
cache.age()     # timedelta | None
cache.info()    # dict
```

Async variants: `aexists`, `aage`, `ainfo`.

[→ Cache Inspection](./docs/python.md#cache-inspection)

## Path Operator

```python
cache = Cachetta(path='./cache')
with read_cache(cache / 'my-data.json') as data:
    ...

# Subfolder for auto-hashed entries
sub = cache / 'llm-calls'

# Callable for custom layouts (resolved at call time)
custom = cache / (lambda kind, ident: f'{kind}/{ident}.pkl')
```

[→ Path Operator](./docs/python.md#path-operator)

## Dynamic Cache Paths

```python
@Cachetta(path=lambda n: f"./cache/{n}.json")
def foo(n: int):
    ...
```

[→ Dynamic Cache Paths](./docs/python.md#dynamic-cache-paths)

## Specifying Paths

```python
new_cache = cache.copy(read=False, duration=timedelta(days=2))
```

[→ Specifying Paths](./docs/python.md#specifying-paths)

## Method Decorators

Methods work as-is; the receiver (`self`/`cls`) is not part of the cache key.

```python
class DataService:
    @Cachetta(path=lambda user_id: f'./cache/{user_id}.json')
    def get_data(self, user_id):
        ...
```

[→ Method Decorators](./docs/python.md#method-decorators)

## Pickle Security

A restricted unpickler blocks arbitrary code execution from tampered cache files. Add custom types to `allowed_pickle_types` to whitelist them.

```python
cache = Cachetta(path='./cache.dat', allowed_pickle_types={UserProfile})
```

[→ Pickle Security](./docs/python.md#pickle-security)

## Error Handling

`read_cache` yields `None` for missing or corrupt files.

[→ Error Handling](./docs/python.md#error-handling)

## Logging

```python
import logging
logging.getLogger("cachetta").setLevel(logging.DEBUG)
```

[→ Logging](./docs/python.md#logging)

## Configuration Reference

| Option | Type | Default |
|---|---|---|
| `path` | `str \| Callable` | required |
| `read` / `write` | `bool` | `True` |
| `duration` | `timedelta` | 7 days |
| `condition` | `Callable` | `None` |
| `stale_duration` | `timedelta` | `None` |
| `allowed_pickle_types` | `set[type]` | `None` |

[→ Configuration Reference](./docs/python.md#configuration-reference)
