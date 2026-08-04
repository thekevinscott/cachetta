import os
from pathlib import Path
from typing import Callable


def clear_path(target: Path, should_clear: Callable[[float], bool]) -> list[Path]:
    """Deletes files under ``target`` for which ``should_clear(mtime)``
    returns True.

    A directory is walked recursively (directories themselves are kept); a
    file is checked in place; a missing path is a no-op. Returns the
    deleted file paths.
    """
    if target.is_dir():
        deleted: list[Path] = []
        for child in sorted(target.iterdir()):
            deleted.extend(clear_path(child, should_clear))
        return deleted
    try:
        mtime = os.path.getmtime(target)
    except OSError:
        # Missing path (or a file that vanished mid-walk): nothing to do.
        return []
    if not should_clear(mtime):
        return []
    try:
        os.unlink(target)
    except FileNotFoundError:
        # The file vanished between stat and unlink; it was not deleted by us.
        return []
    return [target]
