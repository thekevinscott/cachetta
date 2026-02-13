# Cachetta

File-based JSON caching with the same API across JavaScript/TypeScript and Python. The name is a portmanteau of *cache* and *rosetta*.

Both implementations share identical concepts -- configuration, decorators, read/write primitives, LRU, stale-while-revalidate -- differing only where language conventions require it (e.g. `snake_case` vs `camelCase`, `timedelta` vs milliseconds).

## Packages

- [JavaScript/TypeScript](packages/javascript/) -- `pnpm add cachetta`
- [Python](packages/python/) -- `uv add cachetta`

## Feature Parity

| Feature | JavaScript/TypeScript | Python |
|---|---|---|
| File-based JSON cache | Yes | Yes |
| Decorator / function wrapper | Yes | Yes |
| Async support | Always async | Sync + async variants |
| In-memory LRU layer | Yes | Yes (thread-safe) |
| Stale-while-revalidate | Yes | Yes |
| Conditional caching | Yes | Yes |
| Auto cache keys (arg hashing) | Yes | Yes |
| Dynamic path functions | Yes | Yes |
| Cache inspection (exists/age/info) | Yes | Yes (sync + async) |
| Cache invalidation | Yes | Yes (sync + async) |
| Atomic writes | Yes | Yes |
| Path traversal protection | Yes | Yes |
| Prototype pollution protection | Yes | N/A |
| `/` path operator | -- | Yes |
| `skip_self` for method decorators | -- | Yes |

See each package's README for installation, usage, and API details.
