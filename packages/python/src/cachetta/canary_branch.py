"""CANARY — do not merge.

The unit test exercises only the ``x > 0`` path. Every LINE runs, so line
coverage is 100%, but the ``if`` has an untaken (False) arc, so branch
coverage is < 100%. If CI is green, branch coverage is not enforced on
changed code.
"""


def canary_branch(x: int) -> int:
    result = 2
    if x > 0:
        result = 1
    return result
