# Migrations

Upgrade guides for breaking changes to the `cachetta` PyPI package. Each entry
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
| `old_api(...)` | `new_api(...)` |

### Deprecations removed
- Removed `old_option` (deprecated since vX.Y).

### Behavior changes without code changes
- `cache.get()` now raises `KeyError` instead of returning `None` on miss.

### Verification
- Run `uv run cachetta --dry-run` and confirm output matches the expected
  snippet below.
-->

## v0.6 → v0.7

### Summary
The implicit "sibling-hash" behavior has been removed. When `path` was a
`str` or `Path`, cachetta used to silently rewrite the filename into a
`{stem}-{hash}{ext}` sibling whenever the wrapped function received
arguments. That default collided across functions that happened to share
a stem in the same folder, left a dead stem prefix on every file name,
and gave callers no clean way to organize multiple cache kinds under one
root. `path=str|Path` now means exactly that: cachetta writes to the
literal path you gave it, regardless of arguments.

### Required changes
| Before | After |
|--------|-------|
| `@Cachetta(path="cache/llm.pkl")`<br>`def call(prompt): ...`<br>_wrote to `cache/llm-<hash>.pkl`_ | `@Cachetta(path=lambda prompt: f"cache/llm/{prompt}.pkl")`<br>`def call(prompt): ...`<br>_explicit per-arg path callable_ |
| `cache = Cachetta(path="cache.json")`<br>`cache.invalidate("a")`<br>_removed `cache-<hash>.json`_ | `cache = Cachetta(path=lambda x: f"cache/{x}.json")`<br>`cache.invalidate("a")`<br>_removes the path you actually wrote_ |

If a single literal file is what you actually want, no change is needed —
that's the new default.

### Deprecations removed
- The implicit `{stem}-{hash}{ext}` sibling rewrite in
  `Cachetta._get_path` when `path` is a `str` or `Path`.

### Behavior changes without code changes
- `Cachetta(path="cache.json")` decorating a function with arguments now
  writes every call to `cache.json` (last write wins) instead of fanning
  out into per-args sibling files. Existing on-disk `cache-<hash>.json`
  files written by older versions are no longer read; delete or migrate
  them by hand if you need their contents.

### Verification
- After upgrading, run:
  ```python
  from cachetta import Cachetta
  cache = Cachetta(path="/tmp/cachetta_check.pkl")
  assert str(cache._get_path("anything")) == "/tmp/cachetta_check.pkl"
  ```
  The assertion should succeed; pre-upgrade it produced a path of the
  form `/tmp/cachetta_check-<hash>.pkl`.
