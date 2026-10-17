"""The think setting is normalized in code before it reaches Ollama.

No model calls. A reasoning model left on its default thinks for minutes,
so the value from config.toml or REVIEW_THINK must arrive as exactly what
Ollama expects, and anything else must fail loudly with the fix.
"""

import pytest

import review


@pytest.mark.parametrize("value", [False, "false", "off", "no", "0", "FALSE"])
def test_off_values_become_false(value):
    assert review.parse_think(value) is False


@pytest.mark.parametrize("value", [True, "true", "on", "yes", "1"])
def test_on_values_become_true(value):
    assert review.parse_think(value) is True


@pytest.mark.parametrize("value", ["low", "Medium", " high "])
def test_levels_are_kept_lowercase(value):
    assert review.parse_think(value) == value.strip().lower()


def test_unset_sends_nothing():
    assert review.parse_think(None) is None


def test_unknown_value_fails_loudly():
    with pytest.raises(SystemExit):
        review.parse_think("maximum")
