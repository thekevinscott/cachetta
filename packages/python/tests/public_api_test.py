"""Black-box tests for the public ``cachetta`` API surface.

These tests treat the package as a black box: they import only from
``cachetta`` (no internal modules, no private attributes), exercise the
public API, and assert against observable behavior such as files
written to disk.
"""

import tempfile
from pathlib import Path

import pytest

from cachetta import Cachetta, hash

pytestmark = pytest.mark.integration


def describe_hash_export():
    """The public ``hash`` export returns the same digest cachetta
    embeds into the auto-keyed cache path, so consumers can build
    custom paths or external indexes that line up with cachetta's own
    keying without re-implementing the hasher.
    """

    def test_digest_matches_auto_keyed_file_written_to_disk():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"

            @Cachetta(path=str(cache_path))
            def fn(a, b):
                return {"a": a, "b": b}

            fn("x", "y")

            digest = hash("x", "y")
            expected = Path(tmpdir) / f"data-{digest}.json"
            assert expected.exists(), (
                "Expected the cache file to be written at %s; tmpdir contains %s"
                % (expected, list(Path(tmpdir).iterdir()))
            )

    def test_digest_matches_when_keyword_args_are_used():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "data.json"

            @Cachetta(path=str(cache_path))
            def fn(a, *, flag):
                return (a, flag)

            fn("a", flag=True)

            digest = hash("a", flag=True)
            assert (Path(tmpdir) / f"data-{digest}.json").exists()

    def test_digest_matches_for_extensionless_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"

            @Cachetta(path=str(cache_dir))
            def fn(k):
                return k

            fn("k")

            digest = hash("k")
            assert (cache_dir / digest).exists()
