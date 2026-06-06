"""DEMONSTRATION ONLY — do not merge.

New ``src/`` code exercised purely by an integration test
(``tests/demo_uncovered_test.py``, marked ``integration``) with NO
colocated unit test. Used to confirm the coverage gate fails when
``src/`` lacks unit coverage and integration tests are excluded.
"""


def demo_uncovered(a: int, b: int) -> int:
    """Return ``a - b`` when ``a > b`` else ``a + b``."""
    if a > b:
        return a - b
    return a + b
