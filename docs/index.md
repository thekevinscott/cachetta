---
title: Home
layout: home
nav_order: 1
---

# Cachetta

File-based caching with the same API across JavaScript/TypeScript and Python. The name is a portmanteau of *cache* and *rosetta*.

Both implementations share identical concepts -- configuration, decorators, read/write primitives, LRU, stale-while-revalidate -- differing only where language conventions require it (e.g. `snake_case` vs `camelCase`, `timedelta` vs milliseconds).

## Install

```bash
# JavaScript/TypeScript
pnpm add cachetta

# Python
uv add cachetta
```

## Quick Start

### JavaScript/TypeScript

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

## Feature Parity

| Feature | JavaScript/TypeScript | Python |
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
| `/` path operator | -- | Yes |
| `skip_self` for method decorators | -- | Yes |
