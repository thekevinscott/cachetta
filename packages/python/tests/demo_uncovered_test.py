"""DEMONSTRATION ONLY — do not merge.

INTEGRATION test (marked ``integration``, so it is deselected from the
unit coverage run via ``-m "not integration"``). It fully exercises
``demo_uncovered``, but there is deliberately NO colocated unit test.
The coverage gate runs only the unit suite, so this integration
coverage must NOT satisfy the gate.
"""

import pytest

from cachetta import demo_uncovered

pytestmark = pytest.mark.integration


def describe_demo_uncovered():
    def test_adds_when_a_le_b():
        assert demo_uncovered(1, 2) == 3

    def test_subtracts_when_a_gt_b():
        assert demo_uncovered(5, 2) == 3
