import os
import tempfile
from pathlib import Path

from .clear_path import clear_path


def always(_mtime: float) -> bool:
    return True


def never(_mtime: float) -> bool:
    return False


def describe_clear_path():
    def test_returns_empty_for_missing_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            assert clear_path(Path(tmpdir) / "nope", always) == []

    def test_deletes_a_file_when_should_clear_returns_true():
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "a"
            file.write_text("x")
            assert clear_path(file, always) == [file]
            assert not file.exists()

    def test_keeps_a_file_when_should_clear_returns_false():
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "a"
            file.write_text("x")
            assert clear_path(file, never) == []
            assert file.exists()

    def test_passes_the_file_mtime_to_should_clear():
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "a"
            file.write_text("x")
            old_time = 1_000_000_000.0
            os.utime(file, (old_time, old_time))
            seen: list[float] = []

            def record(mtime: float) -> bool:
                seen.append(mtime)
                return False

            clear_path(file, record)
            assert seen == [old_time]

    def test_walks_directories_recursively_keeping_directories():
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "sub"
            sub.mkdir()
            (root / "a").write_text("x")
            (sub / "b").write_text("x")

            deleted = clear_path(root, always)

            assert sorted(deleted) == sorted([root / "a", sub / "b"])
            assert sub.is_dir()

    def test_treats_a_file_vanishing_between_stat_and_unlink_as_not_deleted():
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "a"
            file.write_text("x")

            # should_clear runs between stat and unlink - deleting the file
            # here reproduces the race deterministically.
            def vanish(_mtime: float) -> bool:
                os.unlink(file)
                return True

            assert clear_path(file, vanish) == []
