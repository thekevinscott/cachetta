# Cachetta for JavaScript/TypeScript

File-based JSON caching for JavaScript and TypeScript. Part of the [Cachetta](../../README.md) project, which provides the same caching API in both JS/TS and Python -- learn it once, use it in either language.

## Install

```bash
pnpm add cachetta
```

## Features

- **Local File Storage**: Supports local files with automatic directory creation
- **JSON Serialization**: JSON-based caching (native JavaScript support)
- **Async Support**: Works with both synchronous and asynchronous functions
- **Automatic Expiration**: Cache expiration based on file modification time
- **In-Memory LRU**: Optional in-memory LRU layer for fast repeated access
- **Stale-While-Revalidate**: Serve stale data while refreshing in the background
- **Conditional Caching**: Cache only when a condition is met
- **Cache Inspection**: Check existence, age, and expiry state of cache entries
- **Auto Cache Keys**: Automatic unique paths based on function arguments
- **Flexible Paths**: Dynamic cache paths using functions
- **Error Handling**: Graceful handling of corrupt cache files
- **Logging**: Built-in logging for debugging

## Usage

### Basic Usage

Create a cache object:

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({
  read: true, // allow reading from local caches
  write: true, // allow writing to local caches
  path: './cache.json', // specify path to cache file
  duration: 24 * 60 * 60 * 1000, // specify length of cache in milliseconds (1 day)
});
```

Read and write to a cache object:

```javascript
import { readCache, writeCache } from 'cachetta';

async function getData() {
  const cachedData = await readCache(cache);
  if (cachedData) {
    return cachedData;
  } else {
    const data = await fetchData(); // some long running process
    await writeCache(cache, data);
    return data;
  }
}
```

### Specifying paths

You can specify a base path for your cache folder and then quickly specify cache paths within that folder:

```javascript
import { readCache, writeCache, Cachetta } from 'cachetta';
import path from 'path';

const cache = new Cachetta({
  path: './cache', // our base cache folder
});

async function getData() {
  // specify your file path like below:
  const cachePath = path.join(cache.path, 'my-data.json');
  const cachedData = await readCache(cache.copy({ path: cachePath }));
  // ...
}
```

For modifying other attributes of a base `cache` object, use `copy`:

```javascript
const cache = new Cachetta({
  path: './cache', // our base cache folder
});

const newCache = cache.copy({
  read: false,
  write: false,
  duration: 2 * 24 * 60 * 60 * 1000, // 2 days
});
```

**Note**: The `copy` method is the intended public API for creating variations of cache configurations. It creates a new `Cachetta` instance with the specified overrides while preserving the original configuration.

### Decorators

You can use `Cachetta` as a decorator (requires experimental decorators):

```javascript
import { Cachetta } from 'cachetta';

class DataService {
  @Cachetta({ path: '/my-cache.json' })
  async getData() {
    const parts = [];
    for (let i = 0; i < 10; i++) {
      parts.push(i);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return parts;
  }
}
```

You can also use a specific cache object as a decorator:

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({ path: '/my-cache.json' });

class DataService {
  @cache
  async getData() {
    const parts = [];
    for (let i = 0; i < 10; i++) {
      parts.push(i);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return parts;
  }
}
```

Or with arguments:

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({ path: '/my-cache.json' });

class DataService {
  @cache({ duration: 1000 })
  async getData() {
    const parts = [];
    for (let i = 0; i < 10; i++) {
      parts.push(i);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return parts;
  }
}
```

**Important Note**: Decorated functions always return Promises, even if the original function is synchronous. This is because the caching mechanism involves async file operations. Always use `await` when calling decorated functions:

```javascript
const cache = new Cachetta({ path: './cache.json' });

// Even though this is a sync function, the decorated version returns a Promise
const cachedFunction = cache.call(() => {
  return "Hello World";
});

// Must await the result
const result = await cachedFunction();
console.log(result); // "Hello World"
```

### Async Function Support

Cachetta works seamlessly with async functions:

```javascript
import { Cachetta } from 'cachetta';

@Cachetta({ path: './async-cache.json' })
async function getAsyncData() {
  // Simulate async API call
  await new Promise(resolve => setTimeout(resolve, 2000));
  return { status: "success", data: [1, 2, 3] };
}

// Usage
async function main() {
  const result = await getAsyncData();
  console.log(result);
}
```

### Auto Cache Keys

When a wrapped function receives arguments, Cachetta automatically generates unique cache paths by hashing the arguments:

```javascript
const cache = new Cachetta({ path: './cache/users.json' });

const getUser = cache((userId) => fetchUser(userId));

await getUser(1);   // cached at ./cache/users-<hash1>.json
await getUser(2);   // cached at ./cache/users-<hash2>.json
```

### In-Memory LRU

Add an in-memory LRU layer that is checked before hitting disk:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  lruSize: 100,  // keep up to 100 entries in memory
});
```

LRU entries respect the same `duration` as disk entries and use lazy expiration (evicted on access, not via background timers).

### Conditional Caching

Cache results only when a condition function returns `true`:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  condition: (result) => result !== null,  // don't cache null
});
```

### Stale-While-Revalidate

Return expired (stale) data immediately while refreshing the cache in the background:

```javascript
const cache = new Cachetta({
  path: './cache.json',
  duration: 60 * 60 * 1000,           // 1 hour
  staleDuration: 30 * 60 * 1000,      // serve stale data up to 30min past expiry
});
```

### Cache Invalidation

Delete cache files on disk:

```javascript
const cache = new Cachetta({ path: './cache.json' });

await cache.invalidate();  // or cache.clear()

// With arguments (when using path functions)
await cache.invalidate('userId');
```

### Cache Inspection

Query cache state without reading the cached data:

```javascript
const cache = new Cachetta({ path: './cache.json' });

await cache.exists();   // true if the cache file exists
await cache.age();      // age in milliseconds, or null
await cache.info();     // { exists: true, age: 1234, expired: false, stale: false, path: "..." }
```

### Dynamic Cache Paths

You can specify a function for defining the path as well:

```javascript
function getCachePath(n) {
  return `./cache/${n}.json`;
}

@Cachetta({ path: getCachePath })
async function foo(n) {
  const parts = [];
  for (let i = 0; i < n; i++) {
    parts.push(i);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return parts;
}
```

Or, using a pre-existing cache object:

```javascript
const cache = new Cachetta({ path: './cache' });

function getCachePath(n) {
  return path.join(cache.path, `${n}.json`);
}

@cache.copy({ path: getCachePath })
async function foo(n) {
  const parts = [];
  for (let i = 0; i < n; i++) {
    parts.push(i);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return parts;
}
```

### Function Wrapper (Alternative to Decorators)

If you're not using decorators, you can wrap functions manually:

```javascript
import { Cachetta } from 'cachetta';

const cache = new Cachetta({ path: './my-cache.json' });

async function getData() {
  const parts = [];
  for (let i = 0; i < 10; i++) {
    parts.push(i);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return parts;
}

// Wrap the function with caching
const cachedGetData = cache(getData);

// Usage - always await the result, even for sync functions
const result = await cachedGetData();
```

You can also pass configuration when wrapping:

```javascript
const cache = new Cachetta({ path: './cache' });

function getData(id) {
  return { id, data: 'some data' };
}

// Wrap with specific configuration
const cachedGetData = cache(getData, {
  path: (id) => `./cache/data-${id}.json`,
  duration: 5000
});

// Usage
const result = await cachedGetData(123);
```

**Note**: Wrapped functions always return Promises, even if the original function is synchronous, due to the async nature of file operations in the caching mechanism.

### Error Handling

Cachetta gracefully handles corrupt cache files:

```javascript
import { readCache, writeCache, Cachetta } from 'cachetta';

const cache = new Cachetta({ path: './corrupt-cache.json' });

// If the cache file is corrupt, readCache will return null
async function getData() {
  const data = await readCache(cache);
  if (data === null) {
    // Cache is missing or corrupt, regenerate data
    const freshData = await fetchFreshData();
    await writeCache(cache, freshData);
    return freshData;
  }
  return data;
}
```

### Logging

Cachetta provides detailed logging for debugging. You can configure the log level:

```javascript
import { setLogLevel } from 'cachetta';

// Enable debug logging
setLogLevel('debug');

// Available levels: 'error', 'warn', 'info', 'debug'
// Default is 'warn'
```

Cachetta uses a simple logger that outputs to `console` by default, but you can also configure it to use your preferred logging library:

```javascript
import { setLogger } from 'cachetta';

// Use a custom logger (e.g., winston, pino)
setLogger({
  debug: (msg) => console.debug(`[Cachetta] ${msg}`),
  info: (msg) => console.info(`[Cachetta] ${msg}`),
  warn: (msg) => console.warn(`[Cachetta] ${msg}`),
  error: (msg) => console.error(`[Cachetta] ${msg}`),
});
```

### TypeScript Support

Cachetta includes full TypeScript support:

```typescript
import { Cachetta } from 'cachetta';

interface UserData {
  id: number;
  name: string;
  email: string;
}

const cache = new Cachetta<UserData>({
  path: './user-cache.json',
});

@cache
async function fetchUserData(id: number): Promise<UserData> {
  // API call implementation
  return { id, name: 'John Doe', email: 'john@example.com' };
}
```

### Default Configuration

- **Default duration**: 7 days (7 * 24 * 60 * 60 * 1000 milliseconds)
- **Default read**: `true`
- **Default write**: `true`
- **Supported format**: JSON only
