import asyncio
import pickle
import tempfile
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

import pytest

from cachetta.cachetta import Cachetta
from cachetta.read_cache import read_cache
from cachetta.write_cache import write_cache, _created_dirs
from cachetta.utils.cache_fn import _in_flight

# Resolved via import_module because these module names are shadowed by
# same-named functions re-exported from their packages, which breaks string
# `patch("…")` targets on Python 3.10's dotted-path lookup.
_read_cache_module = import_module("cachetta.read_cache")
_write_cache_module = import_module("cachetta.write_cache")
_get_last_updated_module = import_module("cachetta.utils.get_last_updated")


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

            with patch.object(_write_cache_module.Path, "mkdir") as mock_mkdir:
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
        with patch.object(_get_last_updated_module.os.path, "exists") as mock_exists:
            get_last_updated("/nonexistent/file.json")
            mock_exists.assert_not_called()


def describe_pickle_loading():
    def test_uses_safe_load():
        """read_cache should use safe_load(f) for deserialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"streaming": True}, f)

            cache = Cachetta(path=str(cache_path))

            with patch.object(_read_cache_module, "safe_load", return_value={"streaming": True}) as mock_load:
                with read_cache(cache) as _data:
                    pass
                mock_load.assert_called_once()

    def test_handles_corrupt_data_gracefully():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "corrupt.dat"
            with open(cache_path, "w") as f:
                f.write("not valid pickle data")

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as data:
                pass
            assert data is None

    def test_handles_missing_file_gracefully():
        cache = Cachetta(path="/nonexistent/missing.dat")
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
