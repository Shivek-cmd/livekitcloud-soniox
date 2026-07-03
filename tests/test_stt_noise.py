"""Tests for STT noise and quantity parsing (PR 044)."""

from restaurant.stt_noise import (
    agent_recently_asked_quantity,
    is_likely_stt_noise,
    parse_standalone_quantity,
    utterance_has_explicit_quantity,
)


def test_parse_standalone_van():
    assert parse_standalone_quantity("ਵਨ।") == 1
    assert parse_standalone_quantity("van") == 1
    assert parse_standalone_quantity("one") == 1


def test_utterance_has_explicit_quantity_gurmukhi():
    text = "ਹਾਂ ਜੀ, ਮੈਨੂੰ ਇੱਕ ਫਿਸ਼ ਚਾਹੀਦੀ ਸੀ"
    assert utterance_has_explicit_quantity(text) is True


def test_utterance_has_no_quantity():
    assert utterance_has_explicit_quantity("fish pakora please") is False


def test_stt_noise_subscription():
    assert is_likely_stt_noise("ठीक है, बिगिनर सब्सक्रिप्शन। One—") is True


def test_stt_noise_clean_order():
    assert is_likely_stt_noise("one chicken tikka please") is False


def test_agent_recently_asked_quantity():
    assert agent_recently_asked_quantity(
        ["Okay — one Fish. How many would you like — one or two?"]
    )
