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

## v0.5 → v0.6

### Summary
`clear` and `clearSync` are no longer plain aliases of
`invalidate`/`invalidateSync`. They are now an expiry-aware sweep of
whatever the instance's path resolves to: a folder is walked recursively
(directories are kept), a single file is checked in place, and a missing
path is a no-op. Without options, only entries that are no longer
servable are deleted — age ≥ `duration`, plus `staleDuration` when
configured, so entries inside the stale-while-revalidate window are
kept. A trailing `{ force: true }` options object deletes every entry
regardless of age. Both methods now return the deleted file paths
(`string[]`) instead of `void`. The change exists so hashed/foldered
caches can be cleaned of dead entries without knowing every arg-set ever
used (#110). `invalidate`/`invalidateSync` are unchanged.

### Required changes
| Before | After |
|--------|-------|
| `await cache.clear()` (expecting unconditional delete) | `await cache.clear({ force: true })` or `await cache.invalidate()` |
| `cache.clearSync()` (expecting unconditional delete) | `cache.clearSync({ force: true })` or `cache.invalidateSync()` |
| `await cache.clear('userId')` (delete one entry unconditionally) | `await cache.clear('userId', { force: true })` or `await cache.invalidate('userId')` |

### Deprecations removed
None.

### Behavior changes without code changes
- `clear()`/`clearSync()` without `force` now **keep** entries younger
  than `duration` + `staleDuration` instead of deleting the resolved
  file unconditionally.
- `clear()`/`clearSync()` on a folder now sweep the folder's files
  recursively; previously they attempted to `unlink` the folder itself
  and threw (`EISDIR`/`EPERM`).
- `clear()`/`clearSync()` now return the deleted file paths instead of
  `undefined`, and return `[]` (instead of silently succeeding) when the
  path does not exist.

### Verification
- `await cache.clear()` on a cache whose file was written moments ago
  must return `[]` and leave the file in place.
- `await cache.clear({ force: true })` on the same cache must return the
  file's path and delete it.

## v0.4 → v0.5

### Summary
The in-memory LRU layer has been removed, along with the `lruSize` config
option. It arrived in the initial code import with no design rationale,
the library's sole consumer never enabled it, and issues #79/#82/#83
tracked broken eviction and expiry behavior. Rather than fix a feature
nobody uses, it's gone. `Cachetta` now has no in-memory cache; every read
(`readCache`/`readCacheSync`, and reads inside wrapped functions) hits
disk directly. Write paths no longer populate any in-process cache.

Separately, `InvalidPathError` and the path-traversal check it guarded have
been removed (#86). The check only rejected literal `..` segments in a
resolved path — an absolute path (e.g. `/etc/passwd`) or a path through a
symlink passed through untouched — so it was cosmetic: it overstated the
guarantee ("path traversal detected") without closing the actual risk. The
maintainer, as sole consumer, has decided `path` (literal or `PathFn`) is
trusted developer input, not sanitized. Cachetta now resolves the path
and uses it as-is; it does not sandbox to a base directory, canonicalize
symlinks, or reject absolute/`..` paths. See "Path Contract" in
`docs/javascript.md`.

### Required changes
| Before | After |
|--------|-------|
| `new Cachetta({ path: 'cache.json', lruSize: 100 })` | `new Cachetta({ path: 'cache.json' })` |
| `cache.copy({ lruSize: 50 })` | `cache.copy({})` |
| `import { InvalidPathError } from 'cachetta'` | remove the import; the class no longer exists |
| `try { ... } catch (e) { if (e instanceof InvalidPathError) ... }` | remove the branch — no path-related error is thrown for absolute paths, `..` segments, or symlinks |

If you relied on the LRU purely as a performance optimization to avoid
disk reads, and you need that back, add your own memoization layer in
front of the wrapped function — cachetta no longer provides one.

If you relied on `InvalidPathError` as a security boundary against
untrusted path input, that boundary never existed in a form you could
depend on (absolute paths and symlinks always bypassed it). Do not pass
untrusted data into `path` or the arguments a `PathFn` receives — build
paths only from trusted, static, or internally-generated values.

### Deprecations removed
None. Neither `lruSize` nor the `..` path check were deprecated before
removal.

### Behavior changes without code changes
- Every cache read now touches disk, even for repeated reads of the same
  key in quick succession. If `lruSize` was previously set, expect more
  filesystem I/O and slightly higher read latency; disk-level caching
  (OS page cache) still applies.
- `lruSize` in a config object passed to `new Cachetta(...)` or
  `cache.copy(...)` is now silently ignored at runtime (TypeScript
  rejects it at compile time via the `CacheConfig` type).
- A `path` (literal or returned by a `PathFn`) containing a `..` segment,
  or an absolute path, no longer throws. It resolves and is used exactly
  as given — previously a literal `..` segment threw `InvalidPathError`;
  absolute paths and symlink-escaping paths already worked before this
  change and continue to work identically.

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
- Confirm `InvalidPathError` is gone and a `..`-containing path no longer
  throws:
  ```ts
  import { Cachetta, writeCache } from 'cachetta';
  import { join } from 'path';
  import { tmpdir } from 'os';

  const cache = new Cachetta({ path: join(tmpdir(), '..', 'cachetta_check.json'), write: true });
  await writeCache(cache, { ok: true }); // no longer throws
  ```

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
