import pickle
from datetime import timedelta
from unittest.mock import patch, Mock
import pytest
from pathlib import Path
import tempfile
from cachetta.cachetta import Cachetta  # mock-enforce-ignore: real Cachetta config object used as a plain-data fixture
from cachetta.read_cache import (
    read_cache,
    read_stale_cache,
    async_read_cache,
    async_read_stale_cache,
    _read_cache_file,
    _blocking_read_impl,
)


@pytest.fixture(autouse=True)
def mock_should_use_read_cache():
    with patch("cachetta.utils.should_use_read_cache.should_use_read_cache", new_callable=Mock) as mock:
        mock.return_value = True
        yield mock


class MockCache(Cachetta):
    pass


def describe_read_cache():
    def test_it_yields_none_if_no_cache_is_provided():
        with read_cache(None) as d:
            assert d is None

    def test_it_yields_none_if_should_use_read_cache_is_false(
        mock_should_use_read_cache,
    ):
        mock_should_use_read_cache.return_value = False
        with read_cache(MockCache(path="foobar")) as d:
            assert d is None

    def test_it_yields_data(mock_should_use_read_cache):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "file.dat"
            data = {
                "foo": "bar",
            }
            with open(temp_file, "wb") as f:
                pickle.dump(data, f)
            mock_should_use_read_cache.return_value = True
            with read_cache(MockCache(path=temp_file)) as d:
                pass
            assert d == data

    def test_it_returns_none_for_corrupt_data(
        mock_should_use_read_cache,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "file.dat"
            data = "foobar"
            with open(temp_file, "w") as f:
                f.write(data)
            mock_should_use_read_cache.return_value = True
            with read_cache(MockCache(path=temp_file)) as f:
                pass
            assert f is None

    def test_it_handles_function_based_cache_paths(mock_should_use_read_cache):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "dynamic-cache.dat"
            data = {"dynamic": True}

            with open(temp_file, "wb") as f:
                pickle.dump(data, f)

            mock_should_use_read_cache.return_value = True

            def path_fn(id):
                return temp_file

            with read_cache(MockCache(path=path_fn), "test-id") as d:
                pass
            assert d == data

    def test_it_handles_complex_nested_objects(mock_should_use_read_cache):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "complex.dat"
            complex_data = {
                "string": "hello",
                "number": 123,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "object": {"nested": {"deep": True}}
            }

            with open(temp_file, "wb") as f:
                pickle.dump(complex_data, f)

            mock_should_use_read_cache.return_value = True

            with read_cache(MockCache(path=temp_file)) as d:
                pass
            assert d == complex_data
            assert d["array"] == [1, 2, 3]
            assert d["object"]["nested"]["deep"] is True

    def test_it_returns_null_for_unknown_extension_when_cache_should_not_be_used(mock_should_use_read_cache):
        mock_should_use_read_cache.return_value = False

        with read_cache(MockCache(path="test.unknown")) as d:
            pass
        assert d is None

    def test_it_handles_complex_python_types(mock_should_use_read_cache):
        """Pickle can handle types that JSON cannot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "complex.dat"
            data = {
                "set": {1, 2, 3},
                "tuple": (1, 2, 3),
                "bytes": b"hello",
            }
            with open(temp_file, "wb") as f:
                pickle.dump(data, f)

            mock_should_use_read_cache.return_value = True
            with read_cache(MockCache(path=temp_file)) as d:
                pass
            assert d["set"] == {1, 2, 3}
            assert d["tuple"] == (1, 2, 3)
            assert d["bytes"] == b"hello"

    def test_it_yields_none_when_file_disappears_after_should_use_check():
        """should_use_read_cache passes but the file is gone when opened."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.dat"
            with patch("cachetta.read_cache.should_use_read_cache", return_value=True):
                with read_cache(MockCache(path=missing)) as d:
                    pass
            assert d is None

    def test_it_yields_none_for_unsafe_pickle():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "unsafe.dat"
            with open(temp_file, "wb") as f:
                pickle.dump(_Unsafe(), f)
            with patch("cachetta.read_cache.should_use_read_cache", return_value=True):
                with read_cache(MockCache(path=temp_file)) as d:
                    pass
            assert d is None

    def test_it_yields_lru_hit_without_disk():
        cache = MockCache(path="foo", lru_size=10)
        cache._lru_set("does-not-matter", "sentinel-value")
        # Override _get_path to return the LRU key
        with patch.object(cache, "_get_path", return_value="does-not-matter"):
            with read_cache(cache) as d:
                pass
        assert d == "sentinel-value"


class _Unsafe:
    """A type that is not in the pickle allowlist."""


def describe_read_cache_file():
    def test_it_returns_none_for_unsafe_pickle():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "unsafe.dat"
            with open(temp_file, "wb") as f:
                pickle.dump(_Unsafe(), f)
            assert _read_cache_file(temp_file) is None

    def test_it_returns_none_for_missing_file():
        assert _read_cache_file("/nonexistent/path/file.dat") is None

    def test_it_returns_data_for_valid_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "ok.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"a": 1}, f)
            assert _read_cache_file(temp_file) == {"a": 1}


def describe_read_stale_cache():
    def test_it_returns_none_when_no_stale_duration():
        cache = MockCache(path="foo", stale_duration=None)
        assert read_stale_cache(cache) is None

    def test_it_returns_none_when_read_is_false():
        cache = MockCache(path="foo", read=False, stale_duration=timedelta(days=1))
        assert read_stale_cache(cache) is None

    def test_it_returns_none_when_file_does_not_exist():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MockCache(
                path=Path(tmpdir) / "missing.dat",
                stale_duration=timedelta(days=1),
            )
            assert read_stale_cache(cache) is None

    def test_it_returns_data_when_within_stale_window():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "stale.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"stale": True}, f)
            cache = MockCache(
                path=temp_file,
                duration=timedelta(seconds=-1),  # already expired
                stale_duration=timedelta(days=1),
            )
            assert read_stale_cache(cache) == {"stale": True}

    def test_it_returns_none_when_past_stale_window():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "stale.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"stale": True}, f)
            cache = MockCache(
                path=temp_file,
                duration=timedelta(days=-10),  # very expired
                stale_duration=timedelta(days=1),
            )
            assert read_stale_cache(cache) is None


def describe_blocking_read_impl():
    def test_it_returns_data_for_valid_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "ok.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"x": 1}, f)
            cache = MockCache(path=temp_file)
            assert _blocking_read_impl(cache, temp_file) == {"x": 1}

    def test_it_returns_none_for_missing_file():
        cache = MockCache(path="foo")
        assert _blocking_read_impl(cache, Path("/nonexistent/file.dat")) is None

    def test_it_returns_none_for_unsafe_pickle():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "unsafe.dat"
            with open(temp_file, "wb") as f:
                pickle.dump(_Unsafe(), f)
            cache = MockCache(path=temp_file)
            assert _blocking_read_impl(cache, temp_file) is None

    def test_it_returns_none_for_corrupt_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "corrupt.dat"
            with open(temp_file, "w") as f:
                f.write("not a pickle")
            cache = MockCache(path=temp_file)
            assert _blocking_read_impl(cache, temp_file) is None


def describe_async_read_cache():
    async def test_it_yields_none_when_cache_is_none():
        async with async_read_cache(None) as d:
            assert d is None

    async def test_it_yields_lru_hit():
        cache = MockCache(path="foo", lru_size=10)
        cache._lru_set("k", "lru-value")
        with patch.object(cache, "_get_path", return_value="k"):
            async with async_read_cache(cache) as d:
                pass
        assert d == "lru-value"

    async def test_it_yields_data_via_thread():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "ok.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"async": True}, f)
            with patch("cachetta.read_cache.should_use_read_cache", return_value=True):
                async with async_read_cache(MockCache(path=temp_file)) as d:
                    pass
            assert d == {"async": True}

    async def test_it_yields_none_when_should_not_use_cache():
        with patch("cachetta.read_cache.should_use_read_cache", return_value=False):
            async with async_read_cache(MockCache(path="foo")) as d:
                pass
        assert d is None


def describe_async_read_stale_cache():
    async def test_it_returns_stale_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "stale.dat"
            with open(temp_file, "wb") as f:
                pickle.dump({"stale": True}, f)
            cache = MockCache(
                path=temp_file,
                duration=timedelta(seconds=-1),
                stale_duration=timedelta(days=1),
            )
            assert await async_read_stale_cache(cache) == {"stale": True}
