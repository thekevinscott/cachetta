---
nav_exclude: true
search_exclude: true
---

# Custom path lambda — Python

## When to use

When only some arguments should form the cache key. Give `/` a callable that
receives the wrapped function's arguments and returns the sub-path; call the
public [`hash`](../../python.md#public-hash-helper) helper for the parts you want
keyed the way cachetta keys them.

## Project setup

```python
# config.py — one cache for the whole project
from pathlib import Path
from cachetta import Cachetta

cache = Cachetta(path=Path.home() / '.cache' / 'my-awesome-library')
```

Each module derives a scoped sub-cache from this singleton; here the sub-path is
computed from a *subset* of the call arguments.

## Example

```python
# llm.py
from config import cache
from cachetta import hash

llm_cache = cache / (lambda model, prompt, **kwargs: f'{model}/{hash(prompt)}.pkl')

@llm_cache
def call_llm(model, prompt, *, temperature=0.7):
    return client.responses.create(model=model, input=prompt,
                                   temperature=temperature)

call_llm('gpt-5', 'hi')                    # .../gpt-5/<hash('hi')>.pkl
call_llm('gpt-5', 'hi', temperature=0.9)   # same file — temperature is ignored
call_llm('claude', 'hi')                   # .../claude/<hash('hi')>.pkl
```

`model` shards into folders, `prompt` is hashed into the filename, and
`temperature` (like clients, loggers, or other knobs) is left out of the key.

**On disk:** `~/.cache/my-awesome-library/{model}/{hash(prompt)}.pkl`. The
callable's return is validated against `..` traversal — paths that escape the
base raise `InvalidPathError`.

**Gotchas:**
- The callable must be **deterministic** across runs — keying on a timestamp or
  a random value means you never get a hit.
- On an instance method the receiver (`self`) is auto-excluded, so the callable
  receives only the real call arguments — write its signature without `self`.

For the simpler "hash *all* the args under one folder" case, prefer
[hashed by args](./hashed.md).

→ Full API: [Python reference](../../python.md) · Back to
[Python recipes](./index.md)
