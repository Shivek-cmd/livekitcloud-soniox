"""Tests for conversation intent, templates, and order flow guidance."""

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    UserIntent,
    detect_intent,
    format_order_readback,
    format_order_status,
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


def test_detect_order_status_not_misread_as_add():
    # Live-call regression (PR 042): this exact utterance was classified
    # add_item because _ADD_RE matches the bare word "ਆਰਡਰ", which routed
    # the LLM into freeform generation and it hallucinated a wrong item.
    assert (
        detect_intent("ਮੇਰਾ ਆਰਡਰ ਦੱਸੋ, ਕੀ ਹੈਗਾ ਹੁਣ ਤੱਕਰ? ਕੀ ਆਰਡਰ ਕੀਤਾ ਜੀ ਮੈਂ?")
        == UserIntent.ASK_ORDER_STATUS
    )
    assert detect_intent("what's my order so far?") == UserIntent.ASK_ORDER_STATUS
    assert detect_intent("what did I order?") == UserIntent.ASK_ORDER_STATUS


def test_order_status_does_not_block_genuine_add():
    assert detect_intent("ਆਰਡਰ ਕਰ ਦਿਓ ਗਾਰਲਿਕ ਨਾਨ") == UserIntent.ADD_ITEM


def test_restated_item_after_no_no_is_add_not_confirm_no():
    # Live-call regression (PR 042): caller corrects a missed item by
    # restating it after "ਨਹੀਂ ਨਹੀਂ" (no no); this used to be swallowed as
    # CONFIRM_NO (interpreted as "no allergies") and the item never got
    # added, forcing the caller to repeat it three times.
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ, ਬਟਰ ਨਾਨ ਕਰੋ") == UserIntent.ADD_ITEM


def test_gurmukhi_add_loanword_detected():
    # "ਐਡ" is the common Gurmukhi spelling of the English loanword "add".
    assert detect_intent("ਬਟਰ ਨਾਨ ਐਡ ਕਰੋ") == UserIntent.ADD_ITEM


def test_plain_negation_without_item_still_confirm_no():
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ") == UserIntent.CONFIRM_NO
    assert detect_intent("nahi") == UserIntent.CONFIRM_NO


def test_format_order_status():
    cart = OrderCart()
    assert format_order_status(cart) == "Your order is empty so far."

    cart.add_item({"name": "Amritsari Fish", "voice_line": "Amritsari Fish", "price": 15.0}, 1)
    status = format_order_status(cart, include_price=False)
    assert "Amritsari Fish" in status
    assert "dollar" not in status.lower()
    assert "All good" not in status


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
    plan = flow.build_turn_plan("add mango kulfi", UserIntent.ADD_ITEM, cart)
    assert plan.quantity_allowed is True
    assert "SAY EXACTLY" in plan.guidance or "add_to_order" in plan.guidance


def test_quantity_not_allowed_when_explicit_in_utterance():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਮੈਨੂੰ ਇੱਕ ਚਿਕਨ ਟਿੱਕਾ ਚਾਹੀਦਾ",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert plan.quantity_allowed is False
    assert "How many" not in plan.guidance


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
    assert flow.state.phase == OrderPhase.SPECIAL_INSTRUCTIONS
    assert "CHECKOUT STEP" in plan.guidance


def test_phase_advances_after_no_allergy():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()
    plan = flow.build_turn_plan("ਨਹੀਂ, ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ", UserIntent.CONFIRM_NO, cart)
    assert flow.state.special_instructions_done is True
    assert flow.state.phase == OrderPhase.ORDER_TYPE
    assert "CHECKOUT STEP" in plan.guidance


def test_confirming_readback_template():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.READBACK
    plan = flow.build_turn_plan("yes", UserIntent.CONFIRM_YES, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "CHECKOUT STEP" in plan.guidance


def test_want_to_order_asks_pickup_delivery():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਹਾਂ ਜੀ, ਮੈਂ ਕੁਝ ਆਰਡਰ ਕਰਨਾ ਸੀ ਜੀ।",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "pick items first" in plan.guidance.lower() or "Do NOT ask pickup" in plan.guidance


def test_readback_before_name():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.READBACK
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
    assert "CHECKOUT STEP" in plan.guidance


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


def test_sanitize_strips_price_on_web():
    raw = (
        "ਠੀਕ ਹੈ ਜੀ — ਇਕ ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ, ਇਕ ਸਰ੍ਹੋਂ ਦਾ ਸਾਗ, "
        "ਤੇ ਦੋ ਬਟਰ ਨਾਨ, pickup, ਕੁੱਲ ਤਕਰੀਬਨ ਤੀਹ ਡਾਲਰ। ਬਿਲਕੁਲ ਠੀਕ?"
    )
    out = sanitize_assistant_speech(raw, allow_greeting=False, is_phone=False)
    assert "ਡਾਲਰ" not in out
    assert "dollar" not in out.lower()
    assert "ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ" in out
