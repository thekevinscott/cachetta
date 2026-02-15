import pickle
from unittest.mock import patch, Mock
import pytest
from pathlib import Path
import tempfile
from cachetta.cachetta import Cachetta
from cachetta.read_cache import read_cache


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
