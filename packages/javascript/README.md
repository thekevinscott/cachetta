# Cachetta for TypeScript

File-based caching for TypeScript. Part of the [Cachetta](https://github.com/thekevinscott/cachetta) project, which provides the same caching API in TypeScript and Python -- learn it once, use it in either language.

Three doc layers: this README (overview), the [`docs/`](./docs/) folder bundled with this package, and the [hosted docs site](https://thekevinscott.github.io/cachetta/javascript). Each `##` below mirrors a section in [`docs/javascript.md`](./docs/javascript.md).

## Install

```bash
pnpm add cachetta
```

## Basic Usage

```javascript
import { Cachetta, readCache, writeCache } from 'cachetta';

const cache = new Cachetta({
  path: './cache.json',
  duration: 24 * 60 * 60 * 1000, // 1 day
});

const data = await readCache(cache);
if (!data) await writeCache(cache, await fetchData());
```

[→ Basic Usage](./docs/javascript.md#basic-usage)

## Decorators

```javascript
class DataService {
  @Cachetta({ path: '/my-cache.json' })
  async getData() { return await fetchData(); }
}
```

Decorated functions always return Promises, even when the original is sync.

[→ Decorators](./docs/javascript.md#decorators)

## Function Wrapper

```javascript
const cache = new Cachetta({ path: './my-cache.json' });
const cachedGetData = cache(async () => fetchData());
const result = await cachedGetData();
```

[→ Function Wrapper](./docs/javascript.md#function-wrapper)

## Sync API

```javascript
import { writeCacheSync, readCacheSync } from 'cachetta';
writeCacheSync(cache, { data: 1 });
const data = readCacheSync(cache);
cache.invalidateSync();
```

[→ Sync API](./docs/javascript.md#sync-api)

## Per-Argument Cache Files

Pass a function `path` to vary the cache file by argument. A string `path` is used verbatim regardless of arguments.

[→ Per-Argument Cache Files](./docs/javascript.md#per-argument-cache-files)

## Conditional Caching

```javascript
const cache = new Cachetta({
  path: './cache.json',
  condition: (result) => result !== null,
});
```

[→ Conditional Caching](./docs/javascript.md#conditional-caching)

## Stale-While-Revalidate

```javascript
const cache = new Cachetta({
  path: './cache.json',
  duration: 60 * 60 * 1000,
  staleDuration: 30 * 60 * 1000,
});
```

[→ Stale-While-Revalidate](./docs/javascript.md#stale-while-revalidate)

## Cache Invalidation

```javascript
await cache.invalidate();  // or cache.clear()
```

[→ Cache Invalidation](./docs/javascript.md#cache-invalidation)

## Cache Inspection

```javascript
await cache.exists();  // boolean
await cache.age();     // ms or null
await cache.info();    // { exists, age, expired, stale, path }
```

[→ Cache Inspection](./docs/javascript.md#cache-inspection)

## Dynamic Cache Paths

```javascript
@Cachetta({ path: (n) => `./cache/${n}.json` })
async function foo(n) { /* ... */ }
```

[→ Dynamic Cache Paths](./docs/javascript.md#dynamic-cache-paths)

## Specifying Paths

```javascript
const newCache = cache.copy({ read: false, duration: 2 * 24 * 60 * 60 * 1000 });
```

[→ Specifying Paths](./docs/javascript.md#specifying-paths)

## Error Handling

`readCache` returns `null` for missing or corrupt files.

[→ Error Handling](./docs/javascript.md#error-handling)

## Logging

```javascript
import { setLogLevel, setLogger } from 'cachetta';
setLogLevel('debug');
```

[→ Logging](./docs/javascript.md#logging)

## Configuration Reference

| Option | Type | Default |
|---|---|---|
| `path` | `string \| Function` | required |
| `read` / `write` | `boolean` | `true` |
| `duration` | `number` (ms) | 7 days |
| `condition` | `Function` | undefined |
| `staleDuration` | `number` | undefined |

[→ Configuration Reference](./docs/javascript.md#configuration-reference)
