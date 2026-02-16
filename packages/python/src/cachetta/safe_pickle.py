"""Restricted pickle deserialization to prevent arbitrary code execution.

Standard pickle.load() allows arbitrary code execution from tampered cache files.
This module provides a RestrictedUnpickler that only allows known-safe types.
"""

import io
import pickle
from typing import Iterable


class UnsafePickleError(pickle.UnpicklingError):
    """Raised when a pickle stream references a type not in the allowlist."""

    pass


# (module, qualname) pairs that the RestrictedUnpickler will accept by default.
# Only types that go through find_class need to be listed — plain ints, floats,
# strings, bytes, lists, dicts, tuples, bools, and None are reconstructed by
# the pickle VM directly and never hit find_class.
DEFAULT_ALLOWED_PICKLE_TYPES: frozenset[tuple[str, str]] = frozenset(
    {
        # builtins that DO go through find_class (used as __reduce__ args,
        # defaultdict factories, etc.)
        ("builtins", "set"),
        ("builtins", "frozenset"),
        ("builtins", "complex"),
        ("builtins", "bytearray"),
        ("builtins", "range"),
        ("builtins", "slice"),
        ("builtins", "list"),
        ("builtins", "dict"),
        ("builtins", "tuple"),
        ("builtins", "int"),
        ("builtins", "float"),
        ("builtins", "str"),
        ("builtins", "bool"),
        ("builtins", "bytes"),
        # datetime
        ("datetime", "datetime"),
        ("datetime", "date"),
        ("datetime", "time"),
        ("datetime", "timedelta"),
        ("datetime", "timezone"),
        # decimal / uuid
        ("decimal", "Decimal"),
        ("uuid", "UUID"),
        # collections
        ("collections", "OrderedDict"),
        ("collections", "defaultdict"),
        ("collections", "deque"),
        # pathlib
        ("pathlib", "PurePosixPath"),
        ("pathlib", "PureWindowsPath"),
        ("pathlib", "PosixPath"),
        ("pathlib", "WindowsPath"),
    }
)


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that rejects any type not in the allowlist."""

    def __init__(
        self,
        f: io.BufferedIOBase,
        allowed_types: frozenset[tuple[str, str]],
    ):
        super().__init__(f)
        self._allowed_types = allowed_types

    def find_class(self, module: str, name: str) -> type:
        if (module, name) not in self._allowed_types:
            raise UnsafePickleError(
                "Blocked unpickling of %s.%s — type not in allowlist" % (module, name)
            )
        return super().find_class(module, name)


def _types_to_pairs(types: Iterable[type]) -> frozenset[tuple[str, str]]:
    """Convert an iterable of type objects to (module, qualname) pairs."""
    return frozenset((t.__module__, t.__qualname__) for t in types)


def safe_load(
    f: io.BufferedIOBase,
    allowed_types: set[type] | None = None,
) -> object:
    """Deserialize a pickle stream, blocking types not in the allowlist.

    Args:
        f: A binary file-like object positioned at the start of a pickle stream.
        allowed_types: Optional set of additional type objects to allow beyond
            the defaults. Pass ``None`` (default) to use only the built-in
            safe types.

    Returns:
        The deserialized object.

    Raises:
        UnsafePickleError: If the stream references a type not in the allowlist.
    """
    combined = DEFAULT_ALLOWED_PICKLE_TYPES
    if allowed_types:
        combined = combined | _types_to_pairs(allowed_types)
    return RestrictedUnpickler(f, combined).load()
