---
title: Nested doc fixture
---

# Nested doc fixture

This file is a permanent **test fixture** used by the JS and Python integration
tests to verify that `scripts/sync-docs.sh` recurses into subdirectories and
that the recursive `package-data` glob in `packages/python/pyproject.toml`
picks up nested markdown files in the built wheel.

Its directory name (`_test/`) starts with an underscore so Jekyll ignores it
when building the docs site — it is **not** intended to be linked from any
human-facing page.

If you are removing the test fixture, also remove the tests under
`packages/javascript/tests/nested-docs.test.ts` and
`packages/python/tests/nested_docs_test.py`.
