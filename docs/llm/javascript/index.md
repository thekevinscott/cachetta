---
nav_exclude: true
search_exclude: true
---

# cachetta recipes — JavaScript / TypeScript

## Project setup

Keep one cache for the whole project in a central module, then derive a scoped
sub-cache per function. JavaScript has no `/` operator, so join onto a shared
root with `cache.copy()`:

```typescript
// config.ts
import { homedir } from 'os';
import { join } from 'path';
import { Cachetta } from 'cachetta';

export const CACHE_ROOT = join(homedir(), '.cache', 'my-awesome-library');
export const cache = new Cachetta({ path: CACHE_ROOT });
```

```typescript
// any module that needs caching
import { join } from 'path';
import { cache, CACHE_ROOT } from './config';

const functionCache = cache.copy({ path: join(CACHE_ROOT, 'my-function') });
```

`cache.copy({ path })` returns a new cache scoped to that sub-path, inheriting
`duration` and the rest of the root config. Every recipe below builds on a
`functionCache` handle like this.

{: .note }
Decorated/wrapped functions always return a `Promise` — `await` them even when
the wrapped function is synchronous.

## Pick a recipe

- **[Fixed path](./fixed-path.md)** — cache one function under one file. Use
  when the function always returns the same thing or you want a single, named
  cache file.
- **[Hashed by args](./hashed.md)** — one cache file per argument set, inside a
  folder. Use when the function's output depends on its arguments.
- **[Custom path lambda](./custom-path-lambda.md)** — build the cache path from
  a *subset* of the arguments. Use when some args (clients, loggers, knobs like
  `temperature`) shouldn't participate in the cache key.

Full API (LRU, stale-while-revalidate, invalidation, inspection, sync
variants): [TypeScript reference](../../javascript.md).
