"""Enforce that unit tests mock their cross-module collaborators.

Every test file is either a *unit* test (subject to this check) or an
*integration* test (marked ``pytestmark = pytest.mark.integration`` and
therefore excluded). There is no third category.

A unit test should exercise one module in isolation, so this check requires:

* it targets exactly one source module, colocated by the ``<name>_test.py`` <->
  ``<name>.py`` convention -- otherwise it isn't really a unit test, so rename
  it or mark it integration; and
* every *top-level* first-party import is the module under test, a pure value
  module (``cachetta.exceptions`` / ``cachetta._sentinel``), or carries an
  inline ``# mock-enforce-ignore: <reason>`` waiver.

In Python the idiom for isolating a unit is to ``patch(...)`` the collaborator
on the *consumer* module rather than importing it, so a real first-party
collaborator imported at module scope is the smell this catches. The scan is a
cheap static AST pass, so it lives in the unit suite rather than a separate CI
job.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src" / "cachetta"
SELF = Path(__file__).name

PURE_VALUE_MODULES = {"cachetta.exceptions", "cachetta._sentinel"}

WAIVER = re.compile(r"mock-enforce-ignore:\s*\S")


def _test_files() -> list[Path]:
    return [p for p in sorted(TESTS_DIR.rglob("*_test.py")) if p.name != SELF]


def _is_integration(tree: ast.Module) -> bool:
    """True if the module declares ``pytestmark = pytest.mark.integration``
    (directly or inside a list of marks)."""
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


def _module_under_test(path: Path) -> str | None:
    """Map a test file to the dotted source module it targets, if any."""
    rel = path.relative_to(TESTS_DIR).with_suffix("")
    name = rel.name[: -len("_test")]
    parts = [*rel.parts[:-1], name]
    if not SRC_DIR.joinpath(*parts).with_suffix(".py").exists():
        return None
    return ".".join(["cachetta", *parts])


def _first_party_imports(tree: ast.Module) -> list[tuple[str, int]]:
    """Top-level ``(module, lineno)`` imports of first-party ``cachetta`` code."""
    found: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            if node.module == "cachetta" or node.module.startswith("cachetta."):
                found.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cachetta" or alias.name.startswith("cachetta."):
                    found.append((alias.name, node.lineno))
    return found


def _violations(path: Path) -> list[str]:
    text = path.read_text()
    tree = ast.parse(text)
    if _is_integration(tree):
        return []
    rel = path.relative_to(TESTS_DIR)
    module_under_test = _module_under_test(path)
    if module_under_test is None:
        return [
            f"  {rel} is a unit test but maps to no source module under "
            f"src/cachetta. Rename it to '<module>_test.py' to target one module, "
            f"or mark it `pytestmark = pytest.mark.integration`."
        ]
    lines = text.splitlines()
    problems: list[str] = []
    for module, lineno in _first_party_imports(tree):
        if module == module_under_test or module in PURE_VALUE_MODULES:
            continue
        on_line = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
        above = lines[lineno - 2] if 0 <= lineno - 2 < len(lines) else ""
        if WAIVER.search(on_line) or WAIVER.search(above):
            continue
        problems.append(
            f"  {rel}:{lineno} imports '{module}' — real cross-module collaborator. "
            f"Patch it on the consumer module, or add a "
            f"'# mock-enforce-ignore: <reason>' comment if using the real module is intentional."
        )
    return problems


def describe_mock_enforcement():
    def it_mocks_or_waives_all_cross_module_collaborators():
        problems = [msg for path in _test_files() for msg in _violations(path)]
        assert not problems, (
            "Un-mocked collaborators found in unit tests:\n" + "\n".join(problems)
        )
