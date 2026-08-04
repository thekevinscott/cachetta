"""Integration tests for clear as an expiry-aware sweep (issue #110)."""

import os
import tempfile
from datetime import timedelta
from pathlib import Path
from time import time

from cachetta import Cachetta, read_cache, write_cache

HOUR = timedelta(hours=1)


def backdate(path: str | Path, hours: float) -> None:
    old_time = time() - hours * 3600
    os.utime(path, (old_time, old_time))


def describe_folder_sweep_without_force():
    def test_deletes_dead_entries_keeps_fresh_and_returns_nothing():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=cache_dir, hashed=True, duration=HOUR)

            write_cache(cache, {"v": 1}, "fresh")
            write_cache(cache, {"v": 2}, "old_a")
            write_cache(cache, {"v": 3}, "old_b")
            backdate(cache._get_path("old_a"), 2)
            backdate(cache._get_path("old_b"), 3)

            assert cache.clear() is None

            assert len(list(cache_dir.iterdir())) == 1
            assert cache.exists("fresh")
            assert not cache.exists("old_a")
            assert not cache.exists("old_b")

    def test_keeps_entries_inside_the_stale_while_revalidate_window():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(
                path=cache_dir,
                hashed=True,
                duration=HOUR,
                stale_duration=HOUR,
            )

            write_cache(cache, {"v": 1}, "fresh")
            write_cache(cache, {"v": 2}, "stale")
            write_cache(cache, {"v": 3}, "dead")
            # Expired but within duration + stale_duration: still servable
            # via stale-while-revalidate.
            backdate(cache._get_path("stale"), 1.5)
            # Past duration + stale_duration: never servable again.
            backdate(cache._get_path("dead"), 2.5)

            cache.clear()

            assert cache.exists("fresh")
            assert cache.exists("stale")
            assert not cache.exists("dead")

    def test_recurses_into_subfolders_and_leaves_directories_in_place():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=cache_dir, duration=HOUR)

            nested_dir = cache_dir / "nested"
            nested_dir.mkdir(parents=True)
            nested_file = nested_dir / "entry.json"
            nested_file.write_text('{"v": 1}')
            backdate(nested_file, 2)

            cache.clear()

            assert not nested_file.exists()
            # The (now empty) subfolder still exists.
            assert nested_dir.is_dir()


def describe_force_override():
    def test_removes_the_folder_wholesale_regardless_of_freshness():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=cache_dir, hashed=True, duration=HOUR)

            write_cache(cache, {"v": 1}, "fresh")
            write_cache(cache, {"v": 2}, "old")
            backdate(cache._get_path("old"), 2)

            assert cache.clear(force=True) is None

            assert not cache_dir.exists()
            assert not cache.exists("fresh")
            assert not cache.exists("old")

    def test_deletes_a_fresh_single_file_cache():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=cache_path, duration=HOUR)

            write_cache(cache, {"v": 1})

            cache.clear(force=True)

            assert not cache.exists()

    def test_writes_recreate_the_folder_after_a_forced_clear():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=cache_dir, hashed=True, duration=HOUR)

            write_cache(cache, {"v": 1}, "entry")
            cache.clear(force=True)
            write_cache(cache, {"v": 2}, "entry")

            with read_cache(cache, "entry") as result:
                pass
            assert result == {"v": 2}


def describe_single_file_cache_without_force():
    def test_deletes_the_file_when_it_is_no_longer_servable():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=cache_path, duration=HOUR)

            write_cache(cache, {"v": 1})
            backdate(cache_path, 2)

            cache.clear()

            assert not cache.exists()

    def test_keeps_the_file_while_it_is_fresh():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"
            cache = Cachetta(path=cache_path, duration=HOUR)

            write_cache(cache, {"v": 1})

            cache.clear()

            assert cache.exists()


def describe_path_resolution_parity_with_other_methods():
    def test_resolves_callable_paths_with_the_given_args():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(
                path=lambda model: Path(tmpdir) / model,
                hashed=True,
                duration=HOUR,
            )

            write_cache(cache, {"v": 1}, "gpt")
            write_cache(cache, {"v": 2}, "claude")

            # Both entries are fresh; force-clear only the 'gpt' entry.
            cache.clear("gpt", force=True)

            assert not cache.exists("gpt")
            assert cache.exists("claude")


def describe_missing_path():
    def test_is_a_no_op():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=Path(tmpdir) / "nope", duration=HOUR)
            assert cache.clear() is None
            assert cache.clear(force=True) is None


def describe_aclear():
    async def test_mirrors_clear_including_force():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache = Cachetta(path=cache_dir, hashed=True, duration=HOUR)

            write_cache(cache, {"v": 1}, "fresh")
            write_cache(cache, {"v": 2}, "old")
            backdate(cache._get_path("old"), 2)

            assert await cache.aclear() is None
            assert cache.exists("fresh")
            assert not cache.exists("old")

            assert await cache.aclear(force=True) is None
            assert not cache_dir.exists()

    async def test_is_a_no_op_on_a_missing_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cachetta(path=Path(tmpdir) / "nope", duration=HOUR)
            assert await cache.aclear() is None
