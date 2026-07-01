"""Tests for code-owned order ladder (PR 032)."""

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    PICKUP_DELIVERY_QUESTION,
    UserIntent,
    extract_customer_name,
    extract_phone_digits,
    format_order_readback,
    is_allergies_step_answer,
    resolve_intent,
)
from restaurant.order_flow import OrderFlowController, OrderPhase
from restaurant.orders import OrderCart


def test_no_bas_at_special_instructions_not_order_done():
    assert (
        resolve_intent("No, bas eh karna", phase="special_instructions")
        == UserIntent.CONFIRM_NO
    )
    assert (
        resolve_intent("ਨਹੀਂ ਜੀ, ਬਸ", phase="special_instructions")
        == UserIntent.CONFIRM_NO
    )


def test_i_said_no_at_special_instructions():
    assert (
        resolve_intent("No, no, no, I said no", phase="special_instructions")
        == UserIntent.CONFIRM_NO
    )
    assert resolve_intent("I said no", phase="special_instructions") == UserIntent.CONFIRM_NO


def test_repeated_no_is_allergy_answer():
    assert is_allergies_step_answer("No, no, no", UserIntent.GENERAL) is True


def test_allergy_no_advances_phase():
    cart = OrderCart()
    cart.add_item({"name": "Lassi", "voice_line": "Sweet Lassi", "price": 5}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()
    plan = flow.build_turn_plan("No, bas", UserIntent.CONFIRM_NO, cart)
    assert flow.state.special_instructions_done is True
    assert flow.state.phase == OrderPhase.ORDER_TYPE
    assert "pickup or delivery" in plan.guidance.lower()


def test_order_done_does_not_reask_allergies():
    cart = OrderCart()
    cart.add_item({"name": "Lassi", "voice_line": "Sweet Lassi", "price": 5}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()
    plan = flow.build_turn_plan("bas", UserIntent.CONFIRM_NO, cart)
    assert ALLERGIES_QUESTION not in plan.guidance or "do NOT repeat" in plan.guidance.lower()


def test_readback_spoken_skips_repeat_guidance():
    cart = OrderCart()
    cart.add_item({"name": "Lassi", "voice_line": "Sweet Lassi", "price": 5}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.mark_readback_spoken()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.CONFIRMING
    plan = flow.build_turn_plan("hmm", UserIntent.GENERAL, cart)
    assert flow.state.phase == OrderPhase.CONFIRMING
    assert "do not repeat" in plan.guidance.lower()


def test_phone_readback_no_price():
    cart = OrderCart()
    cart.add_item({"name": "Lassi", "voice_line": "Sweet Lassi", "price": 5.24}, 1)
    cart.add_item({"name": "Nimbu", "voice_line": "Nimbu Pani", "price": 5.24}, 1)
    cart.order_type = "pickup"
    line = format_order_readback(cart, include_price=False)
    assert "dollar" not in line.lower()
    assert "Sweet Lassi" in line or "Lassi" in line
    assert "All good?" in line


def test_extract_name_and_phone():
    assert extract_customer_name("name is Shivik") == "Shivik"
    assert extract_customer_name("ਹਾਂ ਜੀ, name is Shivik,") == "Shivik"
    assert extract_phone_digits("94137 52688") == "9413752688"
    assert extract_phone_digits("ਹਾਂ ਜੀ, 94137 52688.") == "9413752688"


def test_confirm_yes_at_confirming_phase():
    assert resolve_intent("Yes", phase="confirming") == UserIntent.CONFIRM_YES
