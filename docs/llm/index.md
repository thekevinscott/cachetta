---
nav_exclude: true
search_exclude: true
---

# cachetta for LLM agents

`cachetta` is a file-based cache with a decorator API — wrap a function and its
results are persisted to disk, with the same concepts in Python and TypeScript.
The pages below are concise, copy-pasteable recipes aimed at coding agents.

## The shape

Keep **one `cache` singleton** in a central config module (`config.py` /
`config.ts`), then derive a **scoped sub-cache per function** from it:

- Python: `function_cache = cache / 'my-function'`
- JavaScript: `const functionCache = cache.copy({ path: join(CACHE_ROOT, 'my-function') })`

Each language page repeats the full setup at the top.

## Pick your language

- **Python** → [./python/index.md](./python/index.md)
- **JavaScript / TypeScript** → [./javascript/index.md](./javascript/index.md)
