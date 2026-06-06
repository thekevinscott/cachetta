"""Enforce that unit tests mock their cross-module collaborators.

A unit test should exercise one module in isolation. This check scans every
unit test that targets a specific source module (colocated by the
``<name>_test.py`` <-> ``<name>.py`` convention) and flags any *top-level*
first-party import that is neither the module under test, a pure value module
(``cachetta.exceptions`` / ``cachetta._sentinel``), nor explicitly waived.

In Python the idiom for isolating a unit is to ``patch(...)`` the collaborator
on the *consumer* module rather than importing it, so a real first-party
collaborator imported at module scope is the smell we catch here. Where using
the real module is intentional (e.g. the ``Cachetta`` config object used as a
fixture), an inline ``# mock-enforce-ignore: <reason>`` comment records why.

Files that do not map to a single source module (behavior-themed suites such as
``async_test.py``) are out of scope for per-module isolation and are skipped.
The scan is a cheap static AST pass, so it lives in the unit suite rather than a
separate CI job.
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


def _unit_test_files() -> list[Path]:
    return [
        p
        for p in sorted(TESTS_DIR.rglob("*_test.py"))
        if p.name not in {SELF, "integration_test.py"}
    ]


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
    module_under_test = _module_under_test(path)
    if module_under_test is None:
        return []
    text = path.read_text()
    lines = text.splitlines()
    rel = path.relative_to(TESTS_DIR)
    problems: list[str] = []
    for module, lineno in _first_party_imports(ast.parse(text)):
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
        problems = [msg for path in _unit_test_files() for msg in _violations(path)]
        assert not problems, (
            "Un-mocked collaborators found in unit tests:\n" + "\n".join(problems)
        )
