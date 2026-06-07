---
title: TypeScript
nav_order: 2
---

> Rendered docs: [thekevinscott.github.io/cachetta/javascript](https://thekevinscott.github.io/cachetta/javascript)

# Cachetta for TypeScript

File-based caching for TypeScript. Uses `v8.serialize` for native binary serialization -- any file extension works, and all V8-serializable types (Maps, Sets, Dates, Buffers, typed arrays, RegExps, etc.) are supported natively.

## Install

```bash
pnpm add cachetta
```

## Basic Usage

Create a cache object:

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({
  read: true,
  write: true,
  path: './cache.json',
  duration: 24 * 60 * 60 * 1000, // 1 day in milliseconds
});
```

Read and write:

```javascript
import { readCache, writeCache } from 'cachetta';

async function getData() {
  const cachedData = await readCache(cache);
  if (cachedData) {
    return cachedData;
  }
  const data = await fetchData();
  await writeCache(cache, data);
  return data;
}
```

## Decorators

Use `Cachetta` as a decorator (requires experimental decorators):

```javascript
import { Cachetta } from 'cachetta';

class DataService {
  @Cachetta({ path: '/my-cache.json' })
  async getData() {
    return await fetchData();
  }
}
```

With a specific cache object:

```javascript
const cache = new Cachetta({ path: '/my-cache.json' });

class DataService {
  @cache
  async getData() {
    return await fetchData();
  }
}
```

Or with overrides:

```javascript
const cache = new Cachetta({ path: '/my-cache.json' });

class DataService {
  @cache({ duration: 1000 })
  async getData() {
    return await fetchData();
  }
}
```

{: .warning }
> Decorated functions always return Promises, even if the original function is synchronous. Always use `await` when calling decorated functions.

## Function Wrapper

If you're not using decorators, wrap functions manually:

```javascript
const cache = new Cachetta({ path: './my-cache.json' });

const cachedGetData = cache(async () => {
  return await fetchData();
});

const result = await cachedGetData();
```

With configuration:

```javascript
const cache = new Cachetta({ path: './cache' });

const cachedGetData = cache(getData, {
  path: (id) => `./cache/data-${id}.json`,
  duration: 5000
});

const result = await cachedGetData(123);
```

## Sync API

All methods have synchronous counterparts:

```javascript
import { Cachetta, writeCacheSync, readCacheSync } from 'cachetta';

const cache = new Cachetta({ path: './cache.json' });

// Sync read/write
writeCacheSync(cache, { data: 1 });
const data = readCacheSync(cache);

// Sync inspection
cache.existsSync();
cache.ageSync();
cache.infoSync();

// Sync invalidation
cache.invalidateSync();

// Sync function wrapping
const cachedFn = cache.wrapSync(() => computeExpensiveValue());
const result = cachedFn();
```

## Per-Argument Cache Files

A string `path` is used verbatim — every call writes to the same file regardless of arguments. To key cache files by argument, pass `path` as a function that receives the wrapped function's arguments:

```javascript
const cache = new Cachetta({ path: (userId) => `./cache/users/${userId}.json` });

const getUser = cache((userId) => fetchUser(userId));

await getUser(1);   // cached at ./cache/users/1.json
await getUser(2);   // cached at ./cache/users/2.json
```

### Public `hash` helper

The same digest the auto-keyed path uses is exposed as a top-level `hash` export. Use it when you want to construct cache paths manually (e.g. inside a `path:` callable that keys on a subset of args) and keep them aligned with cachetta's own keying:

```javascript
import { Cachetta, hash } from 'cachetta';

const cache = new Cachetta({
  path: (model, prompt, opts) => `./cache/llm/${model}/${hash(prompt)}.json`,
});

const callLLM = cache(async (model, prompt, opts) => callApi(model, prompt, opts));
```

`hash(...args)` accepts any JSON-serializable arguments and returns a 16-char hex string. It's a pure function — no I/O, no `Cachetta` instance required.

{: .warning }
> The JS and Python `hash` exports are **not** cross-language portable. They use different stringifiers (`JSON.stringify` vs `json.dumps(..., default=str)`) and the Python variant also folds in `**kwargs`, so the same logical input produces different digests in each language. Use each language's `hash` only to align with that language's own cachetta.

## In-Memory LRU

Add an in-memory LRU layer that is checked before hitting disk:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  lruSize: 100,
});
```

LRU entries respect the same `duration` as disk entries and use lazy expiration.

## Conditional Caching

Cache results only when a condition function returns `true`:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  condition: (result) => result !== null,
});
```

## Stale-While-Revalidate

Return expired data immediately while refreshing in the background:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  duration: 60 * 60 * 1000,        // 1 hour
  staleDuration: 30 * 60 * 1000,   // serve stale up to 30min past expiry
});
```

## Cache Invalidation

```javascript
const cache = new Cachetta({ path: './cache.json' });

await cache.invalidate();  // or cache.clear()
cache.invalidateSync();    // sync variant

// With arguments (when using path functions)
await cache.invalidate('userId');
```

## Cache Inspection

Query cache state without reading the cached data:

```javascript
const cache = new Cachetta({ path: './cache.json' });

await cache.exists();   // true if the cache file exists
await cache.age();      // age in milliseconds, or null
await cache.info();     // { exists, age, expired, stale, path }

// Sync variants
cache.existsSync();
cache.ageSync();
cache.infoSync();
```

## Dynamic Cache Paths

Specify a function for defining the path:

```javascript
function getCachePath(n) {
  return `./cache/${n}.json`;
}

@Cachetta({ path: getCachePath })
async function foo(n) {
  return computeExpensiveValue(n);
}
```

## Specifying Paths

Use `copy` to create variations of a cache configuration:

```javascript
const cache = new Cachetta({ path: './cache' });

const newCache = cache.copy({
  read: false,
  duration: 2 * 24 * 60 * 60 * 1000,
});
```

## Error Handling

Cachetta gracefully handles corrupt cache files by returning `null`:

```javascript
const cache = new Cachetta({ path: './cache.json' });

const data = await readCache(cache);
if (data === null) {
  // Cache is missing or corrupt
  const freshData = await fetchFreshData();
  await writeCache(cache, freshData);
}
```

## Logging

```javascript
import { setLogLevel, setLogger } from 'cachetta';

// Enable debug logging
setLogLevel('debug');  // 'error', 'warn', 'info', 'debug'

// Or use a custom logger
setLogger({
  debug: (msg) => myLogger.debug(msg),
  info: (msg) => myLogger.info(msg),
  warn: (msg) => myLogger.warn(msg),
  error: (msg) => myLogger.error(msg),
});
```

## Configuration Reference

| Option | Type | Default | Description |
|---|---|---|---|
| `path` | `string \| Function` | required | Cache file path or path function |
| `read` | `boolean` | `true` | Allow reading from cache |
| `write` | `boolean` | `true` | Allow writing to cache |
| `duration` | `number` | 7 days (ms) | Cache TTL in milliseconds |
| `lruSize` | `number` | undefined | Max in-memory LRU entries |
| `condition` | `Function` | undefined | Predicate to decide whether to cache |
| `staleDuration` | `number` | undefined | Time past expiry to serve stale data |
