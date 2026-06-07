"""flake8 plugin: unit tests must mock their cross-module collaborators.

A unit test (``<name>_test.py``) should exercise one module in isolation. Every
test file is either a *unit* test (checked here) or an *integration* test
(marked ``pytestmark = pytest.mark.integration`` and skipped) -- there is no
third category.

For a unit test, this plugin requires:

* it targets exactly one source module, colocated by the ``<name>_test.py`` <->
  ``<name>.py`` convention (else ``MIS002``: rename it or mark it integration);
  and
* every top-level first-party import is the module under test, a pure value
  module (``<pkg>.exceptions`` / ``<pkg>._sentinel``), or mocked (else
  ``MIS001``).

In Python the idiom for isolating a unit is to ``patch(...)`` the collaborator
on the *consumer* module rather than importing it, so a real first-party
collaborator imported at module scope is the smell. To use a real collaborator
on purpose, add an inline ``# mock-enforce-ignore: <reason>`` comment (the
reason is required) or a standard ``# noqa: MIS001``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterator

# Pure value modules: constants and error classes, nothing behavioral to mock.
PURE_VALUE_SUFFIXES = ("exceptions", "_sentinel")

WAIVER = re.compile(r"mock-enforce-ignore:\s*\S")

MIS001 = (
    "MIS001 imports real cross-module collaborator '{module}'; patch it on the "
    "consumer module, or add '# mock-enforce-ignore: <reason>' if intentional"
)
MIS002 = (
    "MIS002 unit test maps to no source module; rename to '<module>_test.py' to "
    "target one module, or mark `pytestmark = pytest.mark.integration`"
)


def _roots(file_path: Path) -> tuple[Path, Path, str] | None:
    """Find ``(tests_dir, package_dir, package_name)`` for a test file by walking
    up to a directory that has both ``tests/`` and a single ``src/<pkg>/``."""
    for parent in file_path.parents:
        src = parent / "src"
        tests = parent / "tests"
        if not (src.is_dir() and tests.is_dir()):
            continue
        pkgs = [d for d in src.iterdir() if (d / "__init__.py").is_file()]
        if len(pkgs) == 1:
            return tests, pkgs[0], pkgs[0].name
    return None


def _is_integration(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            continue
        value = node.value
        marks = value.elts if isinstance(value, ast.List) else [value]
        for mark in marks:
            if isinstance(mark, ast.Attribute) and mark.attr == "integration":
                return True
    return False


def _module_under_test(path: Path, tests_dir: Path, pkg_dir: Path, pkg: str) -> str | None:
    rel = path.relative_to(tests_dir).with_suffix("")
    name = rel.name[: -len("_test")]
    parts = [*rel.parts[:-1], name]
    if not pkg_dir.joinpath(*parts).with_suffix(".py").exists():
        return None
    return ".".join([pkg, *parts])


def _first_party_imports(tree: ast.Module, pkg: str) -> list[tuple[str, int, int]]:
    found: list[tuple[str, int, int]] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            if node.module == pkg or node.module.startswith(pkg + "."):
                found.append((node.module, node.lineno, node.col_offset))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == pkg or alias.name.startswith(pkg + "."):
                    found.append((alias.name, node.lineno, node.col_offset))
    return found


class MockIsolationPlugin:
    name = "flake8-mock-isolation"
    version = "0.1.0"

    def __init__(self, tree: ast.Module, filename: str) -> None:
        self._tree = tree
        self._filename = filename

    def run(self) -> Iterator[tuple[int, int, str, type]]:
        path = Path(self._filename)
        if path.name == "-" or not path.name.endswith("_test.py"):
            return
        if _is_integration(self._tree):
            return
        roots = _roots(path)
        if roots is None:
            return
        tests_dir, pkg_dir, pkg = roots

        module_under_test = _module_under_test(path, tests_dir, pkg_dir, pkg)
        if module_under_test is None:
            yield (1, 0, MIS002, type(self))
            return

        try:
            lines = path.read_text().splitlines()
        except OSError:
            lines = []
        pure = {f"{pkg}.{suffix}" for suffix in PURE_VALUE_SUFFIXES}

        for module, lineno, col in _first_party_imports(self._tree, pkg):
            if module == module_under_test or module in pure:
                continue
            on_line = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
            above = lines[lineno - 2] if 0 <= lineno - 2 < len(lines) else ""
            if WAIVER.search(on_line) or WAIVER.search(above):
                continue
            yield (lineno, col, MIS001.format(module=module), type(self))
