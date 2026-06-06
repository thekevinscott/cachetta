"""Unit tests for the pure helpers in cachetta.utils.cache_fn.

The wrapper construction in ``cache_fn`` itself is exercised end-to-end by the
integration suite; these unit tests pin the pure, side-effect-free helpers.
"""

from types import SimpleNamespace

from cachetta.utils.cache_fn import _resolve_args, _should_cache


def describe_resolve_args():
    def test_strips_first_positional_arg_when_skip_self():
        cache = SimpleNamespace(skip_self=True)
        args, kwargs = _resolve_args(cache, ("self", 1, 2), {"k": "v"})
        assert args == (1, 2)
        assert kwargs == {"k": "v"}

    def test_keeps_args_when_skip_self_but_no_positional_args():
        cache = SimpleNamespace(skip_self=True)
        args, kwargs = _resolve_args(cache, (), {"k": "v"})
        assert args == ()
        assert kwargs == {"k": "v"}

    def test_keeps_all_args_when_not_skip_self():
        cache = SimpleNamespace(skip_self=False)
        args, kwargs = _resolve_args(cache, ("self", 1), {})
        assert args == ("self", 1)


def describe_should_cache():
    def test_caches_when_no_condition_is_set():
        cache = SimpleNamespace(condition=None)
        assert _should_cache(cache, "anything") is True

    def test_delegates_to_the_condition_callable():
        cache = SimpleNamespace(condition=lambda result: result > 0)
        assert _should_cache(cache, 5) is True
        assert _should_cache(cache, -1) is False
