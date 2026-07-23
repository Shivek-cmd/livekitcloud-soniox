"""Tests for restaurant.agent.core tools — validation at the tool boundary.

The agent is constructed without a session; tools are called as plain async
methods via asyncio.run. The menu layer is faked through monkeypatching
restaurant.menu_provider (core calls it as a module attribute).
"""

import asyncio

import pytest

from restaurant import menu_provider
from restaurant.agent import core
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
    assert "ADDED: 2 x Garlic Naan" in result
    assert "ORDER NOW: " in result and "GUIDE: " in result
    assert "SAY EXACTLY" not in result
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


def test_phonetic_only_ascii_single_token_routes_to_clarify(agent, monkeypatch):
    # PR 084 (Gap 7): the matcher caps a lone-Roman-word phonetic-only hit
    # (e.g. "butter"→Bhatura) to 0.65, below the add gate. _resolve_menu_item
    # must then route it through the "did you mean?" clarify path, cart intact.
    bhatura = {
        "name": "Bhatura",
        "voice_line": "Bhatura",
        "price": 2.99,
        "clover_item_id": "bh1",
        "match_confidence": 0.65,
    }
    monkeypatch.setattr(menu_provider, "find_item", lambda name: dict(bhatura))
    monkeypatch.setattr(menu_provider, "disambiguation_options", lambda name, limit=3: [])
    result = run(agent.add_item("butter"))
    assert "AMBIGUOUS" in result
    assert result.startswith("⛔ NOTHING WAS ADDED — CART UNCHANGED. ")
    assert agent.cart.is_empty


def test_add_without_spice_succeeds_spice_unset(agent):
    result = run(agent.add_item("butter chicken"))
    assert "ADDED: 1 x Butter Chicken" in result
    assert "NEEDS SPICE" not in result
    assert agent.cart.items[0].note == ""


def test_spice_at_add_still_passes_through(agent):
    result = run(agent.add_item("butter chicken", spice_level="Medium"))
    assert "ADDED: 1 x Butter Chicken" in result
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
    assert "ADDED: 1 x Curry Combo" in result


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
    assert "CORRECTED (not added): Garlic Naan is now 3 total" in result
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
    assert "REMOVED: Garlic Naan" in result
    assert agent.cart.is_empty


def test_set_item_spice_rewrites_note(agent):
    run(agent.add_item("butter chicken", spice_level="Medium", note="no onions"))
    result = run(agent.set_item_spice("butter chicken", "Spicy"))
    assert "SPICE SET: Butter Chicken is now spicy" in result
    assert agent.cart.items[0].note == "spicy, no onions"


def test_set_item_spice_invalid_value(agent):
    run(agent.add_item("butter chicken", spice_level="Medium"))
    result = run(agent.set_item_spice("butter chicken", "nuclear"))
    assert "INVALID SPICE" in result
    assert agent.cart.items[0].note == "medium"


# ── checkout detail tools ─────────────────────────────────────────────────────

def test_set_order_type_validates_literal(agent):
    run(agent.add_item("garlic naan"))
    run(agent.record_additional_requests("no"))
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


def _ready_for_contact(agent):
    """Advance past the phase gate (items → additional requests → order
    type) so set_customer_contact's own validation can be exercised."""
    run(agent.add_item("garlic naan"))
    run(agent.record_additional_requests("no"))
    run(agent.set_order_type("pickup"))


def test_contact_rejects_junk_name(agent):
    _ready_for_contact(agent)
    result = run(agent.set_customer_contact(name="pickup"))
    assert "NAME NOT SAVED" in result
    assert "does not look like a real name" in result
    assert not agent.cart.customer_name


def test_contact_rejects_nine_digit_phone(agent):
    # PR 082 — a 9-digit fragment is now held as partial progress (buffered for
    # accumulation) rather than discarded; still never saved to the cart.
    _ready_for_contact(agent)
    result = run(agent.set_customer_contact(phone="123456789"))
    assert "PHONE PARTIAL: have 9 of 10 (123456789)" in result
    assert not agent.cart.customer_phone
    assert agent.state.phone_buffer == "123456789"


def test_contact_accepts_ten_digit_phone(agent):
    _ready_for_contact(agent)
    result = run(agent.set_customer_contact(phone="780-444-1234"))
    assert agent.cart.customer_phone == "7804441234"
    # PHONE SAVED fact carries the English word digits the LLM must speak.
    assert "PHONE SAVED" in result
    assert "seven, eight, zero" in result
    # The guide must not read as "make the customer say it".
    assert "do NOT ask the customer to repeat" in result


def test_contact_accepts_eleven_digits_with_leading_one(agent):
    _ready_for_contact(agent)
    run(agent.set_customer_contact(phone="1 780 444 1234"))
    assert agent.cart.customer_phone == "7804441234"


def test_contact_rejects_implausible_phone(agent):
    # 555 exchange / repeated digits are structurally never real NANP
    # numbers — the fabrication backstop for set_customer_contact.
    _ready_for_contact(agent)
    result = run(agent.set_customer_contact(phone="555-123-4567"))
    assert "PHONE NOT SAVED" in result
    assert "does not look like a real phone number" in result
    assert not agent.cart.customer_phone


def test_contact_accumulates_phone_across_calls(agent):
    # PR 082 — the tool now stitches fragments dictated across separate calls
    # instead of replacing (and losing) prior progress.
    _ready_for_contact(agent)
    r1 = run(agent.set_customer_contact(phone="80"))
    assert "PHONE PARTIAL: have 2 of 10 (80)" in r1
    assert not agent.cart.customer_phone
    r2 = run(agent.set_customer_contact(phone="770"))
    assert "PHONE PARTIAL: have 5 of 10 (80770)" in r2
    r3 = run(agent.set_customer_contact(phone="39800"))
    assert "PHONE SAVED" in r3
    assert agent.cart.customer_phone == "8077039800"
    # Buffer cleared once the full number is saved.
    assert agent.state.phone_buffer == ""


def test_contact_saves_valid_name(agent):
    _ready_for_contact(agent)
    result = run(agent.set_customer_contact(name="Aman Singh"))
    assert 'NAME SAVED: "Aman Singh"' in result
    assert agent.cart.customer_name == "Aman Singh"


def test_contact_blocked_before_order_type_set(agent):
    # Direct regression test for the incident: set_customer_contact called
    # before order_type exists must refuse, not fabricate/save anything.
    run(agent.add_item("garlic naan"))
    run(agent.record_additional_requests("no"))
    result = run(agent.set_customer_contact(name="Sir", phone="555-123-4567"))
    assert "Cannot collect contact details yet" in result
    assert not agent.cart.customer_name
    assert not agent.cart.customer_phone


def test_record_additional_requests_none_and_note(agent):
    run(agent.add_item("garlic naan"))
    result = run(agent.record_additional_requests("no"))
    assert agent.state.additional_requests_recorded
    assert agent.state.allergy_note == ""
    assert "none" in result

    result = run(agent.record_additional_requests("peanut allergy"))
    assert agent.state.allergy_note == "peanut allergy"
    assert "peanut allergy" in result


def test_wrapup_defaults_unset_spice_to_medium(agent):
    run(agent.add_item("butter chicken"))
    run(agent.add_item("garlic naan"))
    rev = agent.cart.revision
    result = run(agent.record_additional_requests("no"))
    assert "SPICE DEFAULTED" in result and "Butter Chicken" in result
    assert agent.cart.items[0].note == "medium"  # spiced dish filled
    assert agent.cart.items[1].note == ""  # non-spiced dish untouched
    assert agent.cart.revision == rev + 1  # note change invalidates readbacks


def test_wrapup_never_overwrites_explicit_spice(agent):
    run(agent.add_item("butter chicken", spice_level="Spicy"))
    result = run(agent.record_additional_requests("no allergies"))
    assert "SPICE DEFAULTED" not in result
    assert agent.cart.items[0].note == "spicy"


def test_late_added_spiced_dish_defaulted_at_readback(agent):
    _complete_order(agent)
    run(agent.add_item("butter chicken"))  # after the wrap-up, spice unset
    result = run(agent.get_order_readback())
    assert "READBACK FACTS" in result
    line = next(i for i in agent.cart.items if i.name == "Butter Chicken")
    assert line.note == "medium"


# ── readback / confirm cycle ──────────────────────────────────────────────────

def _complete_order(agent):
    run(agent.add_item("garlic naan", quantity=2))
    run(agent.record_additional_requests("no"))
    run(agent.set_order_type("pickup"))
    run(agent.set_customer_contact(name="Aman Singh"))
    run(agent.set_customer_contact(phone="7804441234"))


def test_readback_refuses_while_incomplete(agent):
    run(agent.add_item("garlic naan"))
    result = run(agent.get_order_readback())
    assert "Cannot read back yet" in result
    assert "record_additional_requests" in result  # wrap-up question still owed


def test_readback_facts_generated_from_cart(agent):
    _complete_order(agent)
    result = run(agent.get_order_readback())
    assert "READBACK FACTS" in result
    assert "2 x Garlic Naan" in result
    assert "order type: pickup" in result
    assert "Aman Singh" in result
    # Phone number read back as English word digits, not saved-tool prose.
    assert "seven, eight, zero, four, four, four, one, two, three, four" in result
    # Phone channel: no price in the readback facts.
    assert "total" not in result.lower() and "$" not in result


def test_set_customer_contact_no_longer_prompts_immediate_phone_readback(agent):
    run(agent.add_item("garlic naan", quantity=2))
    run(agent.record_additional_requests("no"))
    run(agent.set_order_type("pickup"))
    result = run(agent.set_customer_contact(phone="7804441234"))
    assert "PHONE SAVED" in result
    assert "do NOT read it back now" in result
    assert "read back during the order read-back step" in result


def test_readback_facts_include_total_on_web(agent):
    # The agent fixture's menu_provider monkeypatches are module-level — a
    # second (web) agent built here sees the same fake menu.
    web_agent = RestaurantAgent(is_phone=False)
    _complete_order(web_agent)
    result = run(web_agent.get_order_readback())
    assert "total: $" in result


def test_confirm_before_readback_refused(agent):
    _complete_order(agent)
    result = run(agent.confirm_readback())
    assert "No read-back" in result
    assert not agent.state.readback_confirmed


def test_mutation_after_readback_forces_re_readback(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    _complete_order(agent)
    run(agent.get_order_readback())
    # Late add — the readback the customer heard is now stale.
    run(agent.add_item("butter chicken", spice_level="Medium"))
    result = run(agent.confirm_readback())
    assert "changed since the last read-back" in result
    assert not agent.state.readback_confirmed
    # Fresh readback + confirm clears it. Speaking the facts verbatim
    # satisfies the (now default-strict) verifier.
    facts = run(agent.get_order_readback())
    agent.note_agent_speech(facts)
    result = run(agent.confirm_readback())
    assert "ORDER COMPLETE" in result or "Order placed" in result
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


# ── spoken-readback verifier at confirm (PR 078) ──────────────────────────────

_GOOD_READBACK = (
    "So that's two Garlic Naan for pickup, phone seven eight zero four "
    "four four one two three four — is everything correct?"
)


def test_note_agent_speech_buffers_only_while_pending(agent):
    _complete_order(agent)
    agent.note_agent_speech("Anything else for you?")  # before readback
    run(agent.get_order_readback())
    agent.note_agent_speech(_GOOD_READBACK)
    assert agent.state.readback_spoken == [_GOOD_READBACK]
    # A cart mutation voids the in-flight capture.
    run(agent.add_item("butter chicken", spice_level="Medium"))
    assert not agent.state.readback_pending
    assert agent.state.readback_spoken == []


def test_strict_confirm_blocked_until_readback_spoken(agent, monkeypatch):
    monkeypatch.setenv("READBACK_VERIFY", "strict")
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    _complete_order(agent)
    run(agent.get_order_readback())
    # Same-turn readback+confirm: nothing spoken yet → refused.
    result = run(agent.confirm_readback())
    assert "READBACK INCOMPLETE" in result
    assert not agent.state.readback_confirmed
    assert agent.state.readback_pending  # re-read still captured
    # Sloppy readback (item never spoken) → still refused.
    agent.note_agent_speech("So that's your order for pickup, all good?")
    result = run(agent.confirm_readback())
    assert "READBACK INCOMPLETE" in result
    assert "Garlic Naan" in result
    assert not agent.state.readback_confirmed
    # Full spoken readback → confirmed and finalized in the same call.
    agent.note_agent_speech(_GOOD_READBACK)
    result = run(agent.confirm_readback())
    assert "ORDER COMPLETE" in result or "Order placed" in result
    assert agent.state.readback_confirmed
    assert not agent.state.readback_pending
    assert agent.cart.placed


def test_warn_mode_allows_but_records_event(agent, monkeypatch):
    monkeypatch.setenv("READBACK_VERIFY", "warn")
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)

    class _Recorder:
        def __init__(self):
            self.session_id = "sess-1"
            self.events = []

        def log_tool(self, name, args, result):
            pass

        def add_event(self, event_type, payload=None):
            self.events.append((event_type, payload))

        def set_outcome(self, outcome):
            pass

    recorder = _Recorder()
    agent.bind_recorder(recorder)
    _complete_order(agent)
    run(agent.get_order_readback())
    result = run(agent.confirm_readback())  # nothing spoken — warn, allow
    assert "ORDER COMPLETE" in result or "Order placed" in result
    assert agent.state.readback_confirmed
    assert any(e[0] == "readback_verify_warn" for e in recorder.events)


def test_off_mode_skips_verification(agent, monkeypatch):
    monkeypatch.setenv("READBACK_VERIFY", "off")
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    _complete_order(agent)
    run(agent.get_order_readback())
    result = run(agent.confirm_readback())
    assert "ORDER COMPLETE" in result or "Order placed" in result
    assert agent.state.readback_confirmed
    assert agent.state.readback_confirmed


# ── post-refusal false-add-claim verifier (PR 081) ────────────────────────────

_FALSE_CLAIM = "Great choice! I've added one Chana Masala for you."


class _EventRecorder:
    def __init__(self):
        self.events = []

    def log_tool(self, name, args, result):
        pass

    def add_event(self, event_type, payload=None):
        self.events.append((event_type, payload))


def test_refusals_carry_cart_unchanged_marker(agent):
    for query in ("fish", "chana masala", "gulab jamun", "jamun"):
        result = run(agent.add_item(query))
        assert result.startswith("⛔ NOTHING WAS ADDED — CART UNCHANGED. "), query
    assert agent.cart.is_empty


def test_refusal_arms_pending_check(agent):
    run(agent.add_item("chana masala"))
    assert agent.state.pending_add_refusals == ["chana masala"]


def test_successful_mutation_same_turn_disarms(agent):
    run(agent.add_item("chana masala"))
    run(agent.add_item("garlic naan"))
    assert agent.state.pending_add_refusals == []
    # The legitimate confirm for the naan must not be flagged.
    agent.note_agent_speech("I've added one Garlic Naan for you.")
    assert agent._false_add_reanchor is None


def test_strict_hit_sets_reanchor_and_is_one_shot(agent, monkeypatch):
    monkeypatch.delenv("ADD_CLAIM_VERIFY", raising=False)
    recorder = _EventRecorder()
    agent.bind_recorder(recorder)
    run(agent.add_item("chana masala"))
    agent.note_agent_speech(_FALSE_CLAIM)
    assert agent._false_add_reanchor == "chana masala"
    assert agent.state.pending_add_refusals == []
    assert any(e[0] == "false_add_claim" for e in recorder.events)
    # One-shot: a later line is no longer checked.
    agent._false_add_reanchor = None
    agent.note_agent_speech(_FALSE_CLAIM)
    assert agent._false_add_reanchor is None


def test_honest_refusal_speech_passes(agent):
    run(agent.add_item("chana masala"))
    agent.note_agent_speech("Sorry ji, Chana Masala isn't on our menu.")
    assert agent._false_add_reanchor is None
    assert agent.state.pending_add_refusals == []


def test_warn_mode_records_without_reanchor(agent, monkeypatch):
    monkeypatch.setenv("ADD_CLAIM_VERIFY", "warn")
    recorder = _EventRecorder()
    agent.bind_recorder(recorder)
    run(agent.add_item("chana masala"))
    agent.note_agent_speech(_FALSE_CLAIM)
    assert agent._false_add_reanchor is None
    assert any(e[0] == "false_add_claim" for e in recorder.events)


def test_off_mode_skips_check(agent, monkeypatch):
    monkeypatch.setenv("ADD_CLAIM_VERIFY", "off")
    run(agent.add_item("chana masala"))
    agent.note_agent_speech(_FALSE_CLAIM)
    assert agent._false_add_reanchor is None


def test_new_user_turn_disarms_and_injects_reanchor(agent):
    class _TurnCtx:
        def __init__(self):
            self.messages = []

        def add_message(self, *, role, content):
            self.messages.append((role, content))

    class _Msg:
        text_content = "Can I get a butter chicken instead?"

    run(agent.add_item("chana masala"))
    agent._false_add_reanchor = "chana masala"
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg()))
    assert agent.state.pending_add_refusals == []
    assert agent._false_add_reanchor is None
    assert any(
        role == "system" and "RE-ANCHOR" in content and "chana masala" in content
        for role, content in ctx.messages
    )


# ── summary ───────────────────────────────────────────────────────────────────

def test_order_summary_grounded_in_cart(agent):
    run(agent.add_item("garlic naan", quantity=2))
    result = run(agent.get_order_summary())
    assert "ORDER SO FAR (state ONLY these items" in result
    assert "2 x Garlic Naan" in result
    assert "total=$7" in result  # total stays in facts; price policy lives in the prompt
    assert "SAY EXACTLY" not in result


# ── get_recommendations (PR 086) ──────────────────────────────────────────────

def test_get_recommendations_returns_grounded_result(agent, monkeypatch):
    monkeypatch.setattr(menu_provider, "_cache", None)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    result = run(agent.get_recommendations(preference="veg"))
    assert "at most TWO" in result
    assert "(veg)" in result


def test_get_recommendations_empty_records_event(agent, monkeypatch):
    monkeypatch.setattr(
        menu_provider,
        "recommendation_options",
        lambda preference="any", category="", *, limit=4: [],
    )
    recorder = _EventRecorder()
    agent.bind_recorder(recorder)
    result = run(agent.get_recommendations(preference="veg", category="pizza"))
    assert "No matching items" in result
    assert ("recommendations_empty", {"preference": "veg", "category": "pizza"}) in recorder.events
