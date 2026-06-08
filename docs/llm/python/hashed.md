---
nav_exclude: true
search_exclude: true
---

# Hashed by args — Python

## When to use

When the output depends on the arguments and you want one cache file per
argument set inside a folder (the common LLM / embedding shape). Add
`hashed=True` to a sub-cache: its path becomes a directory and each entry is
written as `{path}/{hash(*args, **kwargs)}`.

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
# llm.py
from config import cache

llm_cache = cache / 'llm'

@llm_cache(hashed=True)
def call_llm(prompt: str):
    return client.responses.create(model='gpt-5', input=prompt)

call_llm('hello')   # ~/.cache/my-awesome-library/llm/<hash('hello')>
call_llm('world')   # ~/.cache/my-awesome-library/llm/<hash('world')>
call_llm('hello')   # disk hit on the first file
```

**On disk:** one file per distinct arg-set under the folder, e.g.
`~/.cache/my-awesome-library/llm/9f86d081544320cb`. The filename is exactly the
16-char digest from the public [`hash`](../../python.md#public-hash-helper)
helper — no extension by default.

**Gotcha — methods:** decorating an instance method works as-is. The receiver
(`self`/`cls`) is automatically excluded from the hash, so every instance shares
the same cache files, keyed only by the real arguments.

`hashed` also composes with `condition`, `stale_duration`, async functions, and
the LRU.

→ Full API: [Python reference](../../python.md) · Back to
[Python recipes](./index.md)
