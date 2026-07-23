"""Tests for customer name/phone parsing and English-only phone readback."""

import pytest

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.customer_info import (
    accumulate_phone,
    enforce_english_phone_in_speech,
    extract_phone_digits,
    format_phone_spoken,
    is_plausible_phone,
    is_valid_customer_name,
    looks_like_phone_utterance,
    parse_customer_name,
    phone_fragment_digits,
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


def test_placeholder_names_rejected():
    for bad in ("Sir", "sir", "Customer", "Ma'am", "Guest", "Caller"):
        assert not is_valid_customer_name(bad)


def test_real_names_still_accepted():
    for good in ("Aman", "Aman Singh", "Priya"):
        assert is_valid_customer_name(good)


def test_555_exchange_rejected():
    assert not is_plausible_phone("5551234567")
    assert not is_plausible_phone("4165551234")


def test_repeated_digit_number_rejected():
    assert not is_plausible_phone("1111111111")


def test_sequential_digit_number_rejected():
    assert not is_plausible_phone("1234567890")
    assert not is_plausible_phone("0123456789")


def test_real_looking_number_accepted():
    assert is_plausible_phone("7804441234")


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


# ---------------------------------------------------------------------------
# PR 082 — code-side phone digit custody: pure fragment extractor + reducer.


def test_extract_real_call_single_shot():
    # The real-call vector: dictated with a space, must yield all 10 digits.
    assert extract_phone_digits("It's 80770 39800.") == "8077039800"


def test_phone_fragment_digits_real_vectors():
    # Filler words + danda around real dictated fragments.
    assert phone_fragment_digits("there's zero. 39800।") == "039800"
    assert phone_fragment_digits("80") == "80"
    assert phone_fragment_digits("80।") == "80"
    assert phone_fragment_digits("807") == "807"
    assert phone_fragment_digits("it's 80770") == "80770"


def test_phone_fragment_digits_non_fragments():
    # Non-phone utterances (no digits, or menu words) → None.
    assert phone_fragment_digits("Thanks.") is None
    assert phone_fragment_digits("No, that's it.") is None
    assert phone_fragment_digits("two samosas") is None
    # A single digit is too little to be a fragment.
    assert phone_fragment_digits("eight") is None


def test_accumulate_single_shot_save():
    buf, event = accumulate_phone("", "It's 80770 39800.")
    assert (buf, event) == ("8077039800", "saved")


def test_accumulate_stitches_fragments():
    buf = ""
    buf, e1 = accumulate_phone(buf, "80")
    assert (buf, e1) == ("80", "append")
    buf, e2 = accumulate_phone(buf, "770")
    assert (buf, e2) == ("80770", "append")
    buf, e3 = accumulate_phone(buf, "39800")
    assert (buf, e3) == ("8077039800", "saved")


def test_accumulate_repeat_suppression():
    buf, event = accumulate_phone("80770", "80770")
    assert (buf, event) == ("80770", "repeat")


def test_accumulate_correction_reset():
    buf = ""
    buf, _ = accumulate_phone(buf, "80770")
    buf, e = accumulate_phone(buf, "no, it's 90770")
    assert (buf, e) == ("90770", "reset")
    buf, e = accumulate_phone(buf, "39800")
    assert (buf, e) == ("9077039800", "saved")


def test_accumulate_overflow_restatement():
    # Appending would exceed 10 → treat the fragment as a fresh restatement.
    buf, event = accumulate_phone("80770", "807703")
    assert event == "reset"
    assert buf == "807703"


def test_accumulate_non_fragment_leaves_buffer():
    buf, event = accumulate_phone("80770", "Thanks, that's all.")
    assert (buf, event) == ("80770", "none")
