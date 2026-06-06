from datetime import timedelta
from unittest.mock import patch, Mock
import pytest
from cachetta.cachetta import Cachetta
from cachetta.utils.should_use_read_cache import should_use_read_cache


@pytest.fixture(autouse=True)
def mock_get_last_updated():
    with patch(
        "cachetta.utils.should_use_read_cache.get_last_updated", new_callable=Mock
    ) as mock:
        mock.return_value = 123
        yield mock


@pytest.fixture(autouse=True)
def mock_is_cache_expired():
    with patch(
        "cachetta.utils.should_use_read_cache.is_cache_expired", new_callable=Mock
    ) as mock:
        mock.return_value = False
        yield mock


class MockCache(Cachetta):
    pass


def describe_should_use_read_cache():
    def test_it_returns_false_when_cache_length_is_zero():
        cache = MockCache(path="foo", duration=timedelta(0))
        assert should_use_read_cache(cache, "foo") is False

    def test_it_returns_false_if_cache_time_is_none(mock_get_last_updated):
        mock_get_last_updated.return_value = None
        assert should_use_read_cache(MockCache(path="foo"), "foo") is False

    def test_it_returns_false_if_cache_is_expired(mock_is_cache_expired):
        mock_is_cache_expired.return_value = True
        assert should_use_read_cache(MockCache(path="foo"), "foo") is False

    @pytest.mark.parametrize(
        ("read"),
        [
            (True),
            (False),
        ],
    )
    def test_it_returns_cache_read_value_if_cache_exists_and_is_not_expired(read):
        assert should_use_read_cache(MockCache(path="foo", read=read), "foo") == read

    def test_it_returns_false_when_cache_read_is_false():
        cache = MockCache(path="foo", read=False)
        assert should_use_read_cache(cache, "foo") is False

    def test_it_returns_true_when_cache_read_is_true_and_not_expired():
        cache = MockCache(path="foo", read=True)
        assert should_use_read_cache(cache, "foo") is True



    def test_it_handles_different_cache_paths():
        cache = MockCache(path="foo", read=True)
        assert should_use_read_cache(cache, "foo") is True
        assert should_use_read_cache(cache, "bar") is True  # Same cache object, different path

    def test_it_handles_function_based_paths():
        def path_fn(id):
            return f"path/to/{id}.json"

        cache = MockCache(path=path_fn, read=True)
        assert should_use_read_cache(cache, "user-123") is True

    def test_it_handles_clock_skew_gracefully(mock_get_last_updated, mock_is_cache_expired):
        """When cache_time is in the future (clock skew), treat cache as valid."""
        import time
        mock_get_last_updated.return_value = time.time() + 3600  # 1 hour in the future
        cache = MockCache(path="foo", read=True)
        # Should NOT raise, and should return cache.read
        assert should_use_read_cache(cache, "foo") is True
        # is_cache_expired should NOT have been called (skipped due to clock skew)
        mock_is_cache_expired.assert_not_called()
