---
nav_exclude: true
search_exclude: true
---

# cachetta recipes — Python

## Project setup

Keep one cache for the whole project in a central module, then derive a scoped
sub-cache per function with the `/` operator:

```python
# config.py
from pathlib import Path
from cachetta import Cachetta

cache = Cachetta(path=Path.home() / '.cache' / 'my-awesome-library')
```

```python
# any module that needs caching
from config import cache

function_cache = cache / 'my-function'   # ~/.cache/my-awesome-library/my-function
```

`cache / 'name'` returns a new `Cachetta` scoped to that sub-path, inheriting
`duration` and the rest of the root config. Every recipe below builds on a
`function_cache` handle like this.

## Pick a recipe

- **[Fixed path](./fixed-path.md)** — cache one function under one file. Use
  when the function always returns the same thing or you want a single, named
  cache file.
- **[Hashed by args](./hashed.md)** — one cache file per argument set, inside a
  folder. Use when the function's output depends on its arguments.
- **[Custom path lambda](./custom-path-lambda.md)** — build the cache path from
  a *subset* of the arguments. Use when some args (clients, loggers, knobs like
  `temperature`) shouldn't participate in the cache key.

Full API (stale-while-revalidate, invalidation, inspection, pickle
security): [Python reference](../../python.md).
