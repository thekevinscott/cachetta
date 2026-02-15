import pickle
import pytest
from pathlib import Path
import tempfile
from cachetta.cachetta import Cachetta
from cachetta.write_cache import write_cache


class MockCache(Cachetta):
    pass


def describe_write_cache():
    def test_it_skips_writing_if_no_cache_is_provided():
        # Should not raise or write anything
        write_cache(None, None)

    def test_it_writes_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "foo.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {"key": "value"})

            assert cache_path.exists()
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"key": "value"}

    def test_it_writes_any_file_extension():
        for ext in [".json", ".dat", ".cache", ".xml", ".foo"]:
            with tempfile.TemporaryDirectory() as tmpdir:
                cache_path = Path(tmpdir) / f"data{ext}"
                cache = MockCache(path=str(cache_path))
                cache.write = True

                write_cache(cache, {"ext": ext})

                assert cache_path.exists()
                with open(cache_path, "rb") as f:
                    assert pickle.load(f) == {"ext": ext}

    def test_it_creates_directory_structure_if_it_does_not_exist():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "nested" / "deep" / "test.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {"nested": True})

            assert cache_path.exists()
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"nested": True}

    def test_it_handles_function_based_cache_paths():
        with tempfile.TemporaryDirectory() as tmpdir:
            def path_fn(id):
                return f"{tmpdir}/path/to/{id}.dat"

            cache = MockCache(path=path_fn)
            cache.write = True

            write_cache(cache, {"dynamic": True}, "dynamic")

            result_path = Path(tmpdir) / "path" / "to" / "dynamic.dat"
            assert result_path.exists()
            with open(result_path, "rb") as f:
                assert pickle.load(f) == {"dynamic": True}

    def test_it_handles_complex_nested_objects():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "complex.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            complex_data = {
                "string": "hello",
                "number": 123,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "object": {"nested": {"deep": True}}
            }

            write_cache(cache, complex_data)

            assert cache_path.exists()
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == complex_data

    def test_it_handles_empty_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "empty.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {})

            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {}

    def test_it_handles_none_data():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "none.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, None)

            with open(cache_path, "rb") as f:
                assert pickle.load(f) is None

    def test_it_handles_complex_python_types():
        """Pickle can handle types that JSON cannot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "complex.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            data = {
                "set": {1, 2, 3},
                "tuple": (1, 2, 3),
                "bytes": b"hello",
            }

            write_cache(cache, data)

            with open(cache_path, "rb") as f:
                loaded = pickle.load(f)
            assert loaded["set"] == {1, 2, 3}
            assert loaded["tuple"] == (1, 2, 3)
            assert loaded["bytes"] == b"hello"

    def test_atomic_write_does_not_leave_partial_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "atomic.dat"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            # Write initial data
            write_cache(cache, {"version": 1})

            # Force pickle.dump to fail by passing a non-picklable object
            import _thread
            with pytest.raises((TypeError, pickle.PicklingError)):
                write_cache(cache, _thread.LockType())

            # Original file should still be intact
            with open(cache_path, "rb") as f:
                assert pickle.load(f) == {"version": 1}
