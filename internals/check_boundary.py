#!/usr/bin/env python3
"""Boundary guard: unit coverage is measured by LOCATION, never by a marker.

This is a CI-only guard. It deliberately lives under ``internals/`` — outside
both packages' shipped test suites (``pytest src/`` for Python, the
``src/**/*.test.ts`` globs for JS) — so it can assert facts *about* those
suites without being collected or measured by them.

It exists because the repo repeatedly regressed the same way: integration
tests counting toward "unit" coverage, so a feature with no real unit tests
still reported 100%. The invariant locked in here:

  * Python unit tests are colocated ``src/cachetta/**/*_test.py``; the unit
    coverage gate runs ``pytest src/cachetta`` (by location), not the old
    ``-m "not integration"`` marker.
  * JS unit tests are colocated ``src/**/*.test.ts``; the unit run excludes
    ``tests/``.
  * Everything under ``packages/*/tests/`` is integration and never feeds the
    unit-coverage number.
  * The deprecated ``pytest.mark.integration`` marker is gone.
  * Colocated test files are not shipped in the built package.

Run: ``python internals/check_boundary.py`` (exit non-zero on any violation).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


# --- Python: the unit-coverage gate is location-based, not marker-based. ---
py_test = read(".github/workflows/py-test.yaml")
cov_cmds = [ln for ln in py_test.splitlines() if "pytest" in ln and "--cov" in ln]
check(
    any("pytest src/cachetta" in ln for ln in cov_cmds),
    "py-test.yaml: the unit-coverage command must run `pytest src/cachetta` "
    "(location-based).",
)
check(
    all("not integration" not in ln for ln in cov_cmds),
    "py-test.yaml: the unit-coverage command must not select via the deprecated "
    '`-m "not integration"` marker.',
)

# --- Python: colocated test files are omitted from the coverage measurement. ---
pyproject = read("packages/python/pyproject.toml")
check(
    "[tool.coverage.run]" in pyproject and "*_test.py" in pyproject,
    "pyproject.toml: [tool.coverage.run] must omit *_test.py so the gate "
    "reflects source coverage, not the colocated tests.",
)

# --- Python: the integration marker is fully retired. ---
check(
    "mark.integration" not in pyproject,
    "pyproject.toml: the `integration` pytest marker must not be registered "
    "(the boundary is by location now).",
)
for path in (ROOT / "packages/python/tests").rglob("*.py"):
    check(
        "pytest.mark.integration" not in path.read_text(),
        f"{path.relative_to(ROOT)}: remove `pytest.mark.integration` — the "
        "unit/integration boundary is by location, not a marker.",
    )

# --- No misplaced unit tests: nothing under tests/ may map to a src module. ---
src_pkg = ROOT / "packages/python/src/cachetta"
tests_dir = ROOT / "packages/python/tests"
for path in tests_dir.rglob("*_test.py"):
    rel = path.relative_to(tests_dir).with_suffix("")
    module = src_pkg.joinpath(*rel.parts[:-1], rel.name[: -len("_test")]).with_suffix(".py")
    check(
        not module.exists(),
        f"{path.relative_to(ROOT)} maps to source module "
        f"{module.relative_to(ROOT)}: a unit test belongs colocated under "
        "src/, not in tests/ (which is integration).",
    )

# --- Colocated tests must not ship in the built package. ---
setup_py = read("packages/python/setup.py")
manifest = read("packages/python/MANIFEST.in")
check(
    "build_py" in setup_py and "_test" in setup_py,
    "setup.py: build_py must exclude *_test.py modules from the wheel.",
)
check(
    "global-exclude *_test.py" in manifest,
    "MANIFEST.in: must `global-exclude *_test.py` from the sdist.",
)

# --- JS symmetry: the unit run is colocated src tests, with tests/ excluded. ---
vitest = read("packages/javascript/vitest.config.unit.ts")
check(
    "src/**/*.test.ts" in vitest,
    "vitest.config.unit.ts: the unit run must include src/**/*.test.ts.",
)
check(
    "tests/" in vitest,
    "vitest.config.unit.ts: integration tests under tests/ must be excluded "
    "from the unit run.",
)

if failures:
    print("Boundary guard FAILED:")
    for message in failures:
        print(f"  - {message}")
    sys.exit(1)

print("Boundary guard passed: unit coverage is measured by location in both packages.")
