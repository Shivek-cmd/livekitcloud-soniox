"""Tests for restaurant.agent.facts — structured tool-reply facts (PR 075)."""

from restaurant.agent.facts import (
    _qty_word,
    format_cart_facts,
    format_contact_readback_facts,
    format_mutation_reply,
    format_readback_facts,
)
from restaurant.orders import CartMutation, OrderCart

_NAAN = {"name": "Garlic Naan", "voice_line": "Garlic Naan", "price": 3.50}
_BC = {"name": "Butter Chicken", "voice_line": "ਬਟਰ ਚਿਕਨ", "price": 13.99}


def _cart() -> OrderCart:
    cart = OrderCart()
    cart.add_item(_BC, 2, note="medium")
    cart.add_item(_NAAN, 1)
    return cart


def test_qty_word():
    assert _qty_word(1) == "one"
    assert _qty_word(10) == "ten"
    assert _qty_word(15) == "15"  # beyond the word table, digits fall through


def test_cart_facts_items_total_and_notes():
    facts = format_cart_facts(_cart())
    assert facts.startswith("ORDER NOW: ")
    assert "2 x ਬਟਰ ਚਿਕਨ (Butter Chicken) [medium]" in facts
    assert "1 x Garlic Naan" in facts
    assert facts.endswith("total=$31.48")


def test_cart_facts_empty_cart():
    assert format_cart_facts(OrderCart()) == "ORDER NOW: empty. total=$0"


def _ready_cart(order_type: str = "pickup") -> OrderCart:
    cart = _cart()
    cart.order_type = order_type
    cart.customer_name = "Aman Singh"
    cart.customer_phone = "7805551234"
    if order_type == "delivery":
        cart.delivery_address = "123 Main St, Apt 4"
    return cart


def test_cart_facts_custom_label():
    facts = format_cart_facts(_cart(), label="ORDER SO FAR")
    assert facts.startswith("ORDER SO FAR: ")


def test_cart_facts_whole_dollar_total():
    cart = OrderCart()
    cart.add_item({"name": "Samosa", "voice_line": "Samosa", "price": 4.0}, 2)
    assert format_cart_facts(cart).endswith("total=$8")


def test_added_reply_has_facts_and_guide():
    cart = _cart()
    mutation = CartMutation(
        kind="added", name="Butter Chicken", voice_line="ਬਟਰ ਚਿਕਨ", quantity=2, note="medium"
    )
    reply = format_mutation_reply(mutation, cart)
    # Gurmukhi voice_line passes through untouched, English name for grounding.
    assert "ADDED: 2 x ਬਟਰ ਚਿਕਨ (Butter Chicken), note: medium." in reply
    assert "ORDER NOW: " in reply
    assert "GUIDE: " in reply
    assert '"two"' in reply  # spoken-quantity hint from _qty_word
    assert "SAY EXACTLY" not in reply


def test_merged_reply_states_new_line_total():
    reply = format_mutation_reply(
        CartMutation(kind="merged", name="Garlic Naan", voice_line="Garlic Naan", quantity=3),
        _cart(),
    )
    assert "ADDED MORE: Garlic Naan is now 3 total." in reply


def test_updated_reply_reads_as_correction_not_add():
    reply = format_mutation_reply(
        CartMutation(kind="updated", name="Garlic Naan", voice_line="Garlic Naan", quantity=3),
        _cart(),
    )
    assert "CORRECTED (not added): Garlic Naan is now 3 total." in reply
    assert "not a second add" in reply
    assert '"three"' in reply


def test_removed_reply():
    reply = format_mutation_reply(
        CartMutation(kind="removed", name="Garlic Naan", voice_line="Garlic Naan"),
        _cart(),
    )
    assert "REMOVED: Garlic Naan." in reply
    assert "removal" in reply


def test_voice_line_identical_to_name_not_duplicated():
    reply = format_mutation_reply(
        CartMutation(kind="added", name="Garlic Naan", voice_line="Garlic Naan", quantity=1),
        _cart(),
    )
    assert "Garlic Naan (Garlic Naan)" not in reply


def test_readback_facts_exclude_contact_details():
    # PR 092 — phone/address are confirmed in their own step, not here.
    facts = format_readback_facts(_ready_cart("delivery"), include_total=False)
    assert "phone" not in facts
    assert "address" not in facts
    assert "name: Aman Singh" in facts


def test_contact_readback_spells_name_and_digits():
    facts = format_contact_readback_facts(_ready_cart())
    assert "A-M-A-N S-I-N-G-H" in facts
    assert "seven, eight, zero, five, five, five, one, two, three, four" in facts
    assert "confirm_contact" in facts
