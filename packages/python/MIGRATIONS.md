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

_No migrations yet._
