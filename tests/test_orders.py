"""Tests for OrderCart quantity handling — additive add vs. corrective update (PR 042)."""

from restaurant.orders import OrderCart

_FISH = {"name": "Amritsari Fish", "voice_line": "Amritsari Fish", "price": 15.0}


def test_add_item_is_additive():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    cart.add_item(_FISH, 1)
    assert cart.items[0].quantity == 2


def test_update_item_quantity_sets_absolute_value():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    cart.add_item(_FISH, 1)  # cart now has qty 2, customer meant 1
    reply = cart.update_item_quantity("Amritsari Fish", 1)
    assert cart.items[0].quantity == 1
    assert "SAY EXACTLY" in reply
    assert "fixed" in reply.lower()


def test_update_item_quantity_does_not_compound():
    cart = OrderCart()
    cart.add_item(_FISH, 2)
    cart.update_item_quantity("Amritsari Fish", 1)
    cart.update_item_quantity("Amritsari Fish", 1)
    assert cart.items[0].quantity == 1


def test_update_item_quantity_zero_removes_item():
    cart = OrderCart()
    cart.add_item(_FISH, 2)
    cart.update_item_quantity("Amritsari Fish", 0)
    assert cart.is_empty


def test_update_item_quantity_not_found():
    cart = OrderCart()
    reply = cart.update_item_quantity("Amritsari Fish", 1)
    assert "not found" in reply.lower()
