"""Unit tests for cachetta._sentinel."""

from cachetta._sentinel import _LRU_MISS


def describe_sentinel():
    def test_lru_miss_has_stable_identity():
        assert _LRU_MISS is _LRU_MISS

    def test_lru_miss_is_distinct_from_none():
        # The sentinel must be distinguishable from a cached ``None`` value,
        # which is exactly why a plain ``object()`` is used.
        assert _LRU_MISS is not None
