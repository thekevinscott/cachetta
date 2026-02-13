from datetime import timedelta

from ..exceptions import CachettaError


def is_cache_expired(cache_time: float, now: float, duration: timedelta | int) -> bool:
    if cache_time > now:
        raise CachettaError(
            "Invalid arguments, cache time %s cannot be greater than now %s"
            % (cache_time, now)
        )
    if not isinstance(duration, timedelta):
        duration = timedelta(seconds=duration)
    return timedelta(seconds=now - cache_time) >= duration
