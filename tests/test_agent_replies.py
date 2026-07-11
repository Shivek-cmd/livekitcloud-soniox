"""Tests for restaurant.agent.replies — salvaged formatters + speech guard."""

from restaurant.agent.language import CustomerLanguage
from restaurant.agent.replies import (
    format_add_tool_reply,
    format_order_readback,
    format_order_status,
    format_remove_tool_reply,
    format_update_tool_reply,
    order_placed_goodbye,
    sanitize_assistant_speech,
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


def test_add_tool_reply_no_price_no_meta():
    reply = format_add_tool_reply([(2, "Garlic Naan")])
    assert "two Garlic Naan" in reply
    assert "SAY EXACTLY" in reply
    assert "price" in reply  # the do-NOT instruction
    assert "$" not in reply


def test_update_tool_reply_reads_as_correction():
    reply = format_update_tool_reply(3, "Garlic Naan")
    assert "three Garlic Naan" in reply
    assert "fixed" in reply
    assert "corrected (not added)" in reply


def test_remove_tool_reply():
    reply = format_remove_tool_reply("Garlic Naan")
    assert "removed Garlic Naan" in reply


def test_order_status_grounded():
    status = format_order_status(_cart(), include_price=False)
    assert "one Butter Chicken" in status
    assert "two Garlic Naan" in status
    assert "dollar" not in status

    assert "empty" in format_order_status(OrderCart(), include_price=False)


def test_readback_with_and_without_price():
    cart = _cart()
    cart.customer_name = "Aman"
    spoken = format_order_readback(cart, include_price=False)
    assert spoken.startswith("Okay Aman ji")
    assert "pickup" in spoken
    assert spoken.endswith("All good?")
    assert "dollar" not in spoken

    with_price = format_order_readback(cart, include_price=True)
    assert "dollars" in with_price


def test_readback_empty_cart_is_empty_string():
    assert format_order_readback(OrderCart(), include_price=True) == ""


def test_goodbye_eta_by_order_type():
    assert "20-25" in order_placed_goodbye(order_type="pickup")
    assert "30-40" in order_placed_goodbye(order_type="delivery")


def test_sanitize_strips_mid_call_regreeting():
    out = sanitize_assistant_speech(
        "Hi! I'm Sierra from Bizbull, how can I help?",
        allow_greeting=False,
    )
    assert "Sierra from Bizbull" not in out


def test_sanitize_allows_opening_greeting():
    text = "Sat Sri Akal! Welcome to Bizbull."
    assert sanitize_assistant_speech(text, allow_greeting=True) == text


def test_sanitize_strips_meta_and_price_speech():
    out = sanitize_assistant_speech(
        "I've added Butter Chicken, total about 17 dollars.",
        allow_greeting=False,
    )
    assert "added" not in out.lower()
    assert "dollars" not in out.lower()
