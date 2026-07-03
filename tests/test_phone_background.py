"""Phone background speech filter."""

from restaurant.conversation import UserIntent, detect_intent
from restaurant.phone_background import is_likely_background_speech


def test_pickup_not_background():
    text = "Yeah, I'm looking for pickup."
    intent = detect_intent(text)
    assert not is_likely_background_speech(text, intent)


def test_order_not_background():
    text = "One paneer tikka and two mango shake."
    intent = detect_intent(text)
    assert not is_likely_background_speech(text, intent)


def test_short_filler_is_background():
    assert is_likely_background_speech("mm hmm", UserIntent.GENERAL)
    assert is_likely_background_speech("thank you", UserIntent.GENERAL)


def test_short_meaningful_not_background():
    assert not is_likely_background_speech("pickup", UserIntent.GENERAL)
    assert not is_likely_background_speech("haan ji", detect_intent("haan ji"))


def test_disabled_never_filters():
    assert not is_likely_background_speech(
        "mm hmm", UserIntent.GENERAL, enabled=False
    )


def test_customer_name_phase_never_filters_single_word():
    assert not is_likely_background_speech(
        "ਸੰਦੀਪ",
        UserIntent.GENERAL,
        phase="customer_name",
    )


def test_quantity_van_not_background_while_collecting():
    assert not is_likely_background_speech(
        "ਵਨ।",
        UserIntent.GENERAL,
        phase="awaiting_more",
    )
