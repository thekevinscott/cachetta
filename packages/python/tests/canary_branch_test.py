"""CANARY — do not merge.

Deliberately exercises ONLY the positive branch of ``canary_branch``.
Line coverage is 100%; branch coverage is 50%.
"""

from cachetta.canary_branch import canary_branch


def describe_canary_branch():
    def test_covers_the_positive_side():
        assert canary_branch(5) == 1
