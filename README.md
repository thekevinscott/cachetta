# Cachetta

File-based caching with the same API across JavaScript/TypeScript and Python. The name is a portmanteau of *cache* and *rosetta*.

Both implementations share identical concepts -- configuration, decorators, read/write primitives, LRU, stale-while-revalidate -- differing only where language conventions require it (e.g. `snake_case` vs `camelCase`, `timedelta` vs milliseconds).

[Full documentation](https://thekevinscott.github.io/cachetta/)

## JavaScript / TypeScript

```bash
pnpm add cachetta
```

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({ path: './cache.json', duration: 60_000 });

// As a wrapper
const getData = cache(async () => {
  return await fetchExpensiveData();
});
const result = await getData();

// Or read/write directly
import { readCache, writeCache } from 'cachetta';

const data = await readCache(cache);
if (!data) {
  await writeCache(cache, await fetchExpensiveData());
}
```

[JavaScript/TypeScript docs](https://thekevinscott.github.io/cachetta/javascript) | [Package README](packages/javascript/)

## Python

```bash
uv add cachetta
```

```python
from cachetta import Cachetta, read_cache, write_cache
from datetime import timedelta

cache = Cachetta(path='./cache.json', duration=timedelta(minutes=1))

# As a decorator
@cache
def get_data():
    return fetch_expensive_data()

result = get_data()

# Or read/write directly
with read_cache(cache) as data:
    if data is None:
        data = fetch_expensive_data()
        write_cache(cache, data)
```

[Python docs](https://thekevinscott.github.io/cachetta/python) | [Package README](packages/python/)
