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
