"""Unit tests for cachetta.hash."""

from cachetta.hash import hash


def describe_hash():
    def test_returns_a_16_char_lowercase_hex_string():
        result = hash("a", "b")
        assert isinstance(result, str)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_deterministic_across_calls():
        assert hash("x", "y", z=1) == hash("x", "y", z=1)

    def test_distinct_positional_inputs_produce_distinct_digests():
        assert hash("a") != hash("b")
        assert hash(1) != hash(2)

    def test_distinct_kwargs_produce_distinct_digests():
        assert hash(k=1) != hash(k=2)
        assert hash(name="a") != hash(name="b")

    def test_no_args_is_valid_and_stable():
        # Stable across calls; positional and kwargs separation still applies.
        assert hash() == hash()

    def test_non_json_native_value_falls_back_to_str():
        # ``default=str`` in the JSON encoder is what lets cachetta key on
        # arbitrary objects without raising. A custom ``__str__`` should be
        # respected and influence the digest.
        class Tagged:
            def __init__(self, tag: str) -> None:
                self.tag = tag

            def __str__(self) -> str:
                return f"<Tagged {self.tag}>"

        assert hash(Tagged("a")) != hash(Tagged("b"))
        assert hash(Tagged("a")) == hash(Tagged("a"))
