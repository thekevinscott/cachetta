"""Comprehensive integration tests using real file I/O, no mocks for core paths."""

import asyncio
import os
import pickle
import tempfile
from datetime import timedelta
from pathlib import Path
from time import time

import pytest

from cachetta import (
    Cachetta,
    CachettaError,
    CacheCorruptError,
    read_cache,
    write_cache,
    write_cache_ctx,
)
from cachetta.utils.cache_fn import _in_flight

# Everything in this module is the integration suite. Integration tests live
# under tests/ (the boundary is by location); the unit-coverage gate measures
# only colocated src/cachetta/**/*_test.py, so these end-to-end tests never
# feed it.


@pytest.fixture(autouse=True)
def clear_in_flight():
    _in_flight.clear()
    yield
    _in_flight.clear()


# -- Basic read/write cycle --

def describe_basic_read_write_cycle():
    def test_write_then_read_json():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=str(cache_path))

            data = {"name": "test", "values": [1, 2, 3]}
            write_cache(cache, data)

            with read_cache(cache) as result:
                pass
            assert result == data

    def test_write_then_read_with_nested_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "nested.json"
            cache = Cachetta(path=str(cache_path))

            data = {
                "level1": {
                    "level2": {
                        "level3": [True, None, 42, "string"]
                    }
                }
            }
            write_cache(cache, data)

            with read_cache(cache) as result:
                pass
            assert result == data

    def test_overwrite_existing_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"version": 1})
            write_cache(cache, {"version": 2})

            with read_cache(cache) as result:
                pass
            assert result == {"version": 2}


# -- Cache expiration --

def describe_cache_expiration():
    def test_fresh_cache_is_readable():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "fresh.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))

            write_cache(cache, {"fresh": True})

            with read_cache(cache) as result:
                pass
            assert result == {"fresh": True}

    def test_expired_cache_returns_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "expired.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(hours=1))

            write_cache(cache, {"expired": True})

            # Set mtime to 2 hours ago
            old_time = time() - 7200
            os.utime(cache_path, (old_time, old_time))

            with read_cache(cache) as result:
                pass
            assert result is None

    def test_zero_duration_always_expires():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "zero.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(seconds=0))

            write_cache(cache, {"data": True})

            with read_cache(cache) as result:
                pass
            assert result is None


# -- Dynamic path functions --

def describe_dynamic_path_functions():
    def test_path_function_with_args():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda user_id: f"{tmpdir}/users/{user_id}.json"
            )

            write_cache(cache, {"name": "Alice"}, "user-1")
            write_cache(cache, {"name": "Bob"}, "user-2")

            with read_cache(cache, "user-1") as result:
                pass
            assert result == {"name": "Alice"}

            with read_cache(cache, "user-2") as result:
                pass
            assert result == {"name": "Bob"}

    def test_path_function_creates_directories():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda cat, item: f"{tmpdir}/{cat}/{item}.json"
            )

            write_cache(cache, {"deep": True}, "cat1", "item1")
            assert (Path(tmpdir) / "cat1" / "item1.json").exists()


# -- Sync decorator --

def describe_sync_decorator():
    def test_decorator_caches_result():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/sync.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return {"computed": True}

            r1 = compute()
            r2 = compute()

            assert r1 == {"computed": True}
            assert r2 == {"computed": True}
            assert call_count == 1

    def test_decorator_with_path_function():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=lambda name: f"{tmpdir}/{name}.json")

            @cache
            def get_user(name):
                nonlocal call_count
                call_count += 1
                return {"name": name}

            r1 = get_user("alice")
            r2 = get_user("bob")
            r3 = get_user("alice")

            assert r1 == {"name": "alice"}
            assert r2 == {"name": "bob"}
            assert r3 == {"name": "alice"}
            assert call_count == 2

    def test_decorator_reraises_exceptions():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/err.json")

            @cache
            def failing():
                raise ValueError("boom")

            with pytest.raises(ValueError, match="boom"):
                failing()

    def test_decorator_does_not_cache_after_exception():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/err.json")

            @cache
            def maybe_fail():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ValueError("first call fails")
                return {"success": True}

            with pytest.raises(ValueError):
                maybe_fail()

            # Second call should succeed (no cached error)
            result = maybe_fail()
            assert result == {"success": True}
            assert call_count == 2


# -- Async decorator --

def describe_async_decorator():
    async def test_async_decorator_caches_result():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/async.json")

            @cache
            async def compute():
                nonlocal call_count
                call_count += 1
                return {"async_result": True}

            r1 = await compute()
            r2 = await compute()

            assert r1 == {"async_result": True}
            assert r2 == {"async_result": True}
            assert call_count == 1

    async def test_async_decorator_with_path_function():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=lambda key: f"{tmpdir}/{key}.json")

            @cache
            async def fetch(key):
                nonlocal call_count
                call_count += 1
                return {"key": key}

            r1 = await fetch("a")
            r2 = await fetch("b")
            r3 = await fetch("a")

            assert r1 == {"key": "a"}
            assert r2 == {"key": "b"}
            assert r3 == {"key": "a"}
            assert call_count == 2

    async def test_async_decorator_reraises():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/err.json")

            @cache
            async def failing():
                raise RuntimeError("async boom")

            with pytest.raises(RuntimeError, match="async boom"):
                await failing()

    async def test_async_call_deduplication():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/dedup.json", read=False)

            @cache
            async def slow_compute():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.05)
                return {"result": call_count}

            results = await asyncio.gather(
                slow_compute(), slow_compute(), slow_compute()
            )

            assert call_count == 1
            assert all(r == {"result": 1} for r in results)


# -- Copy and path composition --

def describe_copy_and_composition():
    def test_slash_operator():
        cache = Cachetta(path="base")
        sub = cache / "sub" / "deep.json"
        assert str(sub.path) == "base/sub/deep.json"
        assert sub.write == cache.write
        assert sub.read == cache.read

    def test_slash_string_produces_literal_subfolder_path():
        """`cache / 'sub'` joins onto the base path, producing a literal
        subfolder path used verbatim regardless of args."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=tmpdir) / "llm-calls"
            assert cache._get_path() == Path(tmpdir) / "llm-calls"
            assert cache._get_path("a") == Path(tmpdir) / "llm-calls"

    def test_slash_callable_resolves_at_call_time():
        """`cache / fn` should defer path resolution to call time, joining
        the callable's return onto the cache's base folder.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=tmpdir) / (lambda url: f"{url.split(':')[0]}/{url.split(':')[1]}.pkl")

            resolved = cache._get_path("pdf:2401.12345v1")
            assert resolved == Path(tmpdir) / "pdf" / "2401.12345v1.pkl"

    def test_slash_callable_decorator_writes_to_resolved_path():
        """End-to-end: decorating with `cache / fn` writes to the callable-derived path
        and reads back from the same location on a subsequent call.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=tmpdir) / (lambda kind, ident: f"{kind}/{ident}.pkl")

            @cache
            def download(kind, ident):
                nonlocal call_count
                call_count += 1
                return {"kind": kind, "ident": ident, "n": call_count}

            r1 = download("pdf", "2401.12345v1")
            assert r1 == {"kind": "pdf", "ident": "2401.12345v1", "n": 1}
            expected_file = Path(tmpdir) / "pdf" / "2401.12345v1.pkl"
            assert expected_file.exists(), (
                "Expected cache file at %s" % expected_file
            )

            r2 = download("pdf", "2401.12345v1")
            assert r2 == r1
            assert call_count == 1

            r3 = download("html", "abc")
            assert r3 == {"kind": "html", "ident": "abc", "n": 2}
            assert (Path(tmpdir) / "html" / "abc.pkl").exists()

    def test_slash_callable_uses_path_traversal_as_given():
        """A callable returning a `..`-traversing path is used verbatim: cache
        paths are trusted input, not validated (see docs/python.md)."""
        cache = Cachetta(path="base") / (lambda: "../escape/file.pkl")
        assert cache._get_path() == Path("base/../escape/file.pkl")

    def test_slash_callable_composition_with_hash_helper():
        """A callable returned from `/` can use a hash-style helper to key on a
        subset of args, the common 'kind-routing + hashed-id' pattern.
        """
        import hashlib
        import json as _json

        def _hash(*args, **kwargs):
            return hashlib.sha256(
                _json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=tmpdir) / (lambda kind, payload: f"{kind}/{_hash(payload)}.pkl")

            @cache
            def fetch(kind, payload):
                return {"kind": kind, "payload": payload}

            fetch("llm", {"prompt": "hello"})
            fetch("llm", {"prompt": "world"})
            fetch("embed", {"prompt": "hello"})

            llm_dir = Path(tmpdir) / "llm"
            embed_dir = Path(tmpdir) / "embed"
            assert llm_dir.is_dir() and embed_dir.is_dir()
            assert len(list(llm_dir.iterdir())) == 2
            assert len(list(embed_dir.iterdir())) == 1

    def test_copy_overrides():
        original = Cachetta(
            path="original.json",
            write=True,
            read=True,
            duration=timedelta(days=7),
        )
        copied = original.copy(write=False, duration=timedelta(hours=1))
        assert copied.write is False
        assert copied.read is True
        assert copied.duration == timedelta(hours=1)
        assert copied.path == "original.json"

# -- Corrupt cache recovery --

def describe_corrupt_cache_recovery():
    def test_corrupt_json_yields_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "corrupt.json"
            cache_path.write_text("not valid json {{{")

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as result:
                pass
            assert result is None

    def test_empty_file_yields_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "empty.json"
            cache_path.write_text("")

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as result:
                pass
            assert result is None

    def test_binary_garbage_yields_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "binary.json"
            cache_path.write_bytes(b"\x00\x01\x02\xff\xfe")

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as result:
                pass
            assert result is None


# -- Paths are trusted input --
#
# Cachetta does not validate `path` (literal or callable): `..` segments,
# absolute paths, and symlinks are all used as given. Cache paths are
# developer-authored configuration, not untrusted input — see
# docs/python.md for the full contract.

def describe_trusted_paths():
    def test_dotdot_in_string_path_is_used_as_given():
        cache = Cachetta(path="foo/../../../etc/passwd")
        assert cache._get_path() == Path("foo/../../../etc/passwd")

    def test_dotdot_in_function_path_is_used_as_given():
        cache = Cachetta(path=lambda: "../../../etc/passwd")
        assert cache._get_path() == Path("../../../etc/passwd")

    def test_dotdot_in_path_object_is_used_as_given():
        cache = Cachetta(path=Path("foo/../../bar"))
        assert cache._get_path() == Path("foo/../../bar")

    def test_allows_path_with_dots_in_filename():
        cache = Cachetta(path="foo/bar.baz.json")
        result = cache._get_path()
        assert result == Path("foo/bar.baz.json")

    def test_absolute_path_outside_cwd_writes_and_reads(tmp_path):
        """An absolute path pointing outside the CWD works end-to-end: it
        is used verbatim, with no rejection."""
        abs_path = tmp_path / "nested" / "cache.pkl"
        cache = Cachetta(path=str(abs_path))

        @cache
        def compute():
            return {"value": 42}

        result = compute()
        assert result == {"value": 42}
        assert abs_path.exists()

        # Second call reads back from the same absolute path.
        result2 = compute()
        assert result2 == {"value": 42}


# -- Atomic write safety --

def describe_atomic_writes():
    def test_failed_write_preserves_original():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "atomic.dat"
            cache = Cachetta(path=str(cache_path))

            write_cache(cache, {"version": 1})

            import _thread
            with pytest.raises((TypeError, pickle.PicklingError)):
                write_cache(cache, _thread.LockType())

            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"version": 1}

    def test_no_temp_files_left_after_failure():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "atomic.dat"
            cache = Cachetta(path=str(cache_path))

            import _thread
            with pytest.raises((TypeError, pickle.PicklingError)):
                write_cache(cache, _thread.LockType())

            remaining = list(Path(tmpdir).iterdir())
            assert len(remaining) == 0


# -- read=False, write=False combinations --

def describe_read_write_flags():
    def test_read_false_skips_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "noread.json"
            cache = Cachetta(path=str(cache_path), read=False)

            write_cache(cache, {"cached": True})

            with read_cache(cache) as result:
                pass
            assert result is None

    def test_write_false_skips_write():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "nowrite.json"
            cache = Cachetta(path=str(cache_path), write=False)

            write_cache(cache, {"data": True})
            assert not cache_path.exists()

    def test_both_false_is_noop():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "noop.json"
            cache = Cachetta(path=str(cache_path), read=False, write=False)

            call_count = 0

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return {"data": True}

            r1 = compute()
            r2 = compute()

            assert r1 == {"data": True}
            assert r2 == {"data": True}
            assert call_count == 2  # No caching occurred
            assert not cache_path.exists()


# -- Missing directory auto-creation --

def describe_auto_directory_creation():
    def test_creates_nested_directories():
        with tempfile.TemporaryDirectory() as tmpdir:
            deep_path = Path(tmpdir) / "a" / "b" / "c" / "data.json"
            cache = Cachetta(path=str(deep_path))

            write_cache(cache, {"deep": True})
            assert deep_path.exists()

    def test_creates_directories_for_function_paths():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda uid: f"{tmpdir}/users/{uid}/profile.json"
            )

            write_cache(cache, {"name": "Test"}, "user-123")
            assert (Path(tmpdir) / "users" / "user-123" / "profile.json").exists()


# -- Large data --

def describe_large_data():
    def test_handles_large_json():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "large.json"
            cache = Cachetta(path=str(cache_path))

            # ~1MB of data
            large_data = {
                "items": [
                    {"id": i, "data": "x" * 1000}
                    for i in range(1000)
                ]
            }

            write_cache(cache, large_data)

            with read_cache(cache) as result:
                pass
            assert result == large_data
            assert len(result["items"]) == 1000


# -- Exception types --

def describe_exception_types():
    def test_cache_buddy_error_is_base():
        assert issubclass(CacheCorruptError, CachettaError)


# -- Cachetta construction --

def describe_construction():
    def test_default_values():
        cache = Cachetta(path="test.json")
        assert cache.write is True
        assert cache.read is True
        assert cache.duration == timedelta(days=7)
        assert cache.condition is None
        assert cache.stale_duration is None

    def test_all_parameters():
        def cond(r):
            return r is not None
        cache = Cachetta(
            path="test.json",
            write=False,
            read=False,
            duration=timedelta(minutes=5),
            condition=cond,
            stale_duration=timedelta(minutes=10),
        )
        assert cache.write is False
        assert cache.read is False
        assert cache.duration == timedelta(minutes=5)
        assert cache.condition is cond
        assert cache.stale_duration == timedelta(minutes=10)

    def test_path_types():
        # String
        c1 = Cachetta(path="test.json")
        assert c1._get_path() == Path("test.json")

        # Path object
        c2 = Cachetta(path=Path("test.json"))
        assert c2._get_path() == Path("test.json")

        # Callable
        c3 = Cachetta(path=lambda: "test.json")
        assert c3._get_path() == Path("test.json")


# -- Conditional caching integration --

def describe_conditional_caching_integration():
    def test_condition_skips_none():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(
                path=f"{tmpdir}/cond.json",
                condition=lambda r: r is not None,
            )

            @cache
            def maybe_none(return_none):
                nonlocal call_count
                call_count += 1
                if return_none:
                    return None
                return {"data": True}

            r1 = maybe_none(True)
            assert r1 is None
            assert not (Path(tmpdir) / "cond.json").exists()

            r2 = maybe_none(False)
            assert r2 == {"data": True}


# -- Stale-while-revalidate integration --

def describe_stale_revalidate_integration():
    def test_sync_stale_returns_stale_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"version": 1}, f)

            old_time = time() - 5400  # 90 min ago
            os.utime(cache_path, (old_time, old_time))

            call_count = 0
            cache = Cachetta(
                path=str(cache_path),
                duration=timedelta(hours=1),
                stale_duration=timedelta(hours=1),
            )

            @cache
            def get_data():
                nonlocal call_count
                call_count += 1
                return {"version": 2}

            result = get_data()
            # In sync mode, stale data is returned directly
            assert result == {"version": 1}

    async def test_async_stale_triggers_background_refresh():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "stale-async.dat"
            with open(cache_path, "wb") as f:
                pickle.dump({"version": 1}, f)

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

            result = await get_data()
            assert result == {"version": 1}

            # Wait for background refresh
            await asyncio.sleep(0.1)
            assert call_count == 1

            # Verify the file was updated
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"version": 2}


# -- write_cache_ctx context manager --

def describe_write_cache_ctx_integration():
    def test_full_read_write_cycle():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "ctx.json"
            cache = Cachetta(path=str(cache_path))

            # Write via context manager
            with write_cache_ctx(cache) as writer:
                result = {"computed": True}
                writer.set(result)

            # Read it back
            with read_cache(cache) as data:
                pass
            assert data == {"computed": True}


# -- Wrap method --

def describe_wrap_integration():
    def test_wrap_caches():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/wrap.json")

            def compute():
                nonlocal call_count
                call_count += 1
                return {"wrapped": True}

            cached_compute = cache.wrap(compute)
            r1 = cached_compute()
            r2 = cached_compute()

            assert r1 == {"wrapped": True}
            assert r2 == {"wrapped": True}
            assert call_count == 1


# -- Invalidation integration --

def describe_invalidation_integration():
    def test_invalidate_then_recompute():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/inv.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return {"count": call_count}

            r1 = compute()
            assert r1 == {"count": 1}
            assert call_count == 1

            cache.invalidate()

            r2 = compute()
            assert r2 == {"count": 2}
            assert call_count == 2

    def test_invalidate_with_path_function_arg_scoped():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=lambda x: f"{tmpdir}/{x}.json")

            @cache
            def compute(x):
                nonlocal call_count
                call_count += 1
                return {"x": x}

            compute("a")
            compute("b")
            assert call_count == 2

            # With a callable path, invalidate("a") only removes the "a" file
            cache.invalidate("a")

            compute("a")  # recomputes
            compute("b")  # served from cache
            assert call_count == 3


# -- Falsy value caching --

def describe_falsy_value_caching():
    def test_caches_zero():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/zero.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return 0

            r1 = compute()
            r2 = compute()
            assert r1 == 0
            assert r2 == 0
            assert call_count == 1

    def test_caches_empty_string():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/empty_str.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return ""

            r1 = compute()
            r2 = compute()
            assert r1 == ""
            assert r2 == ""
            assert call_count == 1

    def test_caches_false():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/false.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return False

            r1 = compute()
            r2 = compute()
            assert r1 is False
            assert r2 is False
            assert call_count == 1

    def test_caches_empty_list():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/empty_list.json")

            @cache
            def compute():
                nonlocal call_count
                call_count += 1
                return []

            r1 = compute()
            r2 = compute()
            assert r1 == []
            assert r2 == []
            assert call_count == 1

# -- Condition callback edge cases --

def _raise_zero_division(_result: object) -> bool:
    """A `condition` callable that always raises, used to verify that an
    exception raised inside the condition propagates to the caller."""
    raise ZeroDivisionError("boom")


def describe_condition_edge_cases():
    def test_condition_exception_propagates():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=f"{tmpdir}/cond_err.json",
                condition=_raise_zero_division,
            )

            @cache
            def compute():
                return {"data": True}

            with pytest.raises(ZeroDivisionError):
                compute()

    async def test_async_condition_exception_propagates():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=f"{tmpdir}/cond_err_async.json",
                condition=_raise_zero_division,
            )

            @cache
            async def compute():
                return {"data": True}

            with pytest.raises(ZeroDivisionError):
                await compute()


# -- Path function edge cases --

def describe_path_function_edge_cases():
    def test_path_function_exception_propagates():
        cache = Cachetta(path=lambda: (_ for _ in ()).throw(RuntimeError("bad path")))

        @cache
        def compute():
            return {"data": True}

        with pytest.raises(RuntimeError, match="bad path"):
            compute()

    def test_path_function_returns_empty_string():
        cache = Cachetta(path=lambda: "")

        # Empty string path should produce a Path("")
        result = cache._get_path()
        assert result == Path("")


# -- write_cache_ctx exception behavior --

def describe_write_cache_ctx_exception():
    def test_exception_after_set_does_not_write():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "ctx_err.json"
            cache = Cachetta(path=str(cache_path))

            with pytest.raises(ValueError, match="deliberate"):
                with write_cache_ctx(cache) as writer:
                    writer.set({"should_not_persist": True})
                    raise ValueError("deliberate")

            assert not cache_path.exists()


# -- _created_dirs staleness --

def describe_created_dirs_staleness():
    def test_recreates_deleted_directory():
        """If a cached directory is deleted externally, write should still work."""
        from cachetta.write_cache import _created_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir) / "sub"
            cache_path = sub / "data.json"
            cache = Cachetta(path=str(cache_path))

            # First write creates the directory
            write_cache(cache, {"v": 1})
            assert cache_path.exists()

            resolved = str(sub.resolve())
            assert resolved in _created_dirs

            # Simulate external deletion
            os.remove(cache_path)
            os.rmdir(sub)
            assert not sub.exists()

            # _created_dirs still thinks it exists; the write should
            # fail because the dir is gone and we skip mkdir
            # This documents current behavior (potential staleness bug)
            with pytest.raises(FileNotFoundError):
                write_cache(cache, {"v": 2})

            # Clean up stale entry so subsequent writes work
            _created_dirs.pop(resolved, None)
            write_cache(cache, {"v": 3})
            assert cache_path.exists()


# -- Zero/negative duration --

def describe_zero_negative_duration():
    def test_zero_duration_returns_false_from_should_use_read_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "zero_dur.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(seconds=0))

            write_cache(cache, {"data": True})

            with read_cache(cache) as result:
                pass
            assert result is None

    def test_negative_duration_returns_false_from_should_use_read_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "neg_dur.json"
            cache = Cachetta(path=str(cache_path), duration=timedelta(seconds=-10))

            write_cache(cache, {"data": True})

            with read_cache(cache) as result:
                pass
            assert result is None


# -- Literal string/Path with args (post-sibling-removal semantics, issue #45) --


def describe_literal_path_with_args():
    """A str/Path passed as `path` is now treated literally: arguments to the
    wrapped function do not rewrite the filename into a `{stem}-{hash}{ext}`
    sibling. Consumers who want arg-keyed caching should use a callable `path`
    (or `.hashed` once it ships)."""

    def test_get_path_with_args_returns_literal_string_path():
        cache = Cachetta(path="cache/data.json")
        assert cache._get_path("arg1") == Path("cache/data.json")
        assert cache._get_path("arg1", "arg2") == Path("cache/data.json")
        assert cache._get_path(user="alice") == Path("cache/data.json")
        # Same path regardless of args
        assert cache._get_path("a") == cache._get_path("b")

    def test_get_path_with_args_returns_literal_path_object():
        cache = Cachetta(path=Path("cache/data.json"))
        assert cache._get_path("arg1") == Path("cache/data.json")
        assert cache._get_path("a") == cache._get_path("b")

    def test_get_path_with_args_no_extension():
        cache = Cachetta(path="cache/data")
        assert cache._get_path("arg1") == Path("cache/data")
        assert cache._get_path("a") == cache._get_path("b")

    def test_decorator_writes_literal_path_and_serves_first_value():
        """With `path=str` and args, only the literal file is written; subsequent
        calls (with any args) read that one file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=str(cache_path))

            call_count = 0

            @cache
            def compute(x):
                nonlocal call_count
                call_count += 1
                return {"x": x}

            r1 = compute("a")
            r2 = compute("b")
            r3 = compute("a")

            # Only the literal cache file exists — no `data-<hash>.json` siblings
            siblings = sorted(p.name for p in Path(tmpdir).iterdir())
            assert siblings == ["data.json"]

            # All three calls return the value the first call wrote, the
            # function body runs only once.
            assert r1 == {"x": "a"}
            assert r2 == {"x": "a"}
            assert r3 == {"x": "a"}
            assert call_count == 1

    def test_invalidate_with_args_removes_literal_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=str(cache_path))

            @cache
            def compute(x):
                return {"x": x}

            compute("a")
            assert cache_path.exists()

            # Args to invalidate should also resolve to the literal path
            cache.invalidate("anything")
            assert not cache_path.exists()


# -- `hashed=True` flag (issue #44) --

def describe_hashed_flag():
    """`Cachetta(hashed=True)` (or `@cache(hashed=True)` override) treats `path`
    as a folder and resolves arg-bearing calls to `{path}/{hash(args)}`.
    Off (`hashed=False`, the default), `path` is literal — the behavior shipped
    in #48. The flag is a regular dataclass field, so it composes through the
    constructor, `cache.copy(...)`, and the `@cache(**kwargs)` decorator
    override, with each `@cache(hashed=True)` creating an isolated copy that
    does not mutate the base cache.
    """

    def test_decorator_override_writes_per_arg_inside_path_folder():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "llm"
            cache = Cachetta(path=str(cache_dir))

            @cache(hashed=True)
            def call(prompt):
                return "response: " + prompt

            result = call("hello")
            assert result == "response: hello"

            files = list(cache_dir.iterdir())
            assert len(files) == 1
            assert files[0].parent == cache_dir
            assert files[0].suffix == ""

    def test_decorator_override_different_args_produce_different_files():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=str(cache_dir))

            @cache(hashed=True)
            def call(x):
                return x * 2

            call(1)
            call(2)
            call(3)

            files = list(cache_dir.iterdir())
            assert len(files) == 3

    def test_decorator_override_same_args_hits_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/cache")

            @cache(hashed=True)
            def call(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            r1 = call(5)
            r2 = call(5)
            assert r1 == r2 == 10
            assert call_count == 1

    def test_multiple_decorations_with_and_without_hashed_are_isolated():
        """The base `cache` instance is not mutated by `@cache(hashed=True)`;
        a follow-up `@cache` (plain) on the same base still writes literally.
        This is the critical isolation guarantee for the `__call__` + `replace()`
        copy semantics.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/literal.json")

            @cache(path=f"{tmpdir}/hashed", hashed=True)
            def hashed_fn(x):
                return x

            @cache  # uses the base cache; hashed is False
            def literal_fn():
                return "constant"

            hashed_fn("a")
            hashed_fn("b")
            literal_fn()
            literal_fn()  # cached

            # Hashed entries live as per-arg files inside the folder
            hashed_dir = Path(tmpdir) / "hashed"
            assert hashed_dir.is_dir()
            assert len(list(hashed_dir.iterdir())) == 2

            # The literal decorator wrote to the base cache's literal path
            literal_path = Path(tmpdir) / "literal.json"
            assert literal_path.is_file()

            # The base cache itself was never mutated
            assert cache.hashed is False

    def test_constructor_hashed_true_applies_to_all_entrypoints():
        """Setting `hashed=True` on the Cachetta itself (not just the decorator
        override) makes every entry point — read/write helpers, exists,
        invalidate, the decorator — hash the same way.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=str(cache_dir), hashed=True)

            write_cache(cache, {"x": 1}, "hello")

            assert cache.exists("hello") is True
            assert cache.exists("other") is False

            with read_cache(cache, "hello") as data:
                pass
            assert data == {"x": 1}

            cache.invalidate("hello")
            assert cache.exists("hello") is False

    def test_copy_preserves_and_overrides_hashed():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=f"{tmpdir}/cache", hashed=True)
            preserved = cache.copy()
            overridden = cache.copy(hashed=False)

            assert preserved.hashed is True
            assert overridden.hashed is False

    def test_callable_path_composes_with_hashed():
        """When `path` is callable and `hashed=True`, the callable is evaluated
        with the wrapped function's args to produce a folder, and the hash of
        those same args is appended as the child filename. This is the
        "shard by one arg, hash by all" pattern.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda model, prompt: f"{tmpdir}/{model}",
                hashed=True,
            )

            @cache
            def call(model, prompt):
                return f"{model}: {prompt}"

            call("gpt", "hi")
            call("gpt", "bye")
            call("claude", "hi")

            assert len(list(Path(tmpdir, "gpt").iterdir())) == 2
            assert len(list(Path(tmpdir, "claude").iterdir())) == 1

    def test_callable_path_with_hashed_through_direct_helpers():
        """`read_cache` / `write_cache` / `exists` / `invalidate` go through
        the same `_get_path` consultation as the decorator: the callable picks
        the bucket, the hash names the file. So direct helper calls and the
        decorator agree on the resolved path.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda kind, item: f"{tmpdir}/{kind}",
                hashed=True,
            )

            write_cache(cache, {"v": 1}, "users", 7)

            with read_cache(cache, "users", 7) as data:
                pass
            assert data == {"v": 1}

            assert cache.exists("users", 7) is True
            assert cache.exists("users", 8) is False

            cache.invalidate("users", 7)
            assert cache.exists("users", 7) is False

    def test_callable_path_with_hashed_isolation_across_decorations():
        """A base cache with a callable `path` can host both `@cache(hashed=True)`
        and plain `@cache` without one affecting the other.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=lambda kind, **_: f"{tmpdir}/{kind}")

            @cache(hashed=True)
            def hashed_fn(kind, *, prompt):
                return prompt

            @cache
            def literal_fn(kind):
                return "constant"

            hashed_fn("users", prompt="a")
            hashed_fn("users", prompt="b")
            literal_fn("singletons")

            # Hashed wrote two per-arg files inside {tmpdir}/users
            assert len(list(Path(tmpdir, "users").iterdir())) == 2

            # Literal wrote a single file at {tmpdir}/singletons
            assert Path(tmpdir, "singletons").is_file()

            # Base cache untouched
            assert cache.hashed is False

    def test_callable_path_returning_pathlib_path_composes_with_hashed():
        """A callable returning `Path(...)` (not just `str`) still composes:
        result of the callable is treated as the folder and the hash is appended.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda kind: Path(tmpdir) / kind,
                hashed=True,
            )

            @cache
            def call(kind):
                return f"hi {kind}"

            call("a")
            call("b")

            assert (Path(tmpdir) / "a").is_dir()
            assert (Path(tmpdir) / "b").is_dir()
            assert len(list((Path(tmpdir) / "a").iterdir())) == 1
            assert len(list((Path(tmpdir) / "b").iterdir())) == 1

    def test_condition_gates_writes_under_hashed():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(
                path=str(cache_dir),
                hashed=True,
                condition=lambda r: r is not None,
            )

            @cache
            def call(x):
                return None if x == "skip" else x

            call("skip")
            assert not cache_dir.exists() or len(list(cache_dir.iterdir())) == 0

            call("keep")
            assert len(list(cache_dir.iterdir())) == 1

    async def test_hashed_works_with_async_functions():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=str(cache_dir), hashed=True)

            call_count = 0

            @cache
            async def call(prompt):
                nonlocal call_count
                call_count += 1
                return "resp: " + prompt

            r1 = await call("hi")
            r2 = await call("hi")
            assert r1 == r2 == "resp: hi"
            assert call_count == 1

    def test_decorator_override_can_flip_hashed_off():
        """`@cache(hashed=False)` on a cache constructed with `hashed=True`
        produces a literal-mode decoration for that function only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            literal_path = Path(tmpdir) / "literal.json"
            cache = Cachetta(path=str(literal_path), hashed=True)

            @cache(hashed=False)
            def literal_fn():
                return "constant"

            literal_fn()
            assert literal_path.is_file()
            # The base cache still has hashed=True
            assert cache.hashed is True

    def test_default_hashed_is_false_for_backwards_compat():
        """Constructing without `hashed=` keeps the post-#48 literal-path
        semantic: no implicit hashing of args."""
        cache = Cachetta(path="cache/data.json")
        assert cache.hashed is False
        assert cache._get_path("a") == Path("cache/data.json")
        assert cache._get_path("a") == cache._get_path("b")

    def test_hashed_matches_public_hash_digest():
        """The filename `hashed=True` writes is exactly `cachetta.hash(*args, **kwargs)`."""
        from cachetta import hash as cachetta_hash

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=str(cache_dir), hashed=True)

            @cache
            def call(x):
                return x

            call("hello")
            expected = cache_dir / cachetta_hash("hello")
            assert expected.exists()


# -- Automatic method-receiver exclusion (issue #77) --

def describe_method_receiver_auto_skip():
    """Decorating an instance/class method excludes the receiver (self/cls)
    from the cache key automatically — no `skip_self` flag required. A free
    function's first positional argument is a genuine input and is kept.
    """

    def test_self_excluded_from_hashed_key_across_instances():
        # Two instances calling the method with equal args must share one
        # cache file and compute exactly once: the receiver must not enter
        # the key.
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            calls = []

            cache = Cachetta(path=str(cache_dir), hashed=True)

            class Service:
                @cache
                def call(self, prompt):
                    calls.append(prompt)
                    return prompt.upper()

            s1 = Service()
            s2 = Service()
            assert s1.call("hello") == "HELLO"
            assert s2.call("hello") == "HELLO"
            assert len(list(cache_dir.iterdir())) == 1
            assert calls == ["hello"]

    def test_callable_path_receives_only_real_args():
        # The path callable models the method's real signature (no `self`);
        # the receiver must be stripped before the path is resolved.
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=lambda name: f"{tmpdir}/{name}.json")

            class Service:
                @cache
                def get_data(self, name):
                    return {"name": name}

            svc = Service()
            assert svc.get_data("test") == {"name": "test"}
            assert (Path(tmpdir) / "test.json").exists()

    def test_plain_function_keeps_first_positional_arg_in_key():
        # Guard against over-stripping: a free function's first arg is a real
        # input, so distinct values must produce distinct cache files.
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            calls = []

            cache = Cachetta(path=str(cache_dir), hashed=True)

            @cache
            def compute(x):
                calls.append(x)
                return x * 2

            assert compute(1) == 2
            assert compute(2) == 4
            assert len(list(cache_dir.iterdir())) == 2
            assert calls == [1, 2]
