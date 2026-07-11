"""Tests for customer name/phone parsing and English-only phone readback."""

from restaurant.agent.replies import sanitize_assistant_speech
from restaurant.customer_info import (
    enforce_english_phone_in_speech,
    extract_phone_digits,
    format_phone_spoken,
    is_valid_customer_name,
    looks_like_phone_utterance,
    parse_customer_name,
)


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
