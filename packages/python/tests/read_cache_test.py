import json
from unittest.mock import patch, Mock
import pytest
from pathlib import Path
import tempfile
from cachetta.cachetta import Cachetta
from cachetta.exceptions import UnsupportedFormatError
from cachetta.read_cache import read_cache


@pytest.fixture(autouse=True)
def mock_should_use_read_cache():
    with patch("cachetta.utils.should_use_read_cache.should_use_read_cache", new_callable=Mock) as mock:
        mock.return_value = True
        yield mock


@pytest.fixture(autouse=True)
def mock_get_extension():
    with patch("cachetta.utils.get_extension.get_extension", new_callable=Mock) as mock:
        mock.return_value = "mock-extension"
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

    def test_it_yields_json(mock_should_use_read_cache, mock_get_extension):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "file.json"
            data = {
                "foo": "bar",
            }
            with open(temp_file, "w") as f:
                f.write(json.dumps(data))
            mock_get_extension.return_value = "json"
            mock_should_use_read_cache.return_value = True
            with read_cache(MockCache(path=temp_file)) as d:
                pass
            assert d == data

    def test_it_returns_none_for_corrupt_data(
        mock_should_use_read_cache, mock_get_extension
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "file.json"
            data = "foobar"
            with open(temp_file, "w") as f:
                f.write(data)
            mock_get_extension.return_value = "json"
            mock_should_use_read_cache.return_value = True
            with read_cache(MockCache(path=temp_file)) as f:
                pass
            assert f is None

    def test_it_raises_if_given_unexpected_exception(mock_get_extension, mock_should_use_read_cache):
        ext = "foo"
        mock_get_extension.return_value = ext
        mock_should_use_read_cache.return_value = True
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / f"file.{ext}"
            temp_file.touch()  # Create the file so it exists
            with pytest.raises(UnsupportedFormatError, match=f"Unknown extension: {ext}"):
                with read_cache(MockCache(path=temp_file)):
                    pass

    def test_it_handles_function_based_cache_paths(mock_should_use_read_cache, mock_get_extension):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "dynamic-cache.json"
            data = {"dynamic": True}

            with open(temp_file, "w") as f:
                f.write(json.dumps(data))

            mock_get_extension.return_value = "json"
            mock_should_use_read_cache.return_value = True

            def path_fn(id):
                return temp_file

            with read_cache(MockCache(path=path_fn), "test-id") as d:
                pass
            assert d == data

    def test_it_handles_complex_nested_objects(mock_should_use_read_cache, mock_get_extension):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "complex.json"
            complex_data = {
                "string": "hello",
                "number": 123,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "object": {"nested": {"deep": True}}
            }

            with open(temp_file, "w") as f:
                f.write(json.dumps(complex_data))

            mock_get_extension.return_value = "json"
            mock_should_use_read_cache.return_value = True

            with read_cache(MockCache(path=temp_file)) as d:
                pass
            assert d == complex_data
            assert d["array"] == [1, 2, 3]
            assert d["object"]["nested"]["deep"] is True

    def test_it_returns_null_for_unknown_extension_when_cache_should_not_be_used(mock_get_extension, mock_should_use_read_cache):
        mock_get_extension.return_value = "unknown"
        mock_should_use_read_cache.return_value = False  # Cache should not be used

        with read_cache(MockCache(path="test.unknown")) as d:
            pass
        assert d is None
