"""Consumer-visible Python version floor.

The installed package advertises its supported interpreter range via the
``Requires-Python`` metadata field — the value pip consults before
allowing an install. These tests pin the declared floor to 3.10: the
source uses nothing newer than 3.10 syntax (runtime ``X | Y`` unions),
so consumers on 3.10/3.11 must not be shut out, while 3.9 (EOL October
2025) stays deliberately unsupported.
"""

from importlib.metadata import metadata

from packaging.specifiers import SpecifierSet


def describe_requires_python_floor():
    def _declared_range() -> SpecifierSet:
        return SpecifierSet(metadata("cachetta")["Requires-Python"])

    def test_python_3_10_is_supported():
        assert _declared_range().contains("3.10"), (
            "Expected the declared Requires-Python range to admit 3.10; got %s"
            % _declared_range()
        )

    def test_python_3_11_is_supported():
        assert _declared_range().contains("3.11"), (
            "Expected the declared Requires-Python range to admit 3.11; got %s"
            % _declared_range()
        )

    def test_python_3_9_stays_unsupported():
        assert not _declared_range().contains("3.9"), (
            "Expected the declared Requires-Python range to exclude EOL 3.9; got %s"
            % _declared_range()
        )
