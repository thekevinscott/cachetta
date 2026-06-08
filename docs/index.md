---
title: Home
layout: home
nav_order: 1
---

> Rendered docs: [thekevinscott.github.io/cachetta](https://thekevinscott.github.io/cachetta/)

# Cachetta

File-based caching with the same API across TypeScript and Python. The name is a portmanteau of *cache* and *rosetta*.

Both implementations share identical concepts -- configuration, decorators, read/write primitives, LRU, stale-while-revalidate -- differing only where language conventions require it (e.g. `snake_case` vs `camelCase`, `timedelta` vs milliseconds).

## Install

```bash
# TypeScript
pnpm add cachetta

# Python
uv add cachetta
```

## Quick Start

### TypeScript

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({ path: './cache.json', duration: 60_000 });

const getData = cache(async () => {
  return await fetchExpensiveData();
});

const result = await getData();
```

### Python

```python
from cachetta import Cachetta
from datetime import timedelta

cache = Cachetta(path='./cache.json', duration=timedelta(minutes=1))

@cache
def get_data():
    return fetch_expensive_data()

result = get_data()
```

## Serialization

Cachetta uses native binary serialization in both languages -- **pickle** in Python and **v8.serialize** in TypeScript. This means:

- **Any file extension works** -- `.json`, `.cache`, `.dat`, `.yaml`, whatever you want. The extension is just a name; cachetta doesn't interpret it.
- **Any serializable type works** -- Python: sets, tuples, bytes, dataclasses, etc. TypeScript: Maps, Sets, Dates, Buffers, typed arrays, etc.
- **Not human-readable** -- the trade-off for native type support and speed is that cache files are binary. If you need to inspect cache contents, use `readCache` / `read_cache` programmatically.
- **Atomic writes** -- both languages use temp file + rename to prevent corruption from crashes or concurrent writes.

## Feature Parity

| Feature | TypeScript | Python |
|---|---|---|
| File-based cache | Yes | Yes |
| Decorator / function wrapper | Yes | Yes |
| Sync API | Yes | Yes |
| Async API | Yes (always) | Yes (separate primitives) |
| In-memory LRU layer | Yes | Yes (thread-safe) |
| Stale-while-revalidate | Yes | Yes |
| Conditional caching | Yes | Yes |
| Auto cache keys (arg hashing) | Yes | Yes |
| Dynamic path functions | Yes | Yes |
| Cache inspection (exists/age/info) | Yes | Yes |
| Cache invalidation | Yes | Yes |
| Atomic writes | Yes | Yes |
| Path traversal protection | Yes | Yes |
| Prototype pollution protection | Yes | N/A |
| Restricted deserialization | N/A (v8 is safe) | Yes |
| `/` path operator | -- | Yes |
| Method decorators (`self`/`cls` auto-excluded from key) | -- | Yes |
