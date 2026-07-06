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


def test_stt_noise_does_not_reject_kar_dio_multi_item_order():
    # Live-call regression (PR 049): both of these are genuine, clear
    # multi-item orders using "ਕਰ ਦਿਓ" (do it/make it) — an extremely common
    # Punjabi order phrasing not in the old narrow keyword list — that were
    # silently discarded as "noise" before ever reaching the LLM or menu
    # matching.
    t1 = (
        "आपके अपने एक प्लेन राइज़ के दो गार्लिक नान, और अपने "
        "ਤੁਸੀਂ ਚਾਰ ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ ਕਰ ਦਿਓ।"
    )
    t2 = "ਓਕੇ, ਵਨ ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ, ਦੋ ਮਟਰ ਨਾਨ, ਤੇ ਤਿੰਨ ਗਾਰਲਿਕ ਨਾਨ ਕਰ ਦਿਓ।"
    assert is_likely_stt_noise(t1) is False
    assert is_likely_stt_noise(t2) is False


def test_stt_noise_still_rejects_actual_background_media():
    noise = (
        "subscribe to our channel and hit the bell icon for breaking news "
        "updates today please subscribe"
    )
    assert is_likely_stt_noise(noise) is True


def test_agent_recently_asked_quantity():
    assert agent_recently_asked_quantity(
        ["Okay — one Fish. How many would you like — one or two?"]
    )
