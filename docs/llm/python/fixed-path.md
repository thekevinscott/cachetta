---
nav_exclude: true
search_exclude: true
---

# Fixed path — Python

## When to use

When a function always returns the same thing (or you just want one named cache
file): a sub-cache from a plain `cache / 'name'` is used **verbatim**, so every
call reads and writes the same file regardless of arguments.

## Project setup

```python
# config.py — one cache for the whole project
from pathlib import Path
from cachetta import Cachetta

cache = Cachetta(path=Path.home() / '.cache' / 'my-awesome-library')
```

Each module derives a scoped sub-cache from this singleton with `cache / 'name'`.

## Example

```python
# models.py
from config import cache

models_cache = cache / 'openai-models'

@models_cache
def list_models():
    return client.models.list()   # same for everyone, changes rarely

list_models()   # fetches once, then served from disk
list_models()   # disk hit
```

**On disk:** a single file at `~/.cache/my-awesome-library/openai-models`. The
extension is cosmetic — contents are binary `pickle`, so any name works.

**Gotcha:** arguments are ignored for path resolution, so `f(1)` and `f(2)`
collide in the same file. If the result depends on the arguments, use
[hashed by args](./hashed.md) or a [custom path lambda](./custom-path-lambda.md).

→ Full API: [Python reference](../../python.md) · Back to
[Python recipes](./index.md)
