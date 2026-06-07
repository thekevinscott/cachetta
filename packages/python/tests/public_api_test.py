"""Black-box tests for the public ``cachetta`` API surface.

These tests treat the package as a black box: they import only from
``cachetta`` (no internal modules, no private attributes), exercise the
public API, and assert against observable behavior such as files
written to disk.
"""

import tempfile
from pathlib import Path

from cachetta import Cachetta, hash


def describe_hash_export():
    """The public ``hash`` export returns a stable digest consumers can
    use to build custom ``path=`` callables or external indexes — the
    same hasher cachetta used to embed into the auto-keyed sibling path
    before issue #45 removed that implicit behavior.
    """

    def test_digest_drives_user_built_keyed_file_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            @Cachetta(path=lambda *a: f"{tmpdir}/data-{hash(*a)}.json")
            def fn(a, b):
                return {"a": a, "b": b}

            fn("x", "y")

            digest = hash("x", "y")
            expected = Path(tmpdir) / f"data-{digest}.json"
            assert expected.exists(), (
                "Expected the cache file to be written at %s; tmpdir contains %s"
                % (expected, list(Path(tmpdir).iterdir()))
            )

    def test_digest_drives_user_built_keyed_path_with_kwargs():
        with tempfile.TemporaryDirectory() as tmpdir:
            @Cachetta(path=lambda *a, **kw: f"{tmpdir}/data-{hash(*a, **kw)}.json")
            def fn(a, *, flag):
                return (a, flag)

            fn("a", flag=True)

            digest = hash("a", flag=True)
            assert (Path(tmpdir) / f"data-{digest}.json").exists()

    def test_digest_drives_user_built_subdirectory_layout():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"

            @Cachetta(path=lambda *a: cache_dir / hash(*a))
            def fn(k):
                return k

            fn("k")

            digest = hash("k")
            assert (cache_dir / digest).exists()
