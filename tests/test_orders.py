"""Tests for OrderCart mutations — additive add vs. corrective update, and the
CartMutation facts returns (PR 042 / PR 075)."""

from restaurant.orders import CartMutation, OrderCart

_FISH = {"name": "Amritsari Fish", "voice_line": "Amritsari Fish", "price": 15.0}


def test_add_item_returns_added_mutation():
    cart = OrderCart()
    mutation = cart.add_item(_FISH, 2, note="medium")
    assert isinstance(mutation, CartMutation)
    assert mutation.kind == "added"
    assert mutation.name == "Amritsari Fish"
    assert mutation.voice_line == "Amritsari Fish"
    assert mutation.quantity == 2
    assert mutation.note == "medium"


def test_add_item_is_additive_and_merges():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    mutation = cart.add_item(_FISH, 1)
    assert cart.items[0].quantity == 2
    assert isinstance(mutation, CartMutation)
    assert mutation.kind == "merged"
    assert mutation.quantity == 2  # resulting line total


def test_add_item_unavailable_returns_refusal_string():
    cart = OrderCart()
    reply = cart.add_item(dict(_FISH, unavailable=True), 1)
    assert isinstance(reply, str)
    assert "not available" in reply
    assert cart.is_empty


def test_update_item_quantity_sets_absolute_value():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    cart.add_item(_FISH, 1)  # cart now has qty 2, customer meant 1
    mutation = cart.update_item_quantity("Amritsari Fish", 1)
    assert cart.items[0].quantity == 1
    assert isinstance(mutation, CartMutation)
    assert mutation.kind == "updated"
    assert mutation.quantity == 1


def test_update_item_quantity_does_not_compound():
    cart = OrderCart()
    cart.add_item(_FISH, 2)
    cart.update_item_quantity("Amritsari Fish", 1)
    cart.update_item_quantity("Amritsari Fish", 1)
    assert cart.items[0].quantity == 1


def test_update_item_quantity_zero_removes_item():
    cart = OrderCart()
    cart.add_item(_FISH, 2)
    mutation = cart.update_item_quantity("Amritsari Fish", 0)
    assert cart.is_empty
    assert isinstance(mutation, CartMutation)
    assert mutation.kind == "removed"


def test_update_item_quantity_not_found():
    cart = OrderCart()
    reply = cart.update_item_quantity("Amritsari Fish", 1)
    assert isinstance(reply, str)
    assert "not found" in reply.lower()


def test_remove_item_returns_removed_mutation():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    mutation = cart.remove_item("Amritsari Fish")
    assert cart.is_empty
    assert isinstance(mutation, CartMutation)
    assert mutation.kind == "removed"
    assert mutation.voice_line == "Amritsari Fish"


def test_mutations_bump_revision():
    cart = OrderCart()
    cart.add_item(_FISH, 1)
    r1 = cart.revision
    cart.update_item_quantity("Amritsari Fish", 3)
    r2 = cart.revision
    cart.remove_item("Amritsari Fish")
    assert r1 < r2 < cart.revision
