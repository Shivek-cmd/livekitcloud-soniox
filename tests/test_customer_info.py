"""Tests for customer name/phone parsing and English-only phone readback."""

import pytest

from restaurant import menu_provider
from restaurant.agent.replies import sanitize_assistant_speech
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.customer_info import (
    enforce_english_phone_in_speech,
    extract_phone_digits,
    format_phone_spoken,
    is_valid_customer_name,
    looks_like_phone_utterance,
    parse_customer_name,
)


# ---------------------------------------------------------------------------
# PR 070 — pinned fake cache reproducing the "Singh" -> "Bhatura (single)"
# menu-hint false positive (mirrors tests/test_menu_match.py's _item/_cache
# helpers — no dependence on the real Clover cache file).


def _item(iid, name, speak_as, voice_line, aliases, price=1000):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=speak_as,
        voice_line=voice_line,
        speech_mode="gurmukhi",
        price_cents=price,
        veg=True,
        available=True,
        category_id="",
        category_name="Test",
        aliases=aliases,
    )


def _singh_cache() -> MenuCache:
    items = [
        # Flat single-token phonetic match: phonetic_key("singh")="sng" is a
        # prefix of phonetic_key("single")="sngl" -> UNIQUE_SINGLE_CONF (0.65).
        _item("BHATURA_SINGLE", "Bhatura (single)", "ਭਟੂਰਾ", "ਭਟੂਰਾ", []),
        _item("BUTTER_CHICKEN", "Butter Chicken", "ਬਟਰ ਚਿਕਨ", "ਬਟਰ ਚਿਕਨ", ["butter chicken"]),
    ]
    return MenuCache(items, tenant_id="test", synced_at="now")


@pytest.fixture
def singh_menu_cache(monkeypatch):
    cache = _singh_cache()
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


def test_singh_name_survives_menu_hint(singh_menu_cache):
    assert parse_customer_name("Sandeep Singh") == "Sandeep Singh"


def test_confidence_ladder_guard(singh_menu_cache):
    # Documents what the 0.8 floor is calibrated against — catches silent
    # matcher recalibration in restaurant/clover/match.py.
    hit = menu_provider.find_item("Sandeep Singh")
    assert hit is not None
    assert hit["match_confidence"] == 0.65


def test_singh_gurmukhi_variant(singh_menu_cache):
    assert parse_customer_name("ਅਹ, ਸੰਦੀਪ ਸਿੰਘ") == "ਸੰਦੀਪ ਸਿੰਘ"


def test_name_with_filler_prefix(singh_menu_cache):
    assert parse_customer_name("my name is Sandeep Singh") == "Sandeep Singh"


def test_dish_answer_still_rejected(singh_menu_cache):
    # Precision survives the floor: a caller literally answering the dish
    # name to the name question is still rejected, both scripts.
    assert parse_customer_name("Butter Chicken") is None
    assert parse_customer_name("ਬਟਰ ਚਿਕਨ") is None


def test_extract_phone_digits():
    assert extract_phone_digits("94137 52688") == "9413752688"
    assert extract_phone_digits("+1 941-375-2688") == "9413752688"
    assert extract_phone_digits("9413752688") == "9413752688"


def test_looks_like_phone_utterance():
    assert looks_like_phone_utterance("94137 52688")
    assert not looks_like_phone_utterance("one paneer tikka")


def test_format_phone_spoken_english_words():
    spoken = format_phone_spoken("9413752688")
    assert spoken == "nine, four, one, three, seven, five, two, six, eight, eight"
    assert "ਨੌ" not in spoken
    assert "9" not in spoken


def test_enforce_english_phone_replaces_indic_numerals():
    phone = "9413752688"
    garbled = "ਧੰਨਵਾਦ — ੯੪੧੩੭ ੫੨੬੮੮."
    out = enforce_english_phone_in_speech(garbled, phone)
    assert "nine" in out
    assert "੯" not in out


def test_sanitize_rewrites_phone_to_english_digits():
    phone = "9413752688"
    raw = "Your number is 94137 52688, correct?"
    out = sanitize_assistant_speech(
        raw,
        allow_greeting=True,
        customer_phone=phone,
    )
    assert "nine" in out


def test_parse_customer_name_exact():
    assert parse_customer_name("ਸ਼ਿਵੇਕ") == "ਸ਼ਿਵੇਕ"
    assert parse_customer_name("my name is Shivek") == "Shivek"
    assert parse_customer_name("94137 52688") is None


def test_pickup_not_a_customer_name():
    assert parse_customer_name("ਪਿਕਅੱਪ") is None
    assert parse_customer_name("pickup") is None
    assert not is_valid_customer_name("ਪਿਕਅੱਪ")
    assert is_valid_customer_name("ਸ਼ਿਵੇਕ")


def test_parse_punjabi_name_mera():
    name = parse_customer_name("ਨਾਮ ਮera ਸ਼ਿਵੇਕ ਹੈ")
    assert name
    assert "ਸ਼ਿਵ" in name or "Shiv" in name.lower() or len(name) >= 3


def test_parse_punjabi_name_with_filler_and_two_words():
    name = parse_customer_name("ਅਹ, ਸੰਦੀਪ ਸਿੰਘ")
    assert name == "ਸੰਦੀਪ ਸਿੰਘ"


def test_parse_two_word_english_name():
    assert parse_customer_name("Sandeep Singh") == "Sandeep Singh"
