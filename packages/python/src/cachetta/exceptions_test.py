"""Unit tests for cachetta.exceptions."""

import pytest

from cachetta.exceptions import (
    CacheCorruptError,
    CachettaError,
)


def describe_exceptions():
    def test_cachetta_error_is_an_exception():
        assert issubclass(CachettaError, Exception)

    def test_cache_corrupt_error_subclasses_cachetta_error():
        assert issubclass(CacheCorruptError, CachettaError)

    def test_subclasses_are_catchable_as_the_base_error():
        with pytest.raises(CachettaError):
            raise CacheCorruptError("corrupt")
