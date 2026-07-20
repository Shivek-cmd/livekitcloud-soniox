"""Tests for restaurant.agent.replies — status template + canned lines.
(The VERBATIM readback formatter moved to READBACK FACTS in PR 078; the
log-only speech guard was deleted in PR 079.)"""

from restaurant.agent.replies import (
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
