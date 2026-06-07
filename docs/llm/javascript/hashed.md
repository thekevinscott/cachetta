---
nav_exclude: true
search_exclude: true
---

# Hashed by args — JavaScript / TypeScript

## When to use

When the output depends on the arguments and you want one cache file per
argument set inside a folder (the common LLM / embedding shape). Add
`hashed: true` to a sub-cache: its path becomes a directory and each entry is
written as `{path}/{hash(...args)}`.

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
// llm.ts
import { join } from 'path';
import { cache, CACHE_ROOT } from './config';

const llmCache = cache.copy({ path: join(CACHE_ROOT, 'llm'), hashed: true });
const callLLM = llmCache(async (prompt: string) =>
  client.responses.create({ model: 'gpt-5', input: prompt }));

await callLLM('hello'); // ~/.cache/my-awesome-library/llm/<hash('hello')>
await callLLM('world'); // ~/.cache/my-awesome-library/llm/<hash('world')>
await callLLM('hello'); // disk hit on the first file
```

**On disk:** one file per distinct arg-set under the folder, e.g.
`~/.cache/my-awesome-library/llm/9f86d081544320cb`. The filename is exactly the
16-char digest from the public [`hash`](../../javascript.md#public-hash-helper)
helper — bare, no extension by default.

**Gotcha — `this`:** when you decorate a class method, the instance (`this`) is
**never** part of the key — only the method's arguments are hashed, so two
instances share the same cache files automatically. (Python behaves the same
way — the receiver is auto-excluded there too.)

`hashed` also composes with `condition` and the LRU.

→ Full API: [TypeScript reference](../../javascript.md) · Back to
[JavaScript recipes](./index.md)
