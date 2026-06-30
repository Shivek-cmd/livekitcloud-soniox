"""Tests for conversation intent, templates, and order flow guidance."""

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    UserIntent,
    detect_intent,
    format_order_readback,
    format_price_reply,
    is_confirm_yes,
    is_likely_pickup_stt,
    resolve_intent,
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


def test_pickup_not_add_item():
    assert detect_intent("ਚਾਹੀਦਾ pickup") == UserIntent.PICKUP
    assert detect_intent("pick up please") == UserIntent.PICKUP


def test_detect_order_done():
    assert detect_intent("that's it") == UserIntent.ORDER_DONE
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ, ਬਸ") == UserIntent.ORDER_DONE


def test_format_price_reply():
    assert format_price_reply(6.99) == "That's about 7 dollars ji."
    assert format_price_reply(13.48) == "That's about 13.48 dollars ji."


def test_format_order_readback():
    cart = OrderCart()
    cart.add_item(
        {
            "name": "Paneer Tikka",
            "voice_line": "Paneer Tikka",
            "price": 14.99,
        },
        1,
        note="medium",
    )
    cart.add_item(
        {"name": "Gulab Jamun", "voice_line": "ਗੁਲਾਬ ਜਾਮੁਨ", "price": 6.99},
        2,
    )
    cart.order_type = "pickup"
    cart.customer_name = "Shivek"
    line = format_order_readback(cart)
    assert "one Paneer Tikka (medium)" in line
    assert "two ਗੁਲਾਬ ਜਾਮੁਨ" in line
    assert "pickup" in line
    assert "All good?" in line
    assert " ik " not in f" {line.lower()} "
    assert " do " not in f" {line.lower()} "


def test_sanitize_removes_regreeting():
    raw = "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! How can I help?"
    out = sanitize_assistant_speech(raw, allow_greeting=False)
    assert "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" not in out
    assert out


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
    assert "SAY EXACTLY" in plan.guidance or "add_to_order" in plan.guidance


def test_multi_item_add_guidance():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "add one gulab jamun and one kheer",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "listed 2 items" in plan.guidance
    assert "Do NOT ask what the second item is" in plan.guidance
    assert "Anything else?" in plan.guidance


def test_order_done_uses_allergies_template():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("that's all", UserIntent.ORDER_DONE, cart)
    assert ALLERGIES_QUESTION in plan.guidance
    assert "special instructions" in plan.guidance


def test_phase_advances_after_no_allergy():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()
    plan = flow.build_turn_plan("ਨਹੀਂ, ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ", UserIntent.CONFIRM_NO, cart)
    assert flow.state.special_instructions_done is True
    assert flow.state.phase == OrderPhase.ORDER_TYPE
    assert "pickup or delivery" in plan.guidance.lower()


def test_no_no_advances_allergies_loop():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.build_turn_plan("that's all", UserIntent.ORDER_DONE, cart)
    assert flow.state.allergies_asked is True
    intent = resolve_intent("No, no.", phase="special_instructions")
    assert intent == UserIntent.CONFIRM_NO
    plan = flow.build_turn_plan("No, no.", intent, cart)
    assert flow.state.special_instructions_done is True
    assert flow.state.phase == OrderPhase.ORDER_TYPE
    assert "pickup or delivery" in plan.guidance.lower()


def test_confirming_readback_template():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.CONFIRMING
    plan = flow.build_turn_plan("yes", UserIntent.CONFIRM_YES, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "name for the order" in plan.guidance.lower() or "ਆਰਡਰ ਲਈ" in plan.guidance


def test_want_to_order_asks_pickup_delivery():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਹਾਂ ਜੀ, ਮੈਂ ਕੁਝ ਆਰਡਰ ਕਰਨਾ ਸੀ ਜੀ।",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "Will that be pickup or delivery?" in plan.guidance


def test_readback_before_name():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.CONFIRMING
    assert flow.state.readback_confirmed is False


def test_ikk_cup_pickup_at_order_type():
    assert resolve_intent("ਇੱਕ ਕੱਪ?", phase="order_type") == UserIntent.PICKUP
    assert resolve_intent("ਇੱਕ ਅੱਪ।", phase="order_type") == UserIntent.PICKUP
    assert resolve_intent("ਇੱਕ ਕੱਪ, ਆਈ ਸੈਡ।", phase="order_type") == UserIntent.PICKUP
    assert is_likely_pickup_stt("pick up please") is True


def test_confirm_yes_all_good_code_mix():
    assert is_confirm_yes("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ") is True
    assert is_confirm_yes("ਯੇਸ, ਆਲ ਗੁੱਡ") is True
    assert is_confirm_yes("yes all good") is True
    assert resolve_intent("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ") == UserIntent.CONFIRM_YES


def test_confirming_advances_on_all_good():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    plan = flow.build_turn_plan("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ", UserIntent.GENERAL, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "Do NOT repeat the order" in plan.guidance or "name" in plan.guidance.lower()


def test_readback_without_price_on_phone():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    line = format_order_readback(cart, include_price=False)
    assert "dollar" not in line.lower()
    assert "All good?" in line
    assert "pickup" in line


def test_sanitize_strips_price_on_phone():
    raw = "Okay — one Kulfi, pickup, total about 33 dollars. All good?"
    out = sanitize_assistant_speech(raw, allow_greeting=False, is_phone=True)
    assert "dollar" not in out.lower()
    assert "33" not in out
