import json
import pytest
from pathlib import Path
import tempfile
from cachetta.cachetta import Cachetta
from cachetta.exceptions import UnsupportedFormatError
from cachetta.write_cache import write_cache
from unittest.mock import patch, Mock


@pytest.fixture(autouse=True)
def mock_get_extension():
    with patch("cachetta.utils.get_extension.get_extension", new_callable=Mock) as mock:
        mock.return_value = "mock-extension"
        yield mock


class MockCache(Cachetta):
    pass


def describe_write_cache():
    def test_it_skips_writing_if_no_cache_is_provided():
        # Should not raise or write anything
        write_cache(None, None)

    def test_it_writes_json(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "foo.json"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {"key": "value"})

            assert cache_path.exists()
            with open(cache_path) as f:
                assert json.load(f) == {"key": "value"}

    def test_it_raises_with_unknown_extension(mock_get_extension):
        ext = "foo"
        mock_get_extension.return_value = ext
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / f"foobar.{ext}"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            with pytest.raises(
                UnsupportedFormatError, match=f"Unknown extension for file: {cache_path}"
            ):
                write_cache(cache, {"key": "value"})

    def test_it_creates_directory_structure_if_it_does_not_exist(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "nested" / "deep" / "test.json"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {"nested": True})

            assert cache_path.exists()
            with open(cache_path) as f:
                assert json.load(f) == {"nested": True}

    def test_it_handles_function_based_cache_paths(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            def path_fn(id):
                return f"{tmpdir}/path/to/{id}.json"

            cache = MockCache(path=path_fn)
            cache.write = True

            write_cache(cache, {"dynamic": True}, "dynamic")

            result_path = Path(tmpdir) / "path" / "to" / "dynamic.json"
            assert result_path.exists()
            with open(result_path) as f:
                assert json.load(f) == {"dynamic": True}

    def test_it_handles_complex_nested_objects(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "complex.json"
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
            with open(cache_path) as f:
                assert json.load(f) == complex_data

    def test_it_handles_empty_data(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "empty.json"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, {})

            with open(cache_path) as f:
                assert f.read() == "{}"

    def test_it_handles_none_data(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "none.json"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            write_cache(cache, None)

            with open(cache_path) as f:
                assert f.read() == "null"

    def test_atomic_write_does_not_leave_partial_file(mock_get_extension):
        mock_get_extension.return_value = "json"
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "atomic.json"
            cache = MockCache(path=str(cache_path))
            cache.write = True

            # Write initial data
            write_cache(cache, {"version": 1})

            # Force json.dumps to fail by passing a non-serializable object
            class BadObj:
                pass

            with pytest.raises(TypeError):
                write_cache(cache, BadObj())

            # Original file should still be intact
            with open(cache_path) as f:
                assert json.load(f) == {"version": 1}
