# Migrations

Upgrade guides for breaking changes to the `cachetta` npm package. Each entry
is required to include all five sections below. Write "None." if a section
truly has no content, so reviewers know it was considered.

<!--
Template — copy for each version bump:

## vX.Y → vA.B

### Summary
One paragraph: what broke and why.

### Required changes
| Before | After |
|--------|-------|
| `oldApi(...)` | `newApi(...)` |

### Deprecations removed
- Removed `oldOption` (deprecated since vX.Y).

### Behavior changes without code changes
- `cache.get()` now returns `undefined` instead of `null` on miss.

### Verification
- Run `pnpm cachetta --dry-run` and confirm output matches the expected
  snippet below.
-->

## v0.4 → v0.5

### Summary
The in-memory LRU layer has been removed, along with the `lruSize` config
option. It arrived in the initial code import with no design rationale,
the library's sole consumer never enabled it, and issues #79/#82/#83
tracked broken eviction and expiry behavior. Rather than fix a feature
nobody uses, it's gone. `Cachetta` now has no in-memory cache; every read
(`readCache`/`readCacheSync`, and reads inside wrapped functions) hits
disk directly. Write paths no longer populate any in-process cache.

### Required changes
| Before | After |
|--------|-------|
| `new Cachetta({ path: 'cache.json', lruSize: 100 })` | `new Cachetta({ path: 'cache.json' })` |
| `cache.copy({ lruSize: 50 })` | `cache.copy({})` |

If you relied on the LRU purely as a performance optimization to avoid
disk reads, and you need that back, add your own memoization layer in
front of the wrapped function — cachetta no longer provides one.

### Deprecations removed
None. `lruSize` was not deprecated before this removal.

### Behavior changes without code changes
- Every cache read now touches disk, even for repeated reads of the same
  key in quick succession. If `lruSize` was previously set, expect more
  filesystem I/O and slightly higher read latency; disk-level caching
  (OS page cache) still applies.
- `lruSize` in a config object passed to `new Cachetta(...)` or
  `cache.copy(...)` is now silently ignored at runtime (TypeScript
  rejects it at compile time via the `CacheConfig` type).

### Verification
- After upgrading, run:
  ```ts
  import { Cachetta } from 'cachetta';
  const cache = new Cachetta({ path: '/tmp/cachetta_lru_check.json' });
  console.assert(!('_lru' in cache), 'expected no in-memory LRU state');
  console.assert(!('lruSize' in cache), 'expected no lruSize property');
  ```
  Both assertions should hold. Pre-upgrade, `cache._lru` and
  `cache.lruSize` were defined properties on every instance.

## v0.3 → v0.4

### Summary
The implicit "sibling-hash" behavior has been removed. When `path` was a
string, cachetta used to silently rewrite the filename into a
`{name}-{hash}{ext}` sibling whenever the wrapped function received
arguments. That default collided across functions that happened to share
a base name in the same folder, left a dead name prefix on every file,
and gave callers no clean way to organize multiple cache kinds under one
root. A string `path` now means exactly that: cachetta writes to the
literal path you gave it, regardless of arguments.

### Required changes
| Before | After |
|--------|-------|
| `new Cachetta({ path: 'cache/llm.json' })`<br>_wrapped `fn(prompt)` → `cache/llm-<hash>.json`_ | `new Cachetta({ path: (prompt) => `cache/llm/${prompt}.json` })`<br>_explicit per-arg path function_ |
| `const cache = new Cachetta({ path: 'cache.json' })`<br>`await cache.invalidate('a')`<br>_removed `cache-<hash>.json`_ | `const cache = new Cachetta({ path: (x) => `cache/${x}.json` })`<br>`await cache.invalidate('a')`<br>_removes the path you actually wrote_ |

If a single literal file is what you actually want, no change is needed —
that's the new default.

### Deprecations removed
- The implicit `{name}-{hash}{ext}` sibling rewrite in `Cachetta._getPath`
  when `path` is a string.

### Behavior changes without code changes
- `new Cachetta({ path: 'cache.json' })` wrapping a function with
  arguments now writes every call to `cache.json` (last write wins)
  instead of fanning out into per-args sibling files. Existing on-disk
  `cache-<hash>.json` files written by older versions are no longer
  read; delete or migrate them by hand if you need their contents.

### Verification
- After upgrading, run:
  ```ts
  import { Cachetta } from 'cachetta';
  const cache = new Cachetta({ path: '/tmp/cachetta_check.json' });
  console.assert(cache._getPath('anything') === '/tmp/cachetta_check.json');
  ```
  The assertion should hold; pre-upgrade it produced a path of the form
  `/tmp/cachetta_check-<hash>.json`.
