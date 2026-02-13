import pytest
from pathlib import Path
from cachetta.utils.get_extension import get_extension
from cachetta.exceptions import InvalidPathError

def describe_get_extension():
    def test_it_works_with_a_str():
        assert get_extension('foo/bar/baz.pkl') == 'pkl'

    def test_it_works_with_a_path():
        assert get_extension(Path('foo/bar/baz.pkl')) == 'pkl'

    def test_it_works_with_multiple_dots():
        assert get_extension('foo.bar.baz.pkl') == 'pkl'

    def test_it_raises_if_missing_extension_with_str():
        with pytest.raises(InvalidPathError):
            get_extension('foo/bar/baz')

    def test_it_raises_if_missing_extension_with_path():
        with pytest.raises(InvalidPathError):
            get_extension(Path('foo/bar/baz'))

    def test_it_returns_extension_of_simple_file():
        assert get_extension('test.txt') == 'txt'

    def test_it_returns_extension_of_file_with_multiple_dots():
        assert get_extension('test.min.js') == 'js'
        assert get_extension('config.prod.json') == 'json'

    def test_it_returns_extension_of_file_with_path():
        assert get_extension('/path/to/file.json') == 'json'
        assert get_extension('./cache/data.pkl') == 'pkl'
        assert get_extension('../config/settings.yaml') == 'yaml'

    def test_it_returns_extension_of_file_with_complex_path():
        assert get_extension('/home/user/projects/cache/data.json') == 'json'
        assert get_extension('C:\\Users\\username\\Documents\\file.txt') == 'txt'

    def test_it_handles_different_file_extensions():
        assert get_extension('data.json') == 'json'
        assert get_extension('data.pkl') == 'pkl'
        assert get_extension('data.yaml') == 'yaml'
        assert get_extension('data.yml') == 'yml'
        assert get_extension('data.xml') == 'xml'
        assert get_extension('data.csv') == 'csv'



    def test_it_raises_error_for_empty_string():
        with pytest.raises(InvalidPathError):
            get_extension('')
