import asyncio
import json
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from time import time
from unittest.mock import patch, Mock, MagicMock
from cachetta._sentinel import _LRU_MISS

import pytest

from cachetta.cachetta import Cachetta
from cachetta.read_cache import read_cache
from cachetta.write_cache import write_cache, _created_dirs
from cachetta.utils.cache_fn import _in_flight


@pytest.fixture(autouse=True)
def clear_created_dirs():
    """Clear the directory cache between tests."""
    _created_dirs.clear()
    yield
    _created_dirs.clear()


@pytest.fixture(autouse=True)
def clear_in_flight():
    """Clear in-flight tasks between tests."""
    _in_flight.clear()
    yield
    _in_flight.clear()


def describe_lru_cache():
    def test_lru_size_creates_lru_dict():
        cache = Cachetta(path="test.json", lru_size=10)
        assert cache._lru is not None
        assert len(cache._lru) == 0

    def test_no_lru_size_leaves_lru_none():
        cache = Cachetta(path="test.json")
        assert cache._lru is None

    def test_lru_get_returns_miss_when_disabled():
        cache = Cachetta(path="test.json")
        assert cache._lru_get("key") is _LRU_MISS

    def test_lru_set_is_noop_when_disabled():
        cache = Cachetta(path="test.json")
        cache._lru_set("key", "value")
        assert cache._lru is None

    def test_lru_set_and_get():
        cache = Cachetta(path="test.json", lru_size=10)
        cache._lru_set("key1", {"data": "hello"})
        result = cache._lru_get("key1")
        assert result == {"data": "hello"}

    def test_lru_evicts_oldest_when_full():
        cache = Cachetta(path="test.json", lru_size=2)
        cache._lru_set("key1", "value1")
        cache._lru_set("key2", "value2")
        cache._lru_set("key3", "value3")

        assert cache._lru_get("key1") is _LRU_MISS
        assert cache._lru_get("key2") == "value2"
        assert cache._lru_get("key3") == "value3"

    def test_lru_moves_accessed_to_end():
        cache = Cachetta(path="test.json", lru_size=2)
        cache._lru_set("key1", "value1")
        cache._lru_set("key2", "value2")

        # Access key1 to move it to end
        cache._lru_get("key1")

        # Add key3, which should evict key2 (oldest), not key1
        cache._lru_set("key3", "value3")

        assert cache._lru_get("key1") == "value1"
        assert cache._lru_get("key2") is _LRU_MISS
        assert cache._lru_get("key3") == "value3"

    def test_lru_expires_entries():
        cache = Cachetta(path="test.json", lru_size=10, duration=timedelta(seconds=0))
        cache._lru_set("key1", "value1")
        # Duration is 0, so entry should be expired immediately
        assert cache._lru_get("key1") is _LRU_MISS

    def test_lru_does_not_evict_when_updating_existing_key():
        cache = Cachetta(path="test.json", lru_size=2)
        cache._lru_set("key1", "value1")
        cache._lru_set("key2", "value2")
        # Update existing key1, should not evict
        cache._lru_set("key1", "value1-updated")

        assert cache._lru_get("key1") == "value1-updated"
        assert cache._lru_get("key2") == "value2"


def describe_lru_integration_with_read_cache():
    def test_read_cache_returns_lru_hit(self=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            # Pre-populate LRU
            cache._lru_set(str(cache_path), {"from": "lru"})

            with read_cache(cache) as data:
                pass
            assert data == {"from": "lru"}

    def test_read_cache_populates_lru_from_disk():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            with open(cache_path, "w") as f:
                json.dump({"from": "disk"}, f)

            cache = Cachetta(path=str(cache_path), lru_size=10)

            # First read should come from disk and populate LRU
            with read_cache(cache) as data:
                pass
            assert data == {"from": "disk"}

            # Verify LRU is now populated
            assert cache._lru_get(str(cache_path)) == {"from": "disk"}


def describe_lru_integration_with_write_cache():
    def test_write_cache_populates_lru():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            write_cache(cache, {"written": True})

            assert cache._lru_get(str(cache_path)) == {"written": True}

    def test_write_cache_does_not_populate_lru_when_disabled():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"written": True})

            assert cache._lru is None


def describe_directory_caching():
    def test_write_cache_caches_directories():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "sub" / "test.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"data": 1})

            parent = str(cache_path.parent.resolve())
            assert parent in _created_dirs

    def test_write_cache_skips_mkdir_for_cached_dir():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path))

            with patch("cachetta.write_cache.Path.mkdir") as mock_mkdir:
                # Write twice to same directory
                write_cache(cache, {"data": 1})
                write_cache(cache, {"data": 2})

                # mkdir should only be called once
                assert mock_mkdir.call_count == 1


def describe_eafp_get_last_updated():
    def test_returns_none_for_missing_file():
        from cachetta.utils.get_last_updated import get_last_updated
        assert get_last_updated("/nonexistent/path/file.json") is None

    def test_returns_timestamp_for_existing_file():
        from cachetta.utils.get_last_updated import get_last_updated
        with tempfile.NamedTemporaryFile() as f:
            ts = get_last_updated(f.name)
            assert isinstance(ts, float)
            assert ts > 0

    def test_does_not_call_exists(self=None):
        """EAFP pattern means we should not call os.path.exists."""
        from cachetta.utils.get_last_updated import get_last_updated
        with patch("cachetta.utils.get_last_updated.os.path.exists") as mock_exists:
            get_last_updated("/nonexistent/file.json")
            mock_exists.assert_not_called()


def describe_streaming_json():
    def test_uses_json_load_not_json_loads():
        """read_cache should use json.load(f) for streaming rather than f.read() + json.loads()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            with open(cache_path, "w") as f:
                json.dump({"streaming": True}, f)

            cache = Cachetta(path=str(cache_path))

            with patch("cachetta.read_cache.json.load", return_value={"streaming": True}) as mock_load:
                with read_cache(cache) as data:
                    pass
                mock_load.assert_called_once()

    def test_handles_corrupt_json_gracefully():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "corrupt.json"
            with open(cache_path, "w") as f:
                f.write("not valid json{{{")

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as data:
                pass
            assert data is None

    def test_handles_missing_file_gracefully():
        cache = Cachetta(path="/nonexistent/missing.json")
        with read_cache(cache) as data:
            pass
        assert data is None


def describe_call_deduplication():
    @pytest.fixture(autouse=True)
    def _no_mocks(self=None):
        """These tests use real read/write to test async dedup."""
        pass

    async def test_deduplicates_concurrent_async_calls():
        call_count = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "dedup.json"

            cache = Cachetta(path=str(cache_path), read=False)

            @cache
            async def slow_fn():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.05)
                return {"result": call_count}

            # Launch 3 concurrent calls
            results = await asyncio.gather(slow_fn(), slow_fn(), slow_fn())

            # The function should have only been called once
            assert call_count == 1
            # All results should be the same
            assert all(r == {"result": 1} for r in results)

    async def test_dedup_cleans_up_after_completion():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "dedup2.json"
            cache = Cachetta(path=str(cache_path), read=False)

            @cache
            async def my_fn():
                return {"data": True}

            await my_fn()
            # After completion, no in-flight entries should remain
            assert str(cache_path) not in _in_flight

    async def test_dedup_propagates_errors():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "dedup-err.json"
            cache = Cachetta(path=str(cache_path), read=False)

            @cache
            async def failing_fn():
                raise ValueError("test error")

            with pytest.raises(ValueError, match="test error"):
                await failing_fn()

            # Should be cleaned up after error too
            assert str(cache_path) not in _in_flight
