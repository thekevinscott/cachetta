from datetime import datetime
import tempfile
from cachetta.utils.get_last_updated import get_last_updated


def describe_get_last_updated():
    def test_it_returns_none_if_file_does_not_exist():
        assert get_last_updated("foo") is None

    def test_it_returns_last_updated_if_it_exists():
        with tempfile.NamedTemporaryFile() as f:
            last_updated = get_last_updated(f.name)
            assert type(last_updated) is float
            diff = abs(last_updated - datetime.now().timestamp())
            assert diff < 0.01

    def test_it_returns_timestamp_for_existing_file():
        with tempfile.NamedTemporaryFile() as f:
            timestamp = get_last_updated(f.name)
            assert timestamp is not None
            assert isinstance(timestamp, float)
            assert timestamp > 0

    def test_it_returns_none_for_nonexistent_file():
        result = get_last_updated("nonexistent_file.txt")
        assert result is None

    def test_it_returns_none_for_directory():
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_last_updated(temp_dir)
            assert result is not None
            assert isinstance(result, float)

    def test_it_handles_path_with_spaces():
        with tempfile.NamedTemporaryFile(suffix=" test file.txt") as f:
            timestamp = get_last_updated(f.name)
            assert timestamp is not None
            assert isinstance(timestamp, float)
