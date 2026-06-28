"""Tests for conversation intent, templates, and order flow guidance."""

from restaurant.conversation import (
    UserIntent,
    detect_intent,
    format_price_reply,
    sanitize_assistant_speech,
)
from restaurant.order_flow import OrderFlowController, OrderPhase
from restaurant.orders import OrderCart


def test_detect_price_intent():
    assert detect_intent("how much is butter chicken") == UserIntent.ASK_PRICE
    assert detect_intent("ਕੀਮਤ ਕਿੰਨੀ ਹੈ") == UserIntent.ASK_PRICE


def test_detect_availability_without_add():
    assert detect_intent("do you have gajar halwa") == UserIntent.ASK_AVAILABILITY
    assert detect_intent("ਮਿੱਠੇ ਚ ਕੀ ਹੈ") == UserIntent.ASK_AVAILABILITY


def test_detect_add_intent():
    assert detect_intent("I want to order butter chicken") == UserIntent.ADD_ITEM
    assert detect_intent("ਮੈਨੂੰ ਇੱਕ ਮੈਂਗੋ ਕੁਲਫੀ ਚਾਹੀਦੀ") == UserIntent.ADD_ITEM


def test_detect_order_done():
    assert detect_intent("that's it") == UserIntent.ORDER_DONE


def test_format_price_reply():
    assert format_price_reply(6.99) == "That's about 7 dollars ji."
    assert format_price_reply(13.48) == "That's about 13.48 dollars ji."


def test_sanitize_removes_regreeting():
    raw = "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! How can I help?"
    out = sanitize_assistant_speech(raw, allow_greeting=False)
    assert "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" not in out
    assert out  # still has recovery content


def test_quantity_gate_on_availability():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("do you have gajar halwa", UserIntent.ASK_AVAILABILITY, cart)
    assert "Do NOT ask how many" in plan.guidance
    assert plan.quantity_allowed is False


def test_quantity_allowed_on_add():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("add one mango kulfi", UserIntent.ADD_ITEM, cart)
    assert plan.quantity_allowed is True


def test_price_guidance_one_line():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    flow.note_discussed_item("Mango Kulfi", 6.99)
    plan = flow.build_turn_plan("how much", UserIntent.ASK_PRICE, cart)
    assert "price line" in plan.guidance.lower()
    assert "Do NOT ask quantity" in plan.guidance


def test_phase_advances_after_items_done():
    cart = OrderCart()
    cart.add_item(
        {"name": "Mango Kulfi", "voice_line": "Mango Kulfi", "price": 6.99, "available": True},
        1,
    )
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.SPECIAL_INSTRUCTIONS
