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


def test_checkout_guidance_is_checklist_driven():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.sync_from_cart(cart)
    plan = flow.build_turn_plan("no allergies", UserIntent.CONFIRM_NO, cart)
    # Checkout is now checklist-driven and LLM-led, not a canned muted script.
    assert "Still needed before you can place this order" in plan.guidance
    assert "human host" in plan.guidance
    # The exact fixed question strings are NOT dictated to the LLM.
    assert "Will that be pickup or delivery?" not in plan.guidance


def test_outstanding_requirements_lists_missing_facts():
    from restaurant.order_flow import outstanding_requirements

    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    reqs = outstanding_requirements(cart, flow.state)
    joined = " | ".join(reqs)
    assert "pickup or delivery" in joined
    assert "customer name" in joined
    assert "phone number" in joined

    cart.order_type = "pickup"
    flow.mark_special_instructions_done()
    flow.mark_readback_confirmed()
    cart.customer_name = "Shivek"
    cart.customer_phone = "9413752688"
    assert outstanding_requirements(cart, flow.state) == []


def test_reopen_after_add_invalidates_readback():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Kulfi", "price": 6.0}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.mark_readback_spoken()
    flow.mark_readback_confirmed()
    # A new dish added mid-checkout must force a fresh read-back.
    flow.reopen_after_add()
    assert flow.state.readback_spoken is False
    assert flow.state.readback_confirmed is False


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


def test_correction_guidance_added_when_customer_names_missed_item():
    # Live-call regression (PR 052): caller named ONE missed item after an
    # earlier confirmation. Guidance must tell the LLM not to re-add items
    # already in the cart.
    cart = OrderCart()
    cart.add_item({"name": "Palak Paneer", "voice_line": "Palak Paneer", "price": 16.99}, 1)
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਦਾਲਮਖਨੀ ਵੀ ਕਿਹਾ ਮੈਂ।",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "already confirmed in the cart" in plan.guidance


def test_no_correction_guidance_on_fresh_add():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "add one naan",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "already confirmed in the cart" not in plan.guidance
