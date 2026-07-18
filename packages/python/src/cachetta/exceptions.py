class CachettaError(Exception):
    """Base exception for all Cachetta errors."""
    pass


class CacheCorruptError(CachettaError):
    """Raised when cached data is corrupt or unreadable."""
    pass
