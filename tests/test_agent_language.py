"""Tests for restaurant.agent.language — script detection + sticky language."""

from restaurant.agent.language import (
    OPENING_GREETING,
    CustomerLanguage,
    detect_customer_language,
    update_preferred_language,
)


def test_opening_greeting_offers_three_languages():
    assert "English" in OPENING_GREETING
    assert "Hindi" in OPENING_GREETING
    assert "Punjabi" in OPENING_GREETING


def test_detect_gurmukhi_is_punjabi():
    assert detect_customer_language("ਦੋ ਬਟਰ ਚਿਕਨ ਚਾਹੀਦੇ") == CustomerLanguage.PUNJABI


def test_detect_devanagari_is_hindi():
    assert detect_customer_language("दो बटर चिकन चाहिए") == CustomerLanguage.HINDI


def test_detect_latin_is_english():
    assert detect_customer_language("two butter chicken please") == CustomerLanguage.ENGLISH


def test_detect_short_text_abstains():
    assert detect_customer_language("k") is None
    assert detect_customer_language("") is None


def test_detect_mixed_scripts():
    # One char of each Indic script — neither dominates.
    assert detect_customer_language("ਹ ज") == CustomerLanguage.MIXED


def test_update_is_sticky_when_undetectable():
    assert (
        update_preferred_language(CustomerLanguage.PUNJABI, "k")
        == CustomerLanguage.PUNJABI
    )


def test_update_switches_on_clear_script_change():
    assert (
        update_preferred_language(CustomerLanguage.ENGLISH, "ਦੋ ਸਮੋਸੇ ਚਾਹੀਦੇ")
        == CustomerLanguage.PUNJABI
    )


def test_update_keeps_current_on_mixed():
    assert (
        update_preferred_language(CustomerLanguage.PUNJABI, "ਹਾਂ जी ठीक ਹੈ")
        == CustomerLanguage.PUNJABI
    )


def test_update_defaults_to_english():
    assert update_preferred_language(None, "hm") == CustomerLanguage.ENGLISH
