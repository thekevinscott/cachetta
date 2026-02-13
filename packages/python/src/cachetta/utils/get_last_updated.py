import asyncio
import os
from pathlib import Path


def get_last_updated(file_path: str | Path) -> float | None:
    try:
        return os.path.getmtime(file_path)
    except OSError:
        return None


async def async_get_last_updated(file_path: str | Path) -> float | None:
    """Async version of get_last_updated. Delegates to a thread."""
    return await asyncio.to_thread(get_last_updated, file_path)
