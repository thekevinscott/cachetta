import io
import os
import pickle
import tempfile
from collections import OrderedDict, defaultdict, deque
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath
from uuid import UUID

import pytest

from cachetta import Cachetta, UnsafePickleError
from cachetta.read_cache import read_cache
from cachetta.safe_pickle import safe_load
from cachetta.write_cache import write_cache


class _ArbitraryClass:
    """Module-level class for testing that arbitrary types are blocked."""
    pass


class _CustomData:
    """Module-level class for testing custom allowlist extension."""
    def __init__(self, value=None):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, _CustomData) and self.value == other.value


class _CustomMergeType:
    """Module-level class for testing that custom types merge with defaults."""
    pass


class _UserData:
    """Module-level class for Cachetta integration test with custom allowlist."""
    def __init__(self, name=None):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, _UserData) and self.name == other.name


def _roundtrip(value):
    """Pickle a value then safe_load it back."""
    buf = io.BytesIO()
    pickle.dump(value, buf)
    buf.seek(0)
    return safe_load(buf)


def _make_malicious_payload(module, name, *args):
    """Build a pickle payload that calls module.name(*args)."""
    buf = io.BytesIO()
    # Craft the payload using __reduce__ to invoke module.name(*args)
    class _Exploit:
        def __reduce__(self):
            import importlib
            func = getattr(importlib.import_module(module), name)
            return (func, args)

    pickle.dump(_Exploit(), buf)
    buf.seek(0)
    return buf


def describe_default_safe_types():
    """All types in the default allowlist should round-trip cleanly."""

    def test_primitives():
        # Plain primitives are handled by pickle VM directly, but verify anyway
        for val in [42, 3.14, "hello", b"bytes", True, False, None]:
            assert _roundtrip(val) == val

    def test_set():
        assert _roundtrip({1, 2, 3}) == {1, 2, 3}

    def test_frozenset():
        assert _roundtrip(frozenset([4, 5, 6])) == frozenset([4, 5, 6])

    def test_complex():
        assert _roundtrip(complex(1, 2)) == complex(1, 2)

    def test_bytearray():
        assert _roundtrip(bytearray(b"abc")) == bytearray(b"abc")

    def test_datetime_types():
        now = datetime.now()
        assert _roundtrip(now) == now
        today = date.today()
        assert _roundtrip(today) == today
        t = time(12, 30, 45)
        assert _roundtrip(t) == t
        td = timedelta(days=1, hours=2)
        assert _roundtrip(td) == td
        tz = timezone.utc
        assert _roundtrip(tz) == tz

    def test_decimal():
        d = Decimal("3.14159")
        assert _roundtrip(d) == d

    def test_uuid():
        u = UUID("12345678-1234-5678-1234-567812345678")
        assert _roundtrip(u) == u

    def test_collections():
        od = OrderedDict([("a", 1), ("b", 2)])
        assert _roundtrip(od) == od

        dd = defaultdict(list, {"x": [1, 2]})
        result = _roundtrip(dd)
        assert isinstance(result, defaultdict)
        assert result["x"] == [1, 2]

        dq = deque([1, 2, 3])
        assert _roundtrip(dq) == dq

    def test_pathlib():
        p = PurePosixPath("/usr/local/bin")
        assert _roundtrip(p) == p


def describe_blocked_types():
    """Dangerous types must be rejected."""

    def test_blocks_os_system():
        payload = _make_malicious_payload("os", "system", "echo pwned")
        with pytest.raises(UnsafePickleError, match="not in allowlist"):
            safe_load(payload)

    def test_blocks_subprocess_popen():
        payload = _make_malicious_payload("subprocess", "Popen", ["echo", "pwned"])
        with pytest.raises(UnsafePickleError, match="not in allowlist"):
            safe_load(payload)

    def test_blocks_builtins_eval():
        payload = _make_malicious_payload("builtins", "eval", "1+1")
        with pytest.raises(UnsafePickleError, match="not in allowlist"):
            safe_load(payload)

    def test_blocks_arbitrary_class():
        buf = io.BytesIO()
        pickle.dump(_ArbitraryClass(), buf)
        buf.seek(0)
        with pytest.raises(UnsafePickleError):
            safe_load(buf)


def describe_custom_allowlist():
    """Users can extend the allowlist with their own types."""

    def test_allows_custom_type():
        obj = _CustomData(42)
        buf = io.BytesIO()
        pickle.dump(obj, buf)
        buf.seek(0)

        # Should fail without custom allowlist
        with pytest.raises(UnsafePickleError):
            safe_load(buf)

        # Should succeed with custom allowlist
        buf.seek(0)
        result = safe_load(buf, allowed_types={_CustomData})
        assert result == obj

    def test_custom_types_merge_with_defaults():
        """Custom types don't replace defaults -- they extend them."""
        # Verify a default type still works when custom types are provided
        buf = io.BytesIO()
        pickle.dump({1, 2, 3}, buf)
        buf.seek(0)
        result = safe_load(buf, allowed_types={_CustomMergeType})
        assert result == {1, 2, 3}


def describe_cachetta_integration():
    """Integration tests with the Cachetta class."""

    def test_blocks_malicious_payload_with_default_config():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "evil.dat"

            # Write a malicious payload directly
            class _Exploit:
                def __reduce__(self):
                    # os.system is intentionally referenced as a representative
                    # dangerous callable in the exploit payload; its soft
                    # deprecation is irrelevant to what this test verifies.
                    return (os.system, ("echo pwned",))  # ty: ignore[deprecated]

            with open(cache_path, "wb") as f:
                pickle.dump(_Exploit(), f)

            cache = Cachetta(path=str(cache_path))
            with read_cache(cache) as data:
                pass
            # Should return None (blocked), not execute the payload
            assert data is None

    def test_allows_custom_types_via_config():
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "custom.dat"
            obj = _UserData("alice")

            # Write the object directly with raw pickle
            with open(cache_path, "wb") as f:
                pickle.dump(obj, f)

            # Without allowlist, reading should return None
            cache_default = Cachetta(path=str(cache_path))
            with read_cache(cache_default) as data:
                pass
            assert data is None

            # With allowlist, reading should succeed
            cache_custom = Cachetta(
                path=str(cache_path),
                allowed_pickle_types={_UserData},
            )
            with read_cache(cache_custom) as data:
                pass
            assert data == obj

    def test_safe_types_work_through_cachetta():
        """Standard types should round-trip through the full Cachetta read/write path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "safe.dat"
            cache = Cachetta(path=str(cache_path))

            value = {
                "numbers": {1, 2, 3},
                "time": datetime.now(),
                "id": UUID("12345678-1234-5678-1234-567812345678"),
                "amount": Decimal("99.99"),
            }

            write_cache(cache, value)

            with read_cache(cache) as data:
                pass
            assert data == value
