"""Arg-hashing helper shared by ``Cachetta._get_path`` and the public
``cachetta.hash`` export.

The digest is a 16-char prefix of ``sha256`` over a canonical JSON
encoding of ``{"args": args, "kwargs": kwargs}``. ``json.dumps`` is
called with ``sort_keys=True`` so kwargs are deterministic, and
``default=str`` so non-JSON-native objects fall back to their string
representation rather than raising.

The digest is **not** portable across languages: the JavaScript
implementation hashes ``JSON.stringify(args)`` only (no kwargs concept)
and uses a different stringifier.
"""

import hashlib
import json
from typing import Any


def hash(*args: Any, **kwargs: Any) -> str:
    """Return the 16-char SHA-256 prefix Cachetta uses to derive cache
    file names.

    Matches the digest the auto-keyed path embeds when a decorated
    function is called with the same args. Useful for building custom
    ``path=`` lambdas, the ``/`` operator's callable form, or external
    indexes that line up with cachetta's own keying.

    Example::

        from cachetta import hash

        hash("user-123", page=1)  # 16-char hex string

    Note: the JavaScript ``hash`` export uses a different stringifier,
    so the same logical input produces different digests across
    languages. Do not rely on cross-language equality.
    """
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]
