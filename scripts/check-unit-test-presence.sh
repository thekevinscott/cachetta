#!/usr/bin/env bash
#
# Enforce a hard unit/integration boundary: every source module must have its
# own dedicated, colocated unit test. Integration tests live apart and are
# excluded from the coverage suites, so they never satisfy this requirement.
#
# Why this exists in addition to the coverage gates: line-coverage can be
# satisfied *transitively* — an integration test, or an unrelated unit test,
# happening to execute a module's lines. That lets a brand-new module ship
# "100% covered" without ever having a unit test of its own (see PR #58, where
# `_hash.py` was covered only via an end-to-end test and `Cachetta`'s tests).
# Requiring a colocated unit test per module closes that gap.
#
# To exclude a module that genuinely has no unit-testable logic, add it to the
# explicit skip handling below — never silence the check wholesale.
set -euo pipefail

fail=0

note_missing() {
  echo "::error::$1"
  fail=1
}

# --- JavaScript: unit tests are colocated as `<module>.test.ts` -------------
while IFS= read -r src; do
  case "$src" in
    *.test.ts)  continue ;;  # the tests themselves
    */index.ts) continue ;;  # re-export barrel, no logic
    */types.ts) continue ;;  # type-only declarations
  esac
  expected="${src%.ts}.test.ts"
  if [ ! -f "$expected" ]; then
    note_missing "JS: $src has no colocated unit test (expected $expected)"
  fi
done < <(find packages/javascript/src -name '*.ts' | sort)

# --- Python: unit tests mirror the module path as `<module>_test.py` --------
py_src_root="packages/python/src/cachetta"
py_test_root="packages/python/tests"
while IFS= read -r src; do
  rel="${src#"$py_src_root"/}"
  case "$rel" in
    __init__.py)   continue ;;  # package marker / re-exports
    */__init__.py) continue ;;  # subpackage markers
  esac
  expected="$py_test_root/${rel%.py}_test.py"
  if [ ! -f "$expected" ]; then
    note_missing "Python: $src has no unit test (expected $expected)"
  fi
done < <(find "$py_src_root" -name '*.py' | sort)

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "Every source module needs its own unit test (integration tests do not count)."
  echo "Add the missing unit test next to / mirroring the module, or if the module"
  echo "genuinely has no unit-testable logic, exclude it explicitly in"
  echo "scripts/check-unit-test-presence.sh."
  exit 1
fi

echo "OK: every source module has a colocated unit test."
