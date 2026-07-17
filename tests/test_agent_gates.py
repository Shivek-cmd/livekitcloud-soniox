"""Tests for restaurant.agent.gates — place-order blockers + readback staleness."""

from restaurant.agent.gates import (
    OrderSessionState,
    invalidate_readback,
    place_order_blockers,
)
from restaurant.orders import OrderCart

_ITEM = {"name": "Butter Chicken", "voice_line": "Butter Chicken", "price": 13.99}


def _complete_cart() -> OrderCart:
    cart = OrderCart()
    cart.add_item(_ITEM, 1)
    cart.order_type = "pickup"
    cart.customer_name = "Aman"
    cart.customer_phone = "7805551234"
    return cart


def _confirmed_state(cart: OrderCart) -> OrderSessionState:
    state = OrderSessionState()
    state.additional_requests_recorded = True
    state.readback_revision = cart.revision
    state.readback_confirmed = True
    return state


def test_complete_order_has_no_blockers():
    cart = _complete_cart()
    assert place_order_blockers(cart, _confirmed_state(cart)) == []


def test_empty_cart_blocks():
    cart = OrderCart()
    blockers = place_order_blockers(cart, _confirmed_state(cart))
    assert any("empty" in b for b in blockers)


def test_missing_order_type_blocks():
    cart = _complete_cart()
    cart.order_type = None
    blockers = place_order_blockers(cart, _confirmed_state(cart))
    assert any("Pickup or delivery" in b for b in blockers)


def test_delivery_without_address_blocks():
    cart = _complete_cart()
    cart.order_type = "delivery"
    blockers = place_order_blockers(cart, _confirmed_state(cart))
    assert any("address" in b for b in blockers)
    cart.delivery_address = "123 Main Street, Edmonton"
    assert place_order_blockers(cart, _confirmed_state(cart)) == []


def test_invalid_name_blocks():
    cart = _complete_cart()
    cart.customer_name = "pickup"  # checkout token misheard as a name
    blockers = place_order_blockers(cart, _confirmed_state(cart))
    assert any("name" in b for b in blockers)


def test_bad_phone_blocks():
    cart = _complete_cart()
    cart.customer_phone = "123456789"  # 9 digits
    blockers = place_order_blockers(cart, _confirmed_state(cart))
    assert any("phone" in b for b in blockers)


def test_eleven_digit_phone_with_leading_one_ok():
    cart = _complete_cart()
    cart.customer_phone = "17805551234"
    assert place_order_blockers(cart, _confirmed_state(cart)) == []


def test_additional_requests_not_recorded_blocks():
    cart = _complete_cart()
    state = _confirmed_state(cart)
    state.additional_requests_recorded = False
    blockers = place_order_blockers(cart, state)
    assert any("record_additional_requests" in b for b in blockers)


def test_unconfirmed_readback_blocks():
    cart = _complete_cart()
    state = _confirmed_state(cart)
    state.readback_confirmed = False
    blockers = place_order_blockers(cart, state)
    assert any("read back" in b for b in blockers)


def test_cart_mutation_after_readback_blocks_until_reconfirmed():
    cart = _complete_cart()
    state = _confirmed_state(cart)
    assert place_order_blockers(cart, state) == []

    # Late add after the readback — confirmation is now stale.
    cart.add_item({"name": "Garlic Naan", "voice_line": "Garlic Naan", "price": 3.5}, 2)
    invalidate_readback(state)
    assert place_order_blockers(cart, state) != []

    # Re-readback + re-confirm at the new revision clears it.
    state.readback_revision = cart.revision
    state.readback_confirmed = True
    assert place_order_blockers(cart, state) == []


def test_stale_revision_blocks_even_if_confirmed_flag_set():
    # Web-RPC mutation path: revision bumps even when invalidate_readback was
    # never called — the revision check alone must catch it.
    cart = _complete_cart()
    state = _confirmed_state(cart)
    assert not cart.set_quantity_by_id("missing-id", 3)  # no match -> no bump
    assert place_order_blockers(cart, state) == []
    cart.items[0].clover_item_id = "abc"
    assert cart.set_quantity_by_id("abc", 3)
    assert place_order_blockers(cart, state) != []


def test_every_mutation_path_bumps_revision():
    cart = OrderCart()
    r0 = cart.revision
    cart.add_item(_ITEM, 1)
    assert cart.revision == r0 + 1
    cart.add_item(_ITEM, 1)  # merge into existing line still bumps
    assert cart.revision == r0 + 2
    cart.update_item_quantity("Butter Chicken", 3)
    assert cart.revision == r0 + 3
    cart.items[0].clover_item_id = "abc"
    cart.set_quantity_by_id("abc", 2)
    assert cart.revision == r0 + 4
    cart.remove_by_id("abc")
    assert cart.revision == r0 + 5
    cart.add_item(_ITEM, 1)
    cart.remove_item("Butter Chicken")
    assert cart.revision == r0 + 7
