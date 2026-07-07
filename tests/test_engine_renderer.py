"""Stage 4 tests: renderer grounding + a full engine->renderer call simulation.

The renderer must always speak the code-supplied facts (dish voice_lines,
quantities, options, the read-back list) — in English and Punjabi.
"""

from restaurant.engine import AddRequest, OrderEngine, Proposal
from restaurant.engine.core import Action
from restaurant.engine.renderer import render, render_all

from tests.test_engine import FakeResolver


def test_clarify_speaks_both_options_en_and_pa():
    a = Action("clarify", {"options": ["Punjabi Fish Curry", "Fish Pakora"]})
    en = render(a, "en")
    pa = render(a, "pa")
    assert "Punjabi Fish Curry" in en and "Fish Pakora" in en and "which one" in en.lower()
    assert "Punjabi Fish Curry" in pa and "ਕਿਹੜਾ" in pa


def test_confirm_item_grounded():
    a = Action("confirm_item", {"dish": "Punjabi Fish Curry", "quantity": 2})
    assert render(a, "en") == "two Punjabi Fish Curry — is that right?"
    assert "ਦੋ" in render(a, "pa") and "Punjabi Fish Curry" in render(a, "pa")


def test_readback_lists_every_item():
    a = Action("readback", {
        "items": [
            {"dish": "Punjabi Fish Curry", "quantity": 1, "note": ""},
            {"dish": "Butter Naan", "quantity": 2, "note": ""},
        ],
        "order_type": "pickup", "name": "Sandeep", "total": 30.0,
    })
    en = render(a, "en")
    assert "one Punjabi Fish Curry" in en and "two Butter Naan" in en
    assert "pickup" in en and "Sandeep" in en and "All good" in en
    # no dollar amount is spoken (phone rule): total is data, never voiced here
    assert "30" not in en and "$" not in en


def test_ask_quantity_and_repeat():
    assert "How many" in render(Action("ask_quantity", {"dish": "Butter Naan"}), "en")
    assert render(Action("repeat"), "en").lower().startswith("sorry")


def test_full_call_produces_sensible_speech():
    """Drive a whole order and check the spoken side reads like a real cashier."""
    eng = OrderEngine(FakeResolver(), delivery_charge=5.0)

    def say(p):
        return render_all(eng.handle(p), "en")

    # caller: "one fish" -> must ask which, add nothing
    line = say(Proposal(adds=[AddRequest("fish", quantity=1)]))
    assert "which one" in line.lower()
    assert eng.lines == []

    # caller picks fish curry -> confirm
    line = say(Proposal(choice="fish curry", quantity_answer=1))
    assert line == "one Punjabi Fish Curry — is that right?"

    # caller: yes -> added + anything else
    line = say(Proposal(yes=True))
    assert "Got it" in line and "Anything else" in line
    assert len(eng.lines) == 1

    # caller: done -> allergies
    line = say(Proposal(done_adding=True))
    assert "allergies" in line.lower()

    # no allergies -> pickup/delivery
    line = say(Proposal(no=True))
    assert "Pickup or delivery" in line

    # pickup -> readback
    line = say(Proposal(order_type="pickup"))
    assert "one Punjabi Fish Curry" in line and "All good" in line

    # yes -> ask name
    line = say(Proposal(yes=True))
    assert "name" in line.lower()

    say(Proposal(name="Sandeep"))
    line = say(Proposal(phone="9413752688"))
    assert "order's in" in line.lower()
    assert eng.phase.value == "placed"
