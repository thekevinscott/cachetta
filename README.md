# Cachetta

File-based caching with the same API across TypeScript and Python. The name is a portmanteau of *cache* and *rosetta*.

Both implementations share identical concepts -- configuration, decorators, read/write primitives, LRU, stale-while-revalidate -- differing only where language conventions require it (e.g. `snake_case` vs `camelCase`, `timedelta` vs milliseconds).

Documentation comes in three layers: this README (concise overview), the [`docs/`](docs/) folder (detailed reference, ships with the published packages), and the [hosted docs site](https://thekevinscott.github.io/cachetta/) (1:1 with `docs/`). Each `##` section below mirrors a page in `docs/`.

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

## TypeScript

Decorator and function-wrapper APIs, sync and async primitives, in-memory LRU, stale-while-revalidate, conditional caching, dynamic paths. Uses `v8.serialize` so any V8-serializable type (Maps, Sets, Dates, Buffers, typed arrays, RegExps) caches natively.

```javascript
import { Cachetta, readCache, writeCache } from 'cachetta';

const cache = new Cachetta({ path: './cache.json', duration: 60_000 });

const data = await readCache(cache);
if (!data) await writeCache(cache, await fetchExpensiveData());
```

Full reference: [`docs/javascript.md`](docs/javascript.md).

## Python

Decorator and function-wrapper APIs, sync and async primitives, in-memory LRU, stale-while-revalidate, conditional caching, dynamic paths, restricted unpickling for safety. Uses `pickle` so any picklable type (sets, tuples, dataclasses, etc.) caches natively.

```python
from cachetta import Cachetta, read_cache, write_cache
from datetime import timedelta

cache = Cachetta(path='./cache.json', duration=timedelta(minutes=1))

with read_cache(cache) as data:
    if data is None:
        data = fetch_expensive_data()
        write_cache(cache, data)
```

Full reference: [`docs/python.md`](docs/python.md).

## Migrations

Upgrade guides for breaking changes, tracked per package. Authors add a `Breaking-Change:` trailer to a commit and update the relevant `MIGRATIONS.md`; CI enforces it. The docs site auto-pulls these into per-language migration pages.

Full reference: [`docs/migrations.md`](docs/migrations.md).
