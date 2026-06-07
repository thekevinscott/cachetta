# internals/

CI-only guards that assert facts *about* this repo's tooling. Nothing here is
shipped, and nothing here is part of either package's test suite — it lives
outside `pytest src/` (Python) and the `src/**/*.test.ts` globs (JS) on
purpose, so a guard can check the unit/integration boundary without being
measured by it.

## `check_boundary.py`

Locks in the rule that **unit coverage is measured by location, not by a
marker**: unit tests are colocated (`src/cachetta/**/*_test.py`,
`src/**/*.test.ts`), everything under `packages/*/tests/` is integration and
never feeds the unit-coverage number, and the deprecated
`pytest.mark.integration` marker stays gone. Run it directly:

```bash
python internals/check_boundary.py
```

It runs in CI via `.github/workflows/internals.yaml` on every PR.
