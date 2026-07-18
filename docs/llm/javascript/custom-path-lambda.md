---
nav_exclude: true
search_exclude: true
---

# Custom path lambda — JavaScript / TypeScript

## When to use

When only some arguments should form the cache key. Pass `path` as a function
that receives the wrapped function's arguments and returns the path; call the
public [`hash`](../../javascript.md#public-hash-helper) helper for the parts you
want keyed the way cachetta keys them.

## Project setup

```typescript
// config.ts — one cache for the whole project
import { homedir } from 'os';
import { join } from 'path';
import { Cachetta } from 'cachetta';

export const CACHE_ROOT = join(homedir(), '.cache', 'my-awesome-library');
export const cache = new Cachetta({ path: CACHE_ROOT });
```

Each module derives a scoped sub-cache from this singleton; here the path is
computed from a *subset* of the call arguments.

## Example

```typescript
// llm.ts
import { join } from 'path';
import { cache, CACHE_ROOT } from './config';
import { hash } from 'cachetta';

const llmCache = cache.copy({
  path: (model: string, prompt: string, _opts) => join(CACHE_ROOT, model, hash(prompt)),
});
const callLLM = llmCache(async (model: string, prompt: string, opts = {}) =>
  client.responses.create({ model, input: prompt, ...opts }));

await callLLM('gpt-5', 'hi');                       // .../gpt-5/<hash('hi')>
await callLLM('gpt-5', 'hi', { temperature: 0.9 }); // same file — opts ignored
await callLLM('claude', 'hi');                      // .../claude/<hash('hi')>
```

`model` shards into folders, `prompt` is hashed into the filename, and `opts`
(like clients, loggers, or other knobs) is left out of the key.

**On disk:** `~/.cache/my-awesome-library/{model}/{hash(prompt)}`. The returned
path is used as given — cachetta trusts it, so never build it from untrusted
input (see [Path Contract](../../javascript.md#path-contract)).

**Gotchas:**
- The function must be **deterministic** across runs — keying on `Date.now()` or
  a random value means you never get a hit.
- On a class method the instance (`this`) is not passed to the path function —
  only the call arguments are — so no special handling is needed.

For the simpler "hash *all* the args under one folder" case, prefer
[hashed by args](./hashed.md).

→ Full API: [TypeScript reference](../../javascript.md) · Back to
[JavaScript recipes](./index.md)
