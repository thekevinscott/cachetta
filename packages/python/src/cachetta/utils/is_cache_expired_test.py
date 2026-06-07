import pytest
from datetime import timedelta
from cachetta.utils.is_cache_expired import is_cache_expired
from cachetta.exceptions import CachettaError

def describe_is_cache_expired():
    def test_it_raises_if_cache_time_is_ahead_of_now():
        with pytest.raises(CachettaError):
            is_cache_expired(2, 1, timedelta(seconds=1))

    def test_it_returns_true_if_cache_is_expired():
        assert is_cache_expired(
            cache_time=1,
            now=3, 
            duration=timedelta(seconds=1)
        ) is True

    def test_it_returns_false_if_cache_is_not_expired():
        assert is_cache_expired(
            cache_time=1, 
            now=1, 
            duration=timedelta(seconds=2)
        ) is False

    def test_it_returns_true_if_cache_is_identical_to_now():
        assert is_cache_expired(
            cache_time=1,
            now=3, 
            duration=timedelta(seconds=2)
        ) is True

    def test_it_returns_false_for_non_expired_cache():
        import time
        now = time.time()
        cache_time = now - 1800  # 30 minutes ago
        cache_length = timedelta(hours=1)  # 1 hour cache

        assert is_cache_expired(cache_time, now, cache_length) is False

    def test_it_returns_true_for_expired_cache():
        import time
        now = time.time()
        cache_time = now - 7200  # 2 hours ago
        cache_length = timedelta(hours=1)  # 1 hour cache

        assert is_cache_expired(cache_time, now, cache_length) is True

    def test_it_returns_true_for_exactly_expired_cache():
        import time
        now = time.time()
        cache_time = now - 3600  # Exactly 1 hour ago
        cache_length = timedelta(hours=1)  # 1 hour cache

        assert is_cache_expired(cache_time, now, cache_length) is True

    def test_it_returns_false_for_cache_that_just_expired():
        import time
        now = time.time()
        cache_time = now - 3540  # 59 minutes ago
        cache_length = timedelta(hours=1)  # 1 hour cache

        assert is_cache_expired(cache_time, now, cache_length) is False

    def test_it_handles_very_short_cache_lengths():
        import time
        now = time.time()
        cache_time = now - 1  # 1 second ago
        cache_length = timedelta(milliseconds=500)  # 0.5 seconds cache

        assert is_cache_expired(cache_time, now, cache_length) is True

    def test_it_handles_very_long_cache_lengths():
        import time
        now = time.time()
        cache_time = now - (30 * 24 * 3600)  # 30 days ago
        cache_length = timedelta(days=365)  # 1 year cache

        assert is_cache_expired(cache_time, now, cache_length) is False

    def test_it_handles_zero_cache_length():
        import time
        now = time.time()
        cache_time = now - 1  # 1 second ago
        cache_length = timedelta(seconds=0)  # No cache

        assert is_cache_expired(cache_time, now, cache_length) is True

    def test_it_handles_negative_cache_length():
        import time
        now = time.time()
        cache_time = now - 1  # 1 second ago
        cache_length = timedelta(seconds=-1)  # Negative cache

        assert is_cache_expired(cache_time, now, cache_length) is True

    def test_it_handles_current_time_cache():
        import time
        now = time.time()
        cache_time = now  # Current time
        cache_length = timedelta(hours=1)  # 1 hour cache

        assert is_cache_expired(cache_time, now, cache_length) is False

    def test_it_handles_very_old_cache():
        import time
        now = time.time()
        cache_time = now - (1000 * 24 * 3600)  # 1000 days ago
        cache_length = timedelta(days=1)  # 1 day cache

        assert is_cache_expired(cache_time, now, cache_length) is True
