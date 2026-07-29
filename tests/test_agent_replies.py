"""Tests for restaurant.agent.replies — status template + canned lines.
(The VERBATIM readback formatter moved to READBACK FACTS in PR 078; the
log-only speech guard was deleted in PR 079.)"""

from restaurant.agent import replies
from restaurant.agent.language import CustomerLanguage
from restaurant.agent.replies import (
    contact_readback_line,
    format_order_status,
    order_placed_goodbye,
)
from restaurant.orders import OrderCart

_NAAN = {"name": "Garlic Naan", "voice_line": "Garlic Naan", "price": 3.50}
_BC = {"name": "Butter Chicken", "voice_line": "Butter Chicken", "price": 13.99}


def _cart() -> OrderCart:
    cart = OrderCart()
    cart.add_item(_BC, 1)
    cart.add_item(_NAAN, 2)
    cart.order_type = "pickup"
    return cart


def test_order_status_grounded():
    status = format_order_status(_cart(), include_price=False)
    assert "one Butter Chicken" in status
    assert "two Garlic Naan" in status
    assert "dollar" not in status

    assert "empty" in format_order_status(OrderCart(), include_price=False)


def test_goodbye_eta_by_order_type():
    assert "20-25" in order_placed_goodbye(order_type="pickup")
    assert "30-40" in order_placed_goodbye(order_type="delivery")


def test_goodbye_language_variants():
    # Punjabi default for pa / mixed / unknown.
    for lang in (None, "pa", "mixed"):
        line = order_placed_goodbye(order_type="pickup", language=lang)
        assert "ਤੁਹਾਡਾ ਆਰਡਰ" in line and "ਧੰਨਵਾਦ" in line

    en = order_placed_goodbye(order_type="delivery", language="en")
    assert "30 to 40 minutes" in en and "Thank you" in en

    hi = order_placed_goodbye(order_type="pickup", language="hi")
    assert "आपका ऑर्डर" in hi and "धन्यवाद" in hi and "20-25" in hi


def test_goodbye_accepts_enum_not_just_raw_value():
    """PR 092 regression: core.py passes the CustomerLanguage enum object
    itself (not .value) to order_placed_goodbye. CustomerLanguage subclasses
    (str, Enum), so str(CustomerLanguage.ENGLISH) is "CustomerLanguage.ENGLISH"
    — not "en" — because Enum.__str__ wins over the str mixin. That silently
    defaulted every non-Hindi/English enum call to the Punjabi fallback,
    including English/Hindi sessions, since the string never matched "en"/"hi"."""
    en = order_placed_goodbye(order_type="delivery", language=CustomerLanguage.ENGLISH)
    assert "30 to 40 minutes" in en and "Thank you" in en

    hi = order_placed_goodbye(order_type="pickup", language=CustomerLanguage.HINDI)
    assert "आपका ऑर्डर" in hi and "धन्यवाद" in hi

    pa = order_placed_goodbye(order_type="pickup", language=CustomerLanguage.PUNJABI)
    assert "ਤੁਹਾਡਾ ਆਰਡਰ" in pa and "ਧੰਨਵਾਦ" in pa


def test_reprompt_pools_no_immediate_repeat():
    from restaurant.agent.replies import (
        background_repeat_phrase,
        echo_recovery_phrase,
    )

    for phrase_fn in (echo_recovery_phrase, background_repeat_phrase):
        prev = phrase_fn()
        for _ in range(10):
            cur = phrase_fn()
            assert cur != prev
            prev = cur


def test_reprompt_pool_lines_never_treated_as_caller_speech():
    """Echo of our own reprompt (agent line noted) must be filtered, but the
    pool must not contain lines a real caller would plausibly say cold."""
    from restaurant.agent.replies import _BACKGROUND_REPEAT_POOL, _ECHO_RECOVERY_POOL
    from restaurant.channels.phone_echo import is_likely_phone_echo

    for line in (*_ECHO_RECOVERY_POOL, *_BACKGROUND_REPEAT_POOL):
        assert is_likely_phone_echo(line, [line], intent=None)


# ── AMBIGUOUS refusals must not be spoken as denials ─────────────────────────
# An AMBIGUOUS refusal means the dish IS on the menu and we only failed to pin
# down which one. Speaking "we don't have it" there denies a real menu item.


def test_ambiguous_correction_does_not_deny_the_dish():
    for lang in ("en", "hi", "pa", None):
        line = replies.false_add_correction_phrase(
            "fish", language=lang, ambiguous=True
        )
        assert "don't have" not in line
        assert "नहीं है" not in line
        assert "ਨਹੀਂ ਹੈ" not in line
        assert "fish" in line


def test_not_found_correction_still_denies():
    line = replies.false_add_correction_phrase("sushi", language="en")
    assert "don't have" in line


# ── code-spoken contact readback (PR 101) ────────────────────────────────────


def test_contact_readback_line_is_always_english_digits():
    # The whole point: the digits and the name spelling come from code, so no
    # LLM rendering choice (live: Gurmukhi "ਜ਼ੀਰੋ") can reach the caller.
    line = contact_readback_line(
        name="Paneer Tikka Singh", phone="7780039811", language="pa"
    )
    assert "Paneer Tikka Singh, P-A-N-E-E-R T-I-K-K-A S-I-N-G-H" in line
    assert "seven, seven, eight, zero, zero, three, nine, eight, one, one" in line
    for indic_digit in ("ਜ਼ੀਰੋ", "ਸੱਤ", "ਅੱਠ", "ज़ीरो", "सात", "੭", "७"):
        assert indic_digit not in line
    assert not any(ch.isdigit() for ch in line)


def test_contact_readback_line_language_variants():
    # Only the lead-in follows the customer's language; Punjabi is the default
    # for pa / mixed / unknown, like order_placed_goodbye.
    for lang in (None, "pa", "mixed"):
        assert "ਦੁਹਰਾ ਦਿੰਦੀ ਹਾਂ" in contact_readback_line(
            name="Aman", phone="7804441234", language=lang
        )
    assert "Let me just repeat" in contact_readback_line(
        name="Aman", phone="7804441234", language="en"
    )
    assert "दोहरा देती हूँ" in contact_readback_line(
        name="Aman", phone="7804441234", language="hi"
    )
    # Accepts the CustomerLanguage enum as well as a bare string.
    assert "Let me just repeat" in contact_readback_line(
        name="Aman", phone="7804441234", language=CustomerLanguage.ENGLISH
    )


def test_contact_readback_line_satisfies_the_confirm_verifier():
    # The code line is what feeds the confirm-time gate, so it must pass the
    # verifier by construction — that is what makes the deadlock unreachable.
    from restaurant.agent.readback_verify import verify_contact_readback

    cart = OrderCart()
    cart.customer_name = "Paneer Tikka Singh"
    cart.customer_phone = "7780039811"
    line = contact_readback_line(
        name=cart.customer_name, phone=cart.customer_phone, language="pa"
    )
    assert verify_contact_readback(line, cart).ok
