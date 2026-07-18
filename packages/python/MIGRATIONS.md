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

## v0.7 → v0.8

### Summary
The `skip_self` option has been removed. It existed so that decorating an
instance/class method wouldn't fold the receiver (`self`/`cls`) into the
cache key, but it worked by blindly stripping the first positional
argument whenever set — with no check that the call was actually a method,
so setting it on a plain function silently discarded a real argument.
Receiver exclusion is now automatic: the decorator detects method binding
via the descriptor protocol and strips the receiver from key/path
resolution while still passing it to the wrapped function. Plain functions
keep all of their positional arguments. Because detection is automatic and
correct, the flag is no longer needed and passing it raises `TypeError`.

In the same release, the in-memory LRU layer has been removed entirely.
It arrived in the initial code import with no design rationale, the
library's sole known consumer never used it, and issues #79/#82/#83
tracked broken behavior in it (stale entries surviving invalidation,
inconsistent eviction under concurrent access, and values served past
`duration` expiry). Rather than patch a layer nobody asked for, it's
removed outright — see tracking issue #98. Cachetta remains a disk-backed
cache; callers wanting an in-memory layer should add their own (e.g.
`functools.lru_cache` composed around the decorator, or a process-local
dict) since the right eviction/TTL semantics are application-specific.

Also in this release, `InvalidPathError` and the `..`-segment check in
`_get_path` have been removed (#85). The check raised `InvalidPathError`
claiming "path traversal detected," but it only ever matched a literal
`..` path segment — an absolute path or a symlink pointing outside the
intended directory passed through with no error at all. That gave a false
sense of protection without providing one. Cachetta's sole consumer
treats cache paths as developer-authored configuration, not attacker-
controlled input, so the maintainer decided to remove the check rather
than build it out into something that actually confines paths. `path`
(literal or callable) is now used exactly as given, with no validation.

### Required changes
| Before | After |
|--------|-------|
| `@Cachetta(path=fn, skip_self=True)`<br>`def method(self, x): ...` | `@Cachetta(path=fn)`<br>`def method(self, x): ...`<br>_receiver excluded automatically_ |
| `cache = Cachetta(path=..., skip_self=True)` | `cache = Cachetta(path=...)` |
| `cache.copy(skip_self=True)` | `cache.copy()` |
| `cache = Cachetta(path=..., lru_size=100)` | `cache = Cachetta(path=...)`<br>_no in-memory layer; every read hits disk_ |
| `from cachetta import InvalidPathError`<br>`try: cache._get_path()`<br>`except InvalidPathError: ...` | Remove the import and the `except` clause — the exception no longer exists and `_get_path` no longer raises for path shape. |

### Deprecations removed
- The `skip_self` field on `Cachetta` (and the `skip_self=` keyword to its
  constructor, `copy`, and per-decoration overrides). It was never
  deprecated with a warning; it is removed outright.
- The `lru_size` field on `Cachetta`, the internal `_lru`/`_lru_lock`
  state, and the `_lru_get`/`_lru_set` helpers. Also removed outright,
  with no deprecation warning period.
- The `InvalidPathError` exception class and its export from
  `cachetta.exceptions`/`cachetta.__init__`. Removed outright — it was
  never deprecated. Any `except InvalidPathError` clause is now dead code
  and will fail at import time.

### Behavior changes without code changes
- Decorating an instance/class method now excludes the receiver from the
  cache key by default. Code that previously relied on the *old default*
  (`skip_self=False`) to key on the receiver — e.g. a callable `path` or
  `hashed=True` whose key intentionally varied per instance — will now
  share cache entries across instances for equal arguments. This was
  almost never intentional (object identity is not stable across runs),
  but if you need per-instance partitioning, key on an explicit instance
  attribute via a callable `path`.
- Every cache read now goes to disk, even for calls that would previously
  have been served from the in-memory LRU. Throughput on tight read loops
  against the same key will drop to disk I/O speed; layer your own
  in-memory cache in front of `Cachetta` if that matters for your workload.
- `_get_path` no longer raises for a `path` (literal or callable-returned)
  containing `..` segments, an absolute path, or a symlink — it resolves
  and returns whatever `path` says, unchanged. Code that relied on the
  traversal check to reject bad configuration will now silently write to
  wherever the path points; validate `path` yourself before construction
  if that matters for your use case.

### Verification
- After upgrading, confirm the receiver no longer reaches a callable path:
  ```python
  from cachetta import Cachetta

  seen = []
  cache = Cachetta(path=lambda x: seen.append(x) or f"/tmp/{x}.dat")

  class Svc:
      @cache
      def get(self, x):
          return x

  Svc().get("a")
  assert seen == ["a"]  # the path callable saw "a", not (self, "a")
  ```
  Pre-upgrade (without `skip_self=True`) this raised `TypeError` because
  the lambda received `self` as an extra positional argument.
- Confirm `lru_size` is gone:
  ```python
  from cachetta import Cachetta
  try:
      Cachetta(path="/tmp/x.dat", lru_size=10)
      raise AssertionError("expected TypeError")
  except TypeError:
      pass  # expected: lru_size is no longer a valid keyword
  ```
- Confirm `InvalidPathError` is gone and traversal-shaped paths are used
  as given:
  ```python
  from pathlib import Path
  from cachetta import Cachetta

  cache = Cachetta(path="foo/../bar.dat")
  assert cache._get_path() == Path("foo/../bar.dat")  # no longer raises

  try:
      from cachetta import InvalidPathError
      raise AssertionError("expected ImportError")
  except ImportError:
      pass  # expected: InvalidPathError no longer exists
  ```

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
