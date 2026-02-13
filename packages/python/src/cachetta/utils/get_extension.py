from pathlib import Path

from ..exceptions import InvalidPathError


def get_extension(cache_path: str | Path) -> str:
    cache_path = str(cache_path)
    parts = cache_path.split('/').pop().split('.')
    if len(parts) == 1:
        raise InvalidPathError('Missing extension for path: %s' % cache_path)
    ext = parts[-1]
    return ext
