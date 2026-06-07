"""Integration tests verifying nested docs ship in built artifacts.

Tracks issue #56: the JS sync script and the Python `package-data` glob both
treat `docs/` as flat, so anything under `docs/<subdir>/` is silently dropped
from the npm tarball and the Python wheel. These tests use the committed
`docs/_test/nested.md` fixture as the canary.
"""

import shutil
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PKG_DIR = REPO_ROOT / "packages" / "python"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync-docs.sh"
FIXTURE_REL = Path("docs/_test/nested.md")


def _sync() -> None:
    subprocess.run(["bash", str(SYNC_SCRIPT)], check=True)


def describe_nested_docs_packaging():
    def test_fixture_is_committed():
        assert (REPO_ROOT / FIXTURE_REL).exists(), (
            f"Expected fixture at {REPO_ROOT / FIXTURE_REL}. The tests below "
            "cannot run without it."
        )

    def test_sync_script_preserves_subdirectory_structure():
        _sync()
        for dst in (
            "packages/javascript/docs/_test/nested.md",
            "packages/python/docs/_test/nested.md",
            "packages/python/src/cachetta/docs/_test/nested.md",
        ):
            assert (REPO_ROOT / dst).exists(), (
                f"Expected nested fixture at {dst} after sync-docs.sh; "
                "the sync script must recurse, not iterate `*.md` flatly."
            )

    def test_wheel_includes_nested_docs():
        _sync()
        dist = PKG_DIR / "dist"
        if dist.exists():
            shutil.rmtree(dist)

        subprocess.run(
            ["uv", "build", "--wheel"],
            cwd=str(PKG_DIR),
            check=True,
        )

        wheels = sorted(dist.glob("*.whl"))
        assert wheels, f"No wheel produced in {dist}"

        with zipfile.ZipFile(wheels[-1]) as zf:
            names = zf.namelist()

        docs_entries = [n for n in names if "/docs/" in n]
        nested = [n for n in names if n.endswith("_test/nested.md")]
        assert nested, (
            "Expected nested docs in wheel, but none were packaged. "
            f"Wheel docs entries: {docs_entries}"
        )

    def test_sdist_includes_nested_docs():
        _sync()
        dist = PKG_DIR / "dist"
        if dist.exists():
            shutil.rmtree(dist)

        subprocess.run(
            ["uv", "build", "--sdist"],
            cwd=str(PKG_DIR),
            check=True,
        )

        sdists = sorted(dist.glob("*.tar.gz"))
        assert sdists, f"No sdist produced in {dist}"

        import tarfile

        with tarfile.open(sdists[-1], "r:gz") as tf:
            names = tf.getnames()

        nested = [n for n in names if n.endswith("_test/nested.md")]
        assert nested, (
            "Expected nested docs in sdist. Entries containing 'docs/': "
            f"{[n for n in names if '/docs/' in n]}"
        )
