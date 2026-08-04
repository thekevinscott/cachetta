import os
from pathlib import Path
from typing import Callable


def clear_path(target: Path, should_clear: Callable[[float], bool]) -> None:
    """Deletes files under ``target`` for which ``should_clear(mtime)``
    returns True.

    A directory is walked recursively (directories themselves are kept); a
    file is checked in place; a missing path is a no-op.
    """
    if target.is_dir():
        for child in target.iterdir():
            clear_path(child, should_clear)
        return
    try:
        mtime = os.path.getmtime(target)
    except OSError:
        # Missing path (or a file that vanished mid-walk): nothing to do.
        return
    if not should_clear(mtime):
        return
    try:
        os.unlink(target)
    except FileNotFoundError:
        # The file vanished between stat and unlink; nothing left to do.
        pass
