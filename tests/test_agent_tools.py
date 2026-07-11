"""Tests for restaurant.agent.core tools — validation at the tool boundary.

The agent is constructed without a session; tools are called as plain async
methods via asyncio.run. The menu layer is faked through monkeypatching
restaurant.menu_provider (core calls it as a module attribute).
"""

import asyncio

import pytest

from restaurant import menu_provider
from restaurant.agent.core import RestaurantAgent

# ── fake menu ─────────────────────────────────────────────────────────────────

_MENU = {
    "butter chicken": {
        "name": "Butter Chicken",
        "voice_line": "Butter Chicken",
        "price": 13.99,
        "clover_item_id": "bc1",
        "match_confidence": 0.95,
    },
    "garlic naan": {
        "name": "Garlic Naan",
        "voice_line": "Garlic Naan",
        "price": 3.50,
        "clover_item_id": "gn1",
        "match_confidence": 0.95,
    },
    "curry combo": {
        "name": "Curry Combo",
        "voice_line": "Curry Combo",
        "price": 15.99,
        "clover_item_id": "cc1",
        "match_confidence": 0.95,
    },
    "gulab jamun": {
        "name": "Gulab Jamun",
        "voice_line": "Gulab Jamun",
        "price": 5.99,
        "clover_item_id": "gj1",
        "match_confidence": 0.95,
        "unavailable": True,
    },
}

_SPICED = {"Butter Chicken"}
_REQUIRED_GROUPS = {"cc1": ["Choose Curry"]}
_AMBIGUOUS = {
    "fish": [
        {"name": "Fish Curry", "voice_line": "Fish Curry"},
        {"name": "Fish Pakora", "voice_line": "Fish Pakora"},
    ],
    "jamun": [{"name": "Gulab Jamun", "voice_line": "Gulab Jamun"}],
}


@pytest.fixture()
def agent(monkeypatch) -> RestaurantAgent:
    monkeypatch.setattr(menu_provider, "extract_dish_query", lambda text: None)
    monkeypatch.setattr(
        menu_provider,
        "find_item",
        lambda name: dict(_MENU[name.lower().strip()]) if name.lower().strip() in _MENU else None,
    )
    monkeypatch.setattr(
        menu_provider,
        "disambiguation_options",
        lambda name, limit=3: [dict(o) for o in _AMBIGUOUS.get(name.lower().strip(), [])][:limit],
    )
    monkeypatch.setattr(menu_provider, "item_has_spice_level", lambda name: name in _SPICED)
    monkeypatch.setattr(
        menu_provider,
        "required_modifier_groups",
        lambda item_id: list(_REQUIRED_GROUPS.get(item_id, [])),
    )
    return RestaurantAgent(is_phone=True)


def run(coro):
    return asyncio.run(coro)


# ── add_item ──────────────────────────────────────────────────────────────────

def test_add_happy_path_uses_resolved_payload(agent):
    result = run(agent.add_item("garlic naan", quantity=2))
    assert "INTERNAL: item saved" in result
    assert len(agent.cart.items) == 1
    line = agent.cart.items[0]
    # Price comes from the resolved menu payload, never from the LLM.
    assert line.name == "Garlic Naan"
    assert line.price == 3.50
    assert line.quantity == 2
    assert line.clover_item_id == "gn1"


def test_ambiguous_returns_options_and_cart_unchanged(agent):
    result = run(agent.add_item("fish"))
    assert "AMBIGUOUS" in result
    assert "Fish Curry" in result and "Fish Pakora" in result
    assert "do NOT" in result
    assert agent.cart.is_empty


def test_single_option_asks_yes_no(agent):
    result = run(agent.add_item("jamun"))
    assert "AMBIGUOUS" in result
    assert "Gulab Jamun" in result
    assert agent.cart.is_empty


def test_not_found_never_invents(agent):
    result = run(agent.add_item("lasagna"))
    assert "NOT FOUND" in result
    assert "invent" in result
    assert agent.cart.is_empty


def test_unavailable_item_refused(agent):
    result = run(agent.add_item("gulab jamun"))
    assert "not available" in result
    assert agent.cart.is_empty


def test_low_confidence_match_asks_first(agent, monkeypatch):
    low = dict(_MENU["garlic naan"], match_confidence=0.6)
    monkeypatch.setattr(menu_provider, "find_item", lambda name: dict(low))
    monkeypatch.setattr(menu_provider, "disambiguation_options", lambda name, limit=3: [])
    result = run(agent.add_item("garlic non"))
    assert "AMBIGUOUS" in result
    assert agent.cart.is_empty


def test_spice_refusal_then_retry_with_spice_succeeds(agent):
    result = run(agent.add_item("butter chicken"))
    assert "NEEDS SPICE" in result
    assert "Mild, Medium, Spicy" in result
    assert agent.cart.is_empty

    result = run(agent.add_item("butter chicken", spice_level="Medium"))
    assert "INTERNAL: item saved" in result
    assert agent.cart.items[0].note == "medium"


def test_invalid_spice_value_refused(agent):
    result = run(agent.add_item("butter chicken", spice_level="volcanic"))
    assert "INVALID SPICE" in result
    assert agent.cart.is_empty


def test_spice_written_into_note_with_user_note(agent):
    run(agent.add_item("butter chicken", spice_level="extra spicy", note="no onions"))
    assert agent.cart.items[0].note == "extra spicy, no onions"


def test_required_group_refused_without_note(agent):
    result = run(agent.add_item("curry combo"))
    assert "NEEDS INFO" in result
    assert "Choose Curry" in result
    assert agent.cart.is_empty

    result = run(agent.add_item("curry combo", note="butter chicken curry"))
    assert "INTERNAL: item saved" in result


def test_quantity_clamped(agent):
    run(agent.add_item("garlic naan", quantity=0))
    assert agent.cart.items[0].quantity == 1
    run(agent.remove_item("garlic naan"))
    run(agent.add_item("garlic naan", quantity=500))
    assert agent.cart.items[0].quantity == 20


# ── set_item_quantity / remove_item / set_item_spice ─────────────────────────

def test_set_item_quantity_is_exact_not_additive(agent):
    run(agent.add_item("garlic naan", quantity=2))
    result = run(agent.set_item_quantity("garlic naan", 3))
    assert "corrected" in result
    assert agent.cart.items[0].quantity == 3


def test_set_item_quantity_zero_removes(agent):
    run(agent.add_item("garlic naan"))
    run(agent.set_item_quantity("garlic naan", 0))
    assert agent.cart.is_empty


def test_set_item_quantity_unknown_item(agent):
    result = run(agent.set_item_quantity("samosa", 2))
    assert "not in the order" in result


def test_remove_item(agent):
    run(agent.add_item("garlic naan"))
    result = run(agent.remove_item("naan"))
    assert "removed" in result
    assert agent.cart.is_empty


def test_set_item_spice_rewrites_note(agent):
    run(agent.add_item("butter chicken", spice_level="Medium", note="no onions"))
    result = run(agent.set_item_spice("butter chicken", "Spicy"))
    assert "spice updated" in result
    assert agent.cart.items[0].note == "spicy, no onions"


def test_set_item_spice_invalid_value(agent):
    run(agent.add_item("butter chicken", spice_level="Medium"))
    result = run(agent.set_item_spice("butter chicken", "nuclear"))
    assert "INVALID SPICE" in result
    assert agent.cart.items[0].note == "medium"


# ── checkout detail tools ─────────────────────────────────────────────────────

def test_set_order_type_validates_literal(agent):
    assert "must be" in run(agent.set_order_type("drive-through"))
    assert agent.cart.order_type is None
    result = run(agent.set_order_type("delivery"))
    assert "address" in result
    assert agent.cart.order_type == "delivery"


def test_set_delivery_address_rejects_junk(agent):
    result = run(agent.set_delivery_address("here"))
    assert "does not look like" in result
    assert agent.cart.delivery_address is None
    result = run(agent.set_delivery_address("123 Main Street NW, Edmonton"))
    assert "saved" in result
    assert agent.cart.delivery_address == "123 Main Street NW, Edmonton"


def test_contact_rejects_junk_name(agent):
    result = run(agent.set_customer_contact(name="pickup"))
    assert "does not look like a real name" in result
    assert not agent.cart.customer_name


def test_contact_rejects_nine_digit_phone(agent):
    result = run(agent.set_customer_contact(phone="123456789"))
    assert "NOT saved" in result
    assert not agent.cart.customer_phone


def test_contact_accepts_ten_digit_phone(agent):
    result = run(agent.set_customer_contact(phone="780-555-1234"))
    assert agent.cart.customer_phone == "7805551234"
    # Read-back guidance uses English word digits.
    assert "seven, eight, zero" in result


def test_contact_accepts_eleven_digits_with_leading_one(agent):
    run(agent.set_customer_contact(phone="1 780 555 1234"))
    assert agent.cart.customer_phone == "7805551234"


def test_contact_saves_valid_name(agent):
    result = run(agent.set_customer_contact(name="Aman Singh"))
    assert "Name saved" in result
    assert agent.cart.customer_name == "Aman Singh"


def test_record_allergies_none_and_note(agent):
    result = run(agent.record_allergies("no"))
    assert agent.state.allergies_recorded
    assert agent.state.allergy_note == ""
    assert "none" in result

    result = run(agent.record_allergies("peanut allergy"))
    assert agent.state.allergy_note == "peanut allergy"
    assert "peanut allergy" in result


# ── readback / confirm cycle ──────────────────────────────────────────────────

def _complete_order(agent):
    run(agent.add_item("garlic naan", quantity=2))
    run(agent.record_allergies("no"))
    run(agent.set_order_type("pickup"))
    run(agent.set_customer_contact(name="Aman Singh"))
    run(agent.set_customer_contact(phone="7805551234"))


def test_readback_refuses_while_incomplete(agent):
    run(agent.add_item("garlic naan"))
    result = run(agent.get_order_readback())
    assert "Cannot read back yet" in result
    assert "llerg" in result  # allergies still owed


def test_readback_is_generated_from_cart(agent):
    _complete_order(agent)
    result = run(agent.get_order_readback())
    assert "READ THIS BACK VERBATIM" in result
    assert "two Garlic Naan" in result
    assert "pickup" in result
    # Phone channel: no price in the spoken readback.
    assert "dollar" not in result.lower()


def test_confirm_before_readback_refused(agent):
    _complete_order(agent)
    result = run(agent.confirm_readback())
    assert "No read-back" in result
    assert not agent.state.readback_confirmed


def test_mutation_after_readback_forces_re_readback(agent):
    _complete_order(agent)
    run(agent.get_order_readback())
    # Late add — the readback the customer heard is now stale.
    run(agent.add_item("butter chicken", spice_level="Medium"))
    result = run(agent.confirm_readback())
    assert "changed since the last read-back" in result
    assert not agent.state.readback_confirmed
    # Fresh readback + confirm clears it.
    run(agent.get_order_readback())
    result = run(agent.confirm_readback())
    assert "confirmed" in result.lower()
    assert agent.state.readback_confirmed


def test_web_rpc_mutation_also_invalidates_readback(agent):
    _complete_order(agent)
    run(agent.get_order_readback())
    assert agent.cart.set_quantity_by_id("gn1", 5)  # tap in the web UI
    result = run(agent.confirm_readback())
    assert "changed since the last read-back" in result


def test_order_type_change_invalidates_confirmed_readback(agent):
    _complete_order(agent)
    run(agent.get_order_readback())
    run(agent.confirm_readback())
    run(agent.set_order_type("delivery"))
    result = run(agent.confirm_readback())
    assert "changed since the last read-back" in result


# ── summary ───────────────────────────────────────────────────────────────────

def test_order_summary_grounded_in_cart(agent):
    run(agent.add_item("garlic naan", quantity=2))
    result = run(agent.get_order_summary())
    assert "SAY EXACTLY" in result
    assert "two Garlic Naan" in result
    assert "Do NOT mention price" in result  # phone channel
