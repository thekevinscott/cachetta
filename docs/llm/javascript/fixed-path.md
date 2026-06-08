---
nav_exclude: true
search_exclude: true
---

# Fixed path — JavaScript / TypeScript

## When to use

When a function always returns the same thing (or you just want one named cache
file): a string `path` is used **verbatim**, so every call reads and writes the
same file regardless of arguments.

## Project setup

```typescript
// config.ts — one cache for the whole project
import { homedir } from 'os';
import { join } from 'path';
import { Cachetta } from 'cachetta';

export const CACHE_ROOT = join(homedir(), '.cache', 'my-awesome-library');
export const cache = new Cachetta({ path: CACHE_ROOT });
```

Each module derives a scoped sub-cache with
`cache.copy({ path: join(CACHE_ROOT, 'name') })`.

## Example

```typescript
// models.ts
import { join } from 'path';
import { cache, CACHE_ROOT } from './config';

const modelsCache = cache.copy({ path: join(CACHE_ROOT, 'openai-models') });
const listModels = modelsCache(async () => client.models.list());

await listModels(); // fetches once, then served from disk
await listModels(); // disk hit
```

**On disk:** a single file at `~/.cache/my-awesome-library/openai-models`. The
name is cosmetic — contents are binary (`v8.serialize`), so any extension (or
none) works.

**Gotcha:** arguments are ignored for path resolution, so `f(1)` and `f(2)`
collide in the same file. If the result depends on the arguments, use
[hashed by args](./hashed.md) or a [custom path lambda](./custom-path-lambda.md).

→ Full API: [TypeScript reference](../../javascript.md) · Back to
[JavaScript recipes](./index.md)
