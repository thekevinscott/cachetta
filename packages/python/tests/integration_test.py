"""Comprehensive integration tests using real file I/O, no mocks for core paths."""

import asyncio
import os
import pickle
import tempfile
from datetime import timedelta
from pathlib import Path
from time import time
from cachetta._sentinel import _LRU_MISS

import pytest

from cachetta import (
    Cachetta,
    CachettaError,
    CacheCorruptError,
    InvalidPathError,
    read_cache,
    write_cache,
    write_cache_ctx,
)
from cachetta.utils.cache_fn import _in_flight

# Everything in this module is the integration suite. The coverage gate
# measures the unit suite only (`pytest -m "not integration"`), so these
# end-to-end tests are deliberately excluded from coverage accounting.
pytestmark = pytest.mark.integration


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

    def test_decorator_with_args_and_auto_key():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/data.json")

            @cache
            def compute(x):
                nonlocal call_count
                call_count += 1
                return {"x": x}

            r1 = compute("a")
            r2 = compute("b")
            r3 = compute("a")  # should use cache

            assert r1 == {"x": "a"}
            assert r2 == {"x": "b"}
            assert r3 == {"x": "a"}
            assert call_count == 2

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

    def test_slash_string_descends_into_subdirectory_for_auto_hashed_entries():
        """`cache / 'sub'` should produce entries inside base/sub/, not as
        base/sub-{hash} siblings, when the cache is used with auto-hashing args.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=tmpdir) / "llm-calls"

            @cache
            def compute(x):
                return {"x": x}

            compute("a")

            sub_dir = Path(tmpdir) / "llm-calls"
            assert sub_dir.is_dir(), (
                "Expected '%s' to be a directory containing the cached entry, "
                "not a sibling file." % sub_dir
            )
            entries = list(sub_dir.iterdir())
            assert len(entries) == 1, (
                "Expected exactly one cache file inside the subdirectory, "
                "got: %s" % entries
            )

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

    def test_slash_callable_rejects_path_traversal():
        """Callable returning a `..`-traversing path should raise InvalidPathError."""
        cache = Cachetta(path="base") / (lambda: "../escape/file.pkl")
        with pytest.raises(InvalidPathError, match="Path traversal"):
            cache._get_path()

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

    def test_copy_preserves_lru():
        original = Cachetta(path="test.json", lru_size=10)
        copied = original.copy(write=False)
        assert copied.lru_size == 10
        # Copy should get its own LRU
        assert copied._lru is not None


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


# -- Path traversal rejection --

def describe_path_traversal():
    def test_rejects_dotdot_in_string_path():
        cache = Cachetta(path="foo/../../../etc/passwd")
        with pytest.raises(InvalidPathError, match="Path traversal"):
            cache._get_path()

    def test_rejects_dotdot_in_function_path():
        cache = Cachetta(path=lambda: "../../../etc/passwd")
        with pytest.raises(InvalidPathError, match="Path traversal"):
            cache._get_path()

    def test_rejects_dotdot_in_path_object():
        cache = Cachetta(path=Path("foo/../../bar"))
        with pytest.raises(InvalidPathError, match="Path traversal"):
            cache._get_path()

    def test_allows_path_with_dots_in_filename():
        cache = Cachetta(path="foo/bar.baz.json")
        result = cache._get_path()
        assert result == Path("foo/bar.baz.json")


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


# -- LRU cache behavior --

def describe_lru_integration():
    def test_lru_serves_from_memory():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "lru.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            write_cache(cache, {"data": "original"})

            # Now corrupt the file on disk
            cache_path.write_text("corrupted!!!")

            # LRU should still return the original data
            with read_cache(cache) as result:
                pass
            assert result == {"data": "original"}

    def test_lru_ttl_expiry():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "lru-ttl.json"
            cache = Cachetta(
                path=str(cache_path),
                lru_size=10,
                duration=timedelta(seconds=0),  # Immediately expire
            )

            cache._lru_set(str(cache_path), {"old": True})
            # Should be expired immediately
            assert cache._lru_get(str(cache_path)) is _LRU_MISS

    def test_lru_eviction():
        cache = Cachetta(path="test.json", lru_size=3)
        for i in range(5):
            cache._lru_set(f"key{i}", f"value{i}")

        # Only the last 3 should remain
        assert cache._lru_get("key0") is _LRU_MISS
        assert cache._lru_get("key1") is _LRU_MISS
        assert cache._lru_get("key2") is not _LRU_MISS
        assert cache._lru_get("key3") is not _LRU_MISS
        assert cache._lru_get("key4") is not _LRU_MISS


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
        assert issubclass(InvalidPathError, CachettaError)


# -- Cachetta construction --

def describe_construction():
    def test_default_values():
        cache = Cachetta(path="test.json")
        assert cache.write is True
        assert cache.read is True
        assert cache.duration == timedelta(days=7)
        assert cache.lru_size is None
        assert cache.condition is None
        assert cache.stale_duration is None
        assert cache.skip_self is False
        assert cache._lru is None

    def test_all_parameters():
        def cond(r):
            return r is not None
        cache = Cachetta(
            path="test.json",
            write=False,
            read=False,
            duration=timedelta(minutes=5),
            lru_size=50,
            condition=cond,
            stale_duration=timedelta(minutes=10),
            skip_self=True,
        )
        assert cache.write is False
        assert cache.read is False
        assert cache.duration == timedelta(minutes=5)
        assert cache.lru_size == 50
        assert cache.condition is cond
        assert cache.stale_duration == timedelta(minutes=10)
        assert cache.skip_self is True
        assert cache._lru is not None

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

    def test_invalidate_with_auto_key():
        with tempfile.TemporaryDirectory() as tmpdir:
            call_count = 0
            cache = Cachetta(path=f"{tmpdir}/data.json")

            @cache
            def compute(x):
                nonlocal call_count
                call_count += 1
                return {"x": x}

            compute("a")
            compute("b")
            assert call_count == 2

            # Invalidate only "a"
            cache.invalidate("a")

            compute("a")  # Should recompute
            compute("b")  # Should use cache
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

    def test_caches_none_via_lru():
        """None cached in LRU should be distinguishable from LRU miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "none_lru.json"
            cache = Cachetta(path=str(cache_path), lru_size=10)

            # Manually set None in LRU
            cache._lru_set(str(cache_path), None)
            result = cache._lru_get(str(cache_path))
            assert result is None  # Should be actual None, not _LRU_MISS


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
