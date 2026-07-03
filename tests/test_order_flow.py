"""PR 043 — single-authority order flow phase machine."""

from restaurant.conversation import UserIntent
from restaurant.order_flow import (
    OrderFlowController,
    OrderPhase,
    compute_phase,
)
from restaurant.orders import OrderCart


def test_compute_phase_collecting():
    cart = OrderCart()
    state = OrderFlowController(is_phone=True).state
    assert compute_phase(cart, state) == OrderPhase.BROWSING

    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    assert compute_phase(cart, state) == OrderPhase.AWAITING_MORE


def test_compute_phase_checkout_sequence():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    assert compute_phase(cart, flow.state) == OrderPhase.SPECIAL_INSTRUCTIONS

    flow.mark_special_instructions_done()
    assert compute_phase(cart, flow.state) == OrderPhase.ORDER_TYPE

    cart.order_type = "pickup"
    assert compute_phase(cart, flow.state) == OrderPhase.READBACK

    flow.mark_readback_confirmed()
    assert compute_phase(cart, flow.state) == OrderPhase.CUSTOMER_NAME

    cart.customer_name = "Shivek"
    assert compute_phase(cart, flow.state) == OrderPhase.CUSTOMER_PHONE

    cart.customer_phone = "9413752688"
    assert compute_phase(cart, flow.state) == OrderPhase.READY_TO_PLACE


def test_checkout_guidance_is_code_owned():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.sync_from_cart(cart)
    plan = flow.build_turn_plan("no allergies", UserIntent.CONFIRM_NO, cart)
    assert "CHECKOUT STEP" in plan.guidance
    assert "Will that be pickup or delivery?" not in plan.guidance


def test_menu_miss_stays_collecting():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "add one unicorn burger",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "NOT on menu" in plan.guidance
    assert flow.state.phase in (OrderPhase.BROWSING, OrderPhase.COLLECTING_ITEMS)


def test_confirming_alias_equals_readback():
    assert OrderPhase.CONFIRMING is OrderPhase.READBACK
