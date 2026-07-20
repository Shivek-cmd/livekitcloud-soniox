"""Tests for customer name/phone parsing and English-only phone readback."""

import pytest

from restaurant import menu_provider
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


def test_enforce_rewrites_ascii_phone_in_place():
    # Migrated from the deleted sanitize_assistant_speech (PR 079) — the
    # enforcement now runs in the TTS path, directly on this function.
    phone = "9413752688"
    raw = "Your number is 94137 52688, correct?"
    out = enforce_english_phone_in_speech(raw, phone)
    assert "nine" in out
    assert out.startswith("Your number is")
    assert "correct?" in out


def test_enforce_word_chain_replaced_in_place():
    # PR 079 — a spoken digit-word chain must be canonicalized WITHOUT
    # deleting the surrounding speech (this output is actually spoken now).
    phone = "9413752688"
    raw = "So that's nine four one three seven five two six eight eight, is that right?"
    out = enforce_english_phone_in_speech(raw, phone)
    assert out.startswith("So that's")
    assert "is that right?" in out
    assert "nine, four, one, three, seven, five, two, six, eight, eight" in out


def test_enforce_short_digit_words_untouched():
    # Quantity words must never be rewritten as phone digits.
    phone = "9413752688"
    raw = "two Butter Chicken and three Garlic Naan"
    assert enforce_english_phone_in_speech(raw, phone) == raw


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


# ---------------------------------------------------------------------------
# PR 072 -- spoken-word phone digits (checkout rejection-loop fix).
# extract_phone_digits currently strips every non-digit char, so a
# word-dictated phone number ("nine four one three...") yields zero digits
# and returns None. These tests are RED until Task 2 wires
# _spoken_words_to_digits into extract_phone_digits / looks_like_phone_utterance.


def test_english_word_phone():
    assert (
        extract_phone_digits("nine four one three seven five two six eight eight")
        == "9413752688"
    )


def test_mixed_digit_and_word_phone():
    assert extract_phone_digits("94137 five two six eight eight") == "9413752688"


def test_oh_double_triple_forms():
    assert (
        extract_phone_digits("oh four one three seven five two six eight eight")
        == "0413752688"
    )
    assert (
        extract_phone_digits("double eight one three seven five two six eight one")
        == "8813752681"
    )
    assert (
        extract_phone_digits("triple five one three seven five two six eight")
        == "5551375268"
    )


def test_romanized_hindi_punjabi_phone():
    assert (
        extract_phone_digits("nau char ek teen saat paanch do chhe aath aath")
        == "9413752688"
    )


def test_indic_script_word_phone():
    assert (
        extract_phone_digits("ਨੌ ਚਾਰ ਇੱਕ ਤਿੰਨ ਸੱਤ ਪੰਜ ਦੋ ਛੇ ਅੱਠ ਅੱਠ")
        == "9413752688"
    )
    assert (
        extract_phone_digits("नौ चार एक तीन सात पांच दो छह आठ आठ")
        == "9413752688"
    )


def test_word_phone_negatives():
    # Non-phone utterance must never be misread as a phone number.
    assert extract_phone_digits("do samosa") is None
    # 9-word-digit string (one short of 10) must still return None.
    assert (
        extract_phone_digits("nine four one three seven five two six eight")
        is None
    )
    # A real name utterance is unaffected by the word-digit normalization.
    assert parse_customer_name("my name is Shivek") == "Shivek"


def test_looks_like_phone_utterance_word_digits():
    assert looks_like_phone_utterance(
        "nine four one three seven five two six eight eight"
    )
    assert (
        parse_customer_name(
            "nine four one three seven five two six eight eight"
        )
        is None
    )
