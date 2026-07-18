import asyncio
import os
import pickle
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from time import time
from unittest.mock import patch, Mock, MagicMock

import pytest

from cachetta.cachetta import Cachetta
from cachetta.read_cache import read_stale_cache
from cachetta.write_cache import write_cache_ctx


def describe_unified_call():
    @pytest.fixture(autouse=True)
    def mock_write_cache():
        with patch("cachetta.utils.cache_fn.write_cache", new_callable=Mock) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_read_cache():
        @contextmanager
        def fn(*args, **kwargs):
            yield None
        mock = MagicMock(side_effect=fn)
        with patch("cachetta.utils.cache_fn.read_cache", mock):
            yield mock

    def test_fn_and_kwargs_simultaneously():
        cache = Cachetta(path="test.json")

        def my_fn():
            return {"result": True}

        wrapped = cache(my_fn, write=False)
        assert callable(wrapped)
        result = wrapped()
        assert result == {"result": True}

    def test_fn_and_path_override():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path="base.json")

            def my_fn(x):
                return {"x": x}

            def new_path(x):
                return f"{tmpdir}/{x}.json"
            wrapped = cache(my_fn, path=new_path)
            result = wrapped("hello")
            assert result == {"x": "hello"}


def describe_auto_method_receiver():
    @pytest.fixture(autouse=True)
    def mock_write_cache():
        with patch("cachetta.utils.cache_fn.write_cache", new_callable=Mock) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_read_cache():
        @contextmanager
        def fn(*args, **kwargs):
            yield None
        mock = MagicMock(side_effect=fn)
        with patch("cachetta.utils.cache_fn.read_cache", mock):
            yield mock

    def test_receiver_excluded_from_cache_path_automatically(mock_read_cache):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=lambda name: f"{tmpdir}/{name}.json")

            class MyService:
                @cache
                def get_data(self, name):
                    return {"name": name}

            svc = MyService()
            result = svc.get_data("test")
            assert result == {"name": "test"}

            # read_cache is called with the receiver stripped — no skip_self flag.
            call_args = mock_read_cache.call_args
            # The second positional arg to read_cache is the first cache_arg.
            assert call_args[0][1] == "test"


def describe_cache_invalidation():
    def test_invalidate_deletes_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')

            cache = Cachetta(path=str(cache_path))
            assert cache_path.exists()

            cache.invalidate()
            assert not cache_path.exists()

    def test_invalidate_noop_for_missing_file():
        cache = Cachetta(path="/nonexistent/test.json")
        # Should not raise
        cache.invalidate()

    def test_clear_is_alias_for_invalidate():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')

            cache = Cachetta(path=str(cache_path))
            cache.clear()
            assert not cache_path.exists()

    def test_invalidate_with_path_function():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "user-123.json"
            cache_path.write_text('{"id": "123"}')

            cache = Cachetta(path=lambda uid: f"{tmpdir}/user-{uid}.json")
            cache.invalidate("123")
            assert not cache_path.exists()


def describe_cache_inspection():
    def test_exists_true_for_existing_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')

            cache = Cachetta(path=str(cache_path))
            assert cache.exists() is True

    def test_exists_false_for_missing_file():
        cache = Cachetta(path="/nonexistent/test.json")
        assert cache.exists() is False

    def test_age_returns_timedelta():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')

            cache = Cachetta(path=str(cache_path))
            age = cache.age()
            assert isinstance(age, timedelta)
            assert age.total_seconds() < 1.0

    def test_age_returns_none_for_missing():
        cache = Cachetta(path="/nonexistent/test.json")
        assert cache.age() is None

    def test_info_for_existing_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')

            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))
            info = cache.info()
            assert info["exists"] is True
            assert isinstance(info["age"], timedelta)
            assert info["expired"] is False
            assert info["stale"] is False
            assert info["path"] == str(cache_path)

    def test_info_for_missing_file():
        cache = Cachetta(path="/nonexistent/test.json")
        info = cache.info()
        assert info["exists"] is False
        assert info["age"] is None
        assert info["expired"] is False
        assert info["stale"] is False

    def test_info_shows_expired():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')
            # Set mtime to 2 hours ago
            old_time = time() - 7200
            os.utime(cache_path, (old_time, old_time))

            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))
            info = cache.info()
            assert info["exists"] is True
            assert info["expired"] is True

    def test_info_shows_stale():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache_path.write_text('{"data": true}')
            # Set mtime to 2 hours ago
            old_time = time() - 7200
            os.utime(cache_path, (old_time, old_time))

            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=4),
            )
            info = cache.info()
            assert info["expired"] is True
            assert info["stale"] is True


def describe_conditional_caching():
    def test_condition_prevents_caching_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(
                path=str(cache_path),
                condition=lambda r: r is not None,
            )

            @cache
            def get_data():
                return None

            result = get_data()
            assert result is None
            assert not cache_path.exists()

    def test_condition_allows_caching_valid_result():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(
                path=str(cache_path),
                condition=lambda r: r is not None,
            )

            @cache
            def get_data():
                return {"valid": True}

            result = get_data()
            assert result == {"valid": True}
            assert cache_path.exists()

    def test_condition_with_custom_logic():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(
                path=str(cache_path),
                condition=lambda r: isinstance(r, dict) and "error" not in r,
            )

            @cache
            def get_data(include_error):
                if include_error:
                    return {"error": "something went wrong"}
                return {"data": "success"}

            # Error result should not be cached
            result1 = get_data(True)
            assert result1 == {"error": "something went wrong"}
            assert not cache_path.exists()

    async def test_condition_async():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(
                path=str(cache_path),
                condition=lambda r: r is not None,
            )

            @cache
            async def get_data():
                return None

            result = await get_data()
            assert result is None
            assert not cache_path.exists()


def describe_literal_str_path_with_args():
    """`path=str|Path` is now used verbatim regardless of wrapped-function
    arguments. Use a callable `path` to vary the cache file by arg."""

    def test_literal_path_ignores_args():
        cache = Cachetta(path="cache/data.json")
        assert cache._get_path("arg1") == Path("cache/data.json")
        assert cache._get_path("arg1") == cache._get_path("arg2")

    def test_literal_path_ignores_kwargs():
        cache = Cachetta(path="cache/data.json")
        assert cache._get_path(user="alice") == Path("cache/data.json")
        assert cache._get_path(user="alice") == cache._get_path(user="bob")

    def test_callable_path_still_varies_by_args():
        cache = Cachetta(path=lambda name: f"cache/{name}.json")
        assert cache._get_path("alice") == Path("cache/alice.json")
        assert cache._get_path("alice") != cache._get_path("bob")


def describe_stale_while_revalidate():
    def test_read_stale_cache_returns_none_without_stale_duration():
        cache = Cachetta(path="/nonexistent/test.json")
        result = read_stale_cache(cache)
        assert result is None

    def test_read_stale_cache_returns_none_for_fresh_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"data": True}, f)

            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )
            # File is fresh, so stale cache should return None
            result = read_stale_cache(cache)
            assert result is None

    def test_read_stale_cache_returns_data_in_stale_window():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"data": True}, f)
            # Set mtime to 90 minutes ago (expired but within stale window)
            old_time = time() - 5400
            os.utime(cache_path, (old_time, old_time))

            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )
            result = read_stale_cache(cache)
            assert result == {"data": True}

    def test_read_stale_cache_returns_none_past_stale_window():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"data": True}, f)
            # Set mtime to 3 hours ago (past stale window)
            old_time = time() - 10800
            os.utime(cache_path, (old_time, old_time))

            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )
            result = read_stale_cache(cache)
            assert result is None

    async def test_stale_while_revalidate_async():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"version": 1}, f)
            # Make it expired but in stale window
            old_time = time() - 5400
            os.utime(cache_path, (old_time, old_time))

            call_count = 0
            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )

            @cache
            async def get_data():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)
                return {"version": 2}

            # Should return stale data immediately
            result = await get_data()
            assert result == {"version": 1}

            # Wait for background refresh
            await asyncio.sleep(0.1)

            # The function should have been called in the background
            assert call_count == 1


def describe_write_cache_context_manager():
    def test_write_cache_ctx_writes_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path))

            with write_cache_ctx(cache) as writer:
                writer.set({"written": True})

            assert cache_path.exists()
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"written": True}

    def test_write_cache_ctx_noop_when_not_set():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test.json"
            cache = Cachetta(path=str(cache_path))

            with write_cache_ctx(cache) as _writer:
                pass  # Don't set anything

            assert not cache_path.exists()

    def test_write_cache_ctx_noop_for_none_cache():
        with write_cache_ctx(None) as writer:
            writer.set({"data": True})
        # Should not raise


def describe_wrap_method():
    @pytest.fixture(autouse=True)
    def mock_write_cache():
        with patch("cachetta.utils.cache_fn.write_cache", new_callable=Mock) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_read_cache():
        @contextmanager
        def fn(*args, **kwargs):
            yield None
        mock = MagicMock(side_effect=fn)
        with patch("cachetta.utils.cache_fn.read_cache", mock):
            yield mock

    def test_wrap_wraps_function():
        cache = Cachetta(path="test.json")

        def my_fn():
            return {"data": True}

        wrapped = cache.wrap(my_fn)
        result = wrapped()
        assert result == {"data": True}

    def test_wrap_preserves_function_name():
        cache = Cachetta(path="test.json")

        def my_fn():
            return {"data": True}

        wrapped = cache.wrap(my_fn)
        # `wrap` is typed as returning `Callable`, which doesn't statically
        # expose `__name__`; this asserts the runtime attribute that
        # functools.wraps copies over.
        assert wrapped.__name__ == "my_fn"  # ty: ignore[unresolved-attribute]
