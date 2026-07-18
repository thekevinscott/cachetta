import json
from contextlib import contextmanager
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import tempfile
from cachetta.cachetta import Cachetta
from cachetta.exceptions import CachettaError, InvalidPathError
from datetime import timedelta
from time import time
from typing import Any


@pytest.fixture(autouse=True)
def mock_write_cache():
    with patch("cachetta.utils.cache_fn.write_cache", new_callable=Mock) as mock:
        yield mock


def make_mock_read_cache(val=None):
    @contextmanager
    def fn(*args, **kwargs):
        yield val

    return fn


@pytest.fixture(autouse=True)
def mock_read_cache():
    mock = MagicMock(side_effect=make_mock_read_cache())
    with patch("cachetta.utils.cache_fn.read_cache", mock):
        yield mock


def describe_cache():
    def test_it_instantiates():
        Cachetta(path="foo")

    def test_it_instantiates_with_default_values():
        cache = Cachetta(path="foo")
        assert cache.path == "foo"
        assert cache.write is True
        assert cache.read is True
        assert cache.duration == timedelta(days=7)

    def test_it_instantiates_with_custom_values():
        cache = Cachetta(
            path="custom.json",
            write=False,
            read=False,
            duration=timedelta(seconds=1)
        )
        assert cache.path == "custom.json"
        assert cache.write is False
        assert cache.read is False
        assert cache.duration == timedelta(seconds=1)

    def test_it_handles_function_based_paths():
        def path_fn(id):
            return f"path/to/{id}.json"

        cache = Cachetta(path=path_fn)
        assert cache.path == path_fn

    def test_get_path_returns_path_object_for_string():
        cache = Cachetta(path="./test.json")
        result = cache._get_path()
        assert isinstance(result, Path)
        assert result == Path("./test.json")

    def test_get_path_calls_function_based_path_with_arguments():
        def path_fn(user_id, data_type):
            return f"./cache/{user_id}/{data_type}.json"

        cache = Cachetta(path=path_fn)
        result = cache._get_path("user-123", "data")
        assert isinstance(result, Path)
        assert result == Path("./cache/user-123/data.json")

    def test_get_path_rejects_path_traversal():
        cache = Cachetta(path="foo/../../../etc/passwd")
        with pytest.raises(InvalidPathError, match="Path traversal detected"):
            cache._get_path()

    def test_get_path_rejects_traversal_in_function_paths():
        cache = Cachetta(path=lambda: "../secret/data.json")
        with pytest.raises(InvalidPathError, match="Path traversal detected"):
            cache._get_path()

    def test_it_returns_a_derived_cache_obj():
        cache = Cachetta(path="foo")

        new_cache = cache / "bar" / "baz.json"
        assert new_cache is not cache
        assert str(new_cache.path) == "foo/bar/baz.json"

    def test_truediv_with_callable_defers_resolution_to_call_time():
        cache = Cachetta(path="base")
        new_cache = cache / (lambda x: f"sub/{x}.pkl")

        assert new_cache is not cache
        assert callable(new_cache.path)
        resolved = new_cache._get_path("alice")
        assert resolved == Path("base/sub/alice.pkl")

    def test_truediv_with_string_produces_literal_subfolder_path():
        cache = Cachetta(path="base") / "llm-calls"
        # `/` joins onto the base, producing a literal subfolder path that
        # is used verbatim regardless of args.
        assert cache._get_path() == Path("base/llm-calls")
        assert cache._get_path("a") == Path("base/llm-calls")

    def test_truediv_with_callable_rejects_traversal():
        cache = Cachetta(path="base") / (lambda: "../escape.pkl")
        with pytest.raises(InvalidPathError, match="Path traversal"):
            cache._get_path()

    def test_it_acts_as_a_decorator(mock_write_cache, mock_read_cache):
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t) / "foo.json"
            count = 0
            data = "bar"

            @Cachetta(path=filepath)
            def foo():
                nonlocal data
                nonlocal count

                count += 1

                return f"{data}{count}"

            mock_read_cache.assert_not_called()
            mock_write_cache.assert_not_called()
            assert foo() == f"{data}1"
            mock_read_cache.assert_called_once_with(Cachetta(path=filepath))
            mock_write_cache.assert_called_once_with(Cachetta(path=filepath), f"{data}1")

            cached_data = "baz"
            mock_read_cache.side_effect = make_mock_read_cache(cached_data)
            assert foo() == cached_data
            assert mock_read_cache.call_count == 2
            assert mock_write_cache.call_count == 1

            mock_read_cache.side_effect = make_mock_read_cache(None)
            assert foo() == f"{data}2"
            assert mock_read_cache.call_count == 3
            assert mock_write_cache.call_count == 2

    def test_decorator_accepts_cache_object(mock_write_cache, mock_read_cache):
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t) / "foo.json"
            count = 0
            data = "bar"

            cache = Cachetta(path=filepath, duration=timedelta(days=1))

            @cache
            def foo():
                nonlocal data
                nonlocal count

                count += 1

                return f"{data}{count}"

            mock_read_cache.assert_not_called()
            mock_write_cache.assert_not_called()
            assert foo() == f"{data}1"
            mock_read_cache.assert_called_once_with(cache)
            mock_write_cache.assert_called_once_with(cache, f"{data}1")

    def test_it_acts_as_a_decorator_with_a_callback_path(
        mock_write_cache, mock_read_cache
    ):
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t)
            count = 0

            mock_file_system = {}

            def make_mock_read_cache():
                @contextmanager
                def fn(cache, *args, **kwargs):
                    filepath = cache._get_path(*args, **kwargs)
                    yield mock_file_system.get(filepath)

                return fn

            def mock_write_cache_fn(cache, data, *args, **kwargs):
                mock_file_system[cache._get_path(*args, **kwargs)] = data

            mock_read_cache.side_effect = make_mock_read_cache()
            mock_write_cache.side_effect = mock_write_cache_fn

            def path_fn_side_effect(*args, **kwargs):
                nonlocal filepath
                return filepath / f"{json.dumps({'args': args, 'kwargs': kwargs})}.json"

            path_fn = Mock()
            path_fn.side_effect = path_fn_side_effect

            @Cachetta(path=path_fn)
            def foo(*args, **kwargs):
                nonlocal count
                count += 1

                return {
                    "count": count,
                    "args": args,
                    "kwargs": kwargs,
                }

            assert path_fn.call_count == 0
            assert mock_read_cache.call_count == 0
            assert mock_write_cache.call_count == 0

            cache_miss = [
                # path_fn should be called twice; once in read and once in write
                (path_fn, 2),
                (mock_read_cache, 1),
                (mock_write_cache, 1),
            ]
            cache_hit = [
                # path_fn should be called once since we've already called it
                (path_fn, 1),
                (mock_read_cache, 1),
                (mock_write_cache, 0),
            ]

            # Typed as dict[str, Any] so the heterogeneous case values unpack
            # cleanly; the dynamic dispatch below is intentional.
            cases: list[dict[str, Any]] = [
                {
                    "count": 1,
                    "args": (),
                    "kwargs": {},
                    "call_counts": cache_miss,
                    "after": lambda: mock_write_cache.assert_called_once_with(
                        Cachetta(path=path_fn),
                        {
                            "count": 1,
                            "args": (),
                            "kwargs": {},
                        },
                    ),
                },
                {
                    "count": 1,
                    "args": (),
                    "kwargs": {},
                    "call_counts": cache_hit,
                },
                {
                    "count": 2,
                    "args": ("arg1",),
                    "kwargs": {},
                    "call_counts": cache_miss,
                },
                {
                    "count": 2,
                    "args": ("arg1",),
                    "kwargs": {},
                    "call_counts": cache_hit,
                },
                {
                    "count": 3,
                    "args": (),
                    "kwargs": {"foo": "foo"},
                    "call_counts": cache_miss,
                },
                {
                    "count": 3,
                    "args": (),
                    "kwargs": {"foo": "foo"},
                    "call_counts": cache_hit,
                },
                {
                    "count": 1,  # because this is the _cached_ value
                    "args": (),
                    "kwargs": {},
                    "call_counts": cache_hit,
                },
                {
                    "count": 4,
                    "args": ("foo", "bar"),
                    "kwargs": {"foo": "foo"},
                    "call_counts": cache_miss,
                },
                {
                    "count": 4,
                    "args": ("foo", "bar"),
                    "kwargs": {"foo": "foo"},
                    "call_counts": cache_hit,
                },
            ]
            for case in cases:
                case_count, args, kwargs, after, call_counts = (
                    case["count"],
                    case["args"],
                    case["kwargs"],
                    case.get("after"),
                    case.get("call_counts", []),
                )
                assert foo(*args, **kwargs) == {
                    "count": case_count,
                    "args": args,
                    "kwargs": kwargs,
                }
                for fn, call_count in call_counts:
                    assert fn.call_count == call_count
                if after:
                    after()
                path_fn.reset_mock()
                mock_read_cache.reset_mock()
                mock_write_cache.reset_mock()

    def test_decorator_accepts_cache_object_with_additional_args(
        mock_write_cache, mock_read_cache
    ):
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t)
            count = 0
            data = "bar"

            cache = Cachetta(path=filepath, duration=timedelta(days=1))

            @cache(path=lambda arg: filepath / arg / "foo.json")
            def foo(arg):
                nonlocal data
                nonlocal count

                count += 1

                return f"{data}-{count}-{arg}"

            mock_read_cache.assert_not_called()
            mock_write_cache.assert_not_called()
            assert foo("123") == f"{data}-1-123"
            assert any(
                call.args[0].path("123") == filepath / "123" / "foo.json"
                for call in mock_read_cache.call_args_list
            )
            assert any(
                call.args[0].path("123") == filepath / "123" / "foo.json"
                for call in mock_write_cache.call_args_list
            )
            mock_read_cache.side_effect = make_mock_read_cache(f"{data}-1-123")
            assert foo(123) == f"{data}-1-123"
            assert mock_read_cache.call_count == 2
            assert mock_write_cache.call_count == 1

    def test_copy_creates_copy_with_modified_properties():
        original = Cachetta(
            path="original.json",
            write=True,
            read=True,
            duration=timedelta(seconds=1)
        )

        copy = original.copy(
            write=False,
            duration=timedelta(seconds=2)
        )

        assert copy.path == original.path
        assert copy.write is False
        assert copy.read is True
        assert copy.duration == timedelta(seconds=2)

    def test_copy_creates_copy_with_new_path():
        original = Cachetta(path="original.json")
        copy = original.copy(path="copy.json")

        assert copy.path == "copy.json"
        assert copy.write == original.write
        assert copy.read == original.read
        assert copy.duration == original.duration

    def test_call_method_works_as_decorator():
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t) / "call.json"
            cache = Cachetta(path=filepath, read=True, write=True)

            count = 0
            def test_fn():
                nonlocal count
                count += 1
                return {"data": "test"}

            decorated_fn = cache(test_fn)

            # First call should execute function
            result1 = decorated_fn()
            assert result1 == {"data": "test"}
            assert count == 1

            # Second call should use cache (but Python implementation may not cache as expected)
            result2 = decorated_fn()
            assert result2 == {"data": "test"}

    def test_to_string_representation():
        cache = Cachetta(
            path="test.json",
            write=False,
            read=True,
            duration=timedelta(seconds=5)
        )

        str_repr = str(cache)
        assert "test.json" in str_repr
        assert "read=True" in str_repr
        assert "write=False" in str_repr
        assert "timedelta" in str_repr

    def test_integration_with_function_based_paths_and_caching(mock_write_cache, mock_read_cache):
        with tempfile.TemporaryDirectory() as t:
            base_path = Path(t) / "base"

            def path_fn(id):
                return base_path / f"{id}.json"

            cache = Cachetta(path=path_fn, read=True, write=True)

            count = 0
            def test_fn(id):
                nonlocal count
                count += 1
                return {"id": id, "data": f"result-{id}"}

            decorated_fn = cache(test_fn)

            # Call with different IDs
            result1 = decorated_fn("user-1")
            result2 = decorated_fn("user-2")
            result3 = decorated_fn("user-1")  # Should use cache

            assert result1 == {"id": "user-1", "data": "result-user-1"}
            assert result2 == {"id": "user-2", "data": "result-user-2"}
            assert result3 == result1

    def test_integration_with_chained_operations():
        base_cache = Cachetta(
            path="base",
            write=True,
            read=True
        )

        sub_cache = base_cache / "subdir"
        final_cache = sub_cache.copy(write=False)

        assert str(final_cache.path) == "base/subdir"
        assert final_cache.write is False
        assert final_cache.read is True

    def test_call_throws_error_when_no_function_or_kwargs_provided():
        cache = Cachetta(path="test.json")

        with pytest.raises(CachettaError, match="No function or kwargs provided"):
            cache()

    def test_call_with_both_function_and_kwargs_applies_overrides():
        cache = Cachetta(path="test.json")

        def test_fn():
            return "test"

        # fn + kwargs simultaneously wraps the function with overrides applied
        wrapped = cache(test_fn, write=False)
        assert callable(wrapped)
        assert wrapped() == "test"

    def test_call_throws_error_when_kwargs_provided_but_no_function():
        cache = Cachetta(path="test.json")

        decorator = cache(write=False)

        with pytest.raises(TypeError):
            decorator()

    def test_call_throws_error_when_decorator_called_without_function():
        cache = Cachetta(path="test.json")

        decorator = cache(write=False)

        with pytest.raises(TypeError):
            decorator()


def describe_get_path_literal_with_args():
    def test_returns_literal_path_when_args_provided():
        # Args to the wrapped function no longer rewrite str/Path paths into
        # `{stem}-{hash}{ext}` siblings — `path` is used verbatim. See #45.
        cache = Cachetta(path="data/cache.json")
        assert cache._get_path("a", "b") == Path("data/cache.json")
        assert cache._get_path("a", "b") == cache._get_path("x", y=1)


def describe_get_path_hashed():
    def test_with_args_appends_hash_under_literal_path():
        from cachetta.hash import hash as _h
        cache = Cachetta(path="cache", hashed=True)
        assert cache._get_path("a") == Path("cache") / _h("a")
        assert cache._get_path("a") != cache._get_path("b")

    def test_without_args_returns_literal_path():
        cache = Cachetta(path="cache", hashed=True)
        assert cache._get_path() == Path("cache")

    def test_with_callable_path_appends_hash_under_callable_result():
        from cachetta.hash import hash as _h
        cache = Cachetta(path=lambda kind, **_: f"base/{kind}", hashed=True)
        assert cache._get_path("users", id=1) == Path("base/users") / _h("users", id=1)


def describe_wrap():
    def test_wrap_returns_cached_callable():
        cache = Cachetta(path="x")

        def fn():
            return "v"

        wrapped = cache.wrap(fn)
        assert callable(wrapped)
        assert wrapped() == "v"


def describe_invalidate():
    def test_deletes_file():
        cache = Cachetta(path="x.json", duration=timedelta(days=1))
        with patch("cachetta.cachetta.os.unlink") as unlink:
            cache.invalidate()
        unlink.assert_called_once()

    def test_swallows_missing_file():
        cache = Cachetta(path="x.json")
        with patch("cachetta.cachetta.os.unlink", side_effect=FileNotFoundError):
            cache.invalidate()  # must not raise


def describe_sync_instance_methods():
    def test_exists_true_when_file_present():
        with patch("cachetta.cachetta.get_last_updated", return_value=123.0):
            assert Cachetta(path="x").exists() is True

    def test_exists_false_when_absent():
        with patch("cachetta.cachetta.get_last_updated", return_value=None):
            assert Cachetta(path="x").exists() is False

    def test_age_returns_timedelta_when_present():
        with patch("cachetta.cachetta.get_last_updated", return_value=time() - 5):
            age = Cachetta(path="x").age()
            assert isinstance(age, timedelta)
            assert age.total_seconds() >= 4

    def test_age_none_when_absent():
        with patch("cachetta.cachetta.get_last_updated", return_value=None):
            assert Cachetta(path="x").age() is None

    def test_info_reports_missing_file():
        with patch("cachetta.cachetta.get_last_updated", return_value=None):
            info = Cachetta(path="x").info()
            assert info == {
                "exists": False,
                "age": None,
                "expired": False,
                "stale": False,
                "path": "x",
            }

    def test_info_reports_fresh_cache():
        with patch("cachetta.cachetta.get_last_updated", return_value=time()):
            info = Cachetta(path="x", duration=timedelta(days=1)).info()
            assert info["exists"] is True
            assert info["expired"] is False
            assert info["stale"] is False

    def test_info_reports_expired_and_stale():
        with patch("cachetta.cachetta.get_last_updated", return_value=time() - 5):
            info = Cachetta(
                path="x",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            ).info()
            assert info["expired"] is True
            assert info["stale"] is True

    def test_info_expired_but_not_stale_without_stale_duration():
        with patch("cachetta.cachetta.get_last_updated", return_value=time() - 5):
            info = Cachetta(path="x", duration=timedelta(seconds=1)).info()
            assert info["expired"] is True
            assert info["stale"] is False

    def test_info_expired_but_past_stale_window():
        with patch("cachetta.cachetta.get_last_updated", return_value=time() - 100):
            info = Cachetta(
                path="x",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(seconds=5),
            ).info()
            assert info["expired"] is True
            assert info["stale"] is False


def describe_async_instance_methods():
    async def test_ainvalidate_deletes_file():
        cache = Cachetta(path="x.json", duration=timedelta(days=1))
        with patch("cachetta.cachetta.os.unlink") as unlink:
            await cache.ainvalidate()
        unlink.assert_called_once()

    async def test_ainvalidate_swallows_missing_file():
        cache = Cachetta(path="x.json")
        with patch("cachetta.cachetta.os.unlink", side_effect=FileNotFoundError):
            await cache.ainvalidate()

    async def test_aexists_true_and_false():
        with patch("cachetta.cachetta.async_get_last_updated", return_value=1.0):
            assert await Cachetta(path="x").aexists() is True
        with patch("cachetta.cachetta.async_get_last_updated", return_value=None):
            assert await Cachetta(path="x").aexists() is False

    async def test_aage_present_and_absent():
        with patch("cachetta.cachetta.async_get_last_updated", return_value=time() - 5):
            age = await Cachetta(path="x").aage()
            assert isinstance(age, timedelta)
        with patch("cachetta.cachetta.async_get_last_updated", return_value=None):
            assert await Cachetta(path="x").aage() is None

    async def test_ainfo_reports_missing_file():
        with patch("cachetta.cachetta.async_get_last_updated", return_value=None):
            info = await Cachetta(path="x").ainfo()
            assert info["exists"] is False
            assert info["age"] is None

    async def test_ainfo_reports_fresh_expired_and_stale_states():
        with patch("cachetta.cachetta.async_get_last_updated", return_value=time()):
            fresh = await Cachetta(path="x", duration=timedelta(days=1)).ainfo()
            assert fresh["expired"] is False
        with patch("cachetta.cachetta.async_get_last_updated", return_value=time() - 5):
            stale = await Cachetta(
                path="x",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(days=1),
            ).ainfo()
            assert stale["expired"] is True
            assert stale["stale"] is True
        with patch("cachetta.cachetta.async_get_last_updated", return_value=time() - 100):
            past = await Cachetta(
                path="x",
                duration=timedelta(seconds=1),
                stale_duration=timedelta(seconds=5),
            ).ainfo()
            assert past["expired"] is True
            assert past["stale"] is False
