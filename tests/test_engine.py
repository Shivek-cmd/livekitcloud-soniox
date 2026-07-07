"""Proof tests for the deterministic order engine.

These lock the guarantees the old free-form flow could not make: no guessing on
ambiguous words, no invented quantities, confirmation before every add, and a
correction that sets an exact total instead of doubling.
"""

from restaurant.engine import (
    AddRequest,
    Ambiguous,
    Dish,
    NotFound,
    OrderEngine,
    Phase,
    Proposal,
    Resolved,
)

FISH_CURRY = Dish("FISH_CURRY", "Punjabi Fish Curry", "Punjabi Fish Curry", 21.99)
FISH_PAKORA = Dish("FISH_PAKORA", "Amritsari Fish Pakora", "Fish Pakora", 14.99)
PANEER_TIKKA = Dish("PANEER_TIKKA", "Paneer Tikka", "Paneer Tikka", 16.0, has_spice=True)


class FakeResolver:
    """Mimics the real matcher's behaviour: exact -> Resolved, a bare 'fish'
    (two dishes) -> Ambiguous, nonsense -> NotFound."""

    def resolve(self, query):
        q = query.strip().lower()
        if q in ("fish", "ਮੱਛੀ", "machhi"):
            return Ambiguous("fish", (FISH_CURRY, FISH_PAKORA))
        if "fish curry" in q or q == "punjabi fish curry":
            return Resolved(FISH_CURRY, 1.0)
        if "fish pakora" in q or q == "amritsari fish pakora":
            return Resolved(FISH_PAKORA, 1.0)
        if "paneer" in q:
            return Resolved(PANEER_TIKKA, 1.0)
        return NotFound(query)


def _engine():
    return OrderEngine(FakeResolver(), delivery_charge=5.0)


def _kinds(actions):
    return [a.kind for a in actions]


# --------------------------------------------------------------------------- #
# The exact live bug: "one fish" must NOT become dishes + quantities.
# --------------------------------------------------------------------------- #
def test_ambiguous_fish_asks_which_one_and_adds_nothing():
    eng = _engine()
    acts = eng.handle(Proposal(adds=[AddRequest("fish", quantity=1)]))
    assert _kinds(acts) == ["clarify"]
    assert set(acts[0].data["options"]) == {"Punjabi Fish Curry", "Fish Pakora"}
    assert eng.lines == []            # nothing added
    assert eng.phase == Phase.CLARIFY_ITEM


def test_clarify_then_confirm_then_commit_single_item():
    eng = _engine()
    eng.handle(Proposal(adds=[AddRequest("fish", quantity=1)]))     # -> clarify
    acts = eng.handle(Proposal(choice="fish curry", quantity_answer=1))
    assert _kinds(acts) == ["confirm_item"]
    assert acts[0].data == {"dish": "Punjabi Fish Curry", "quantity": 1}
    assert eng.lines == []            # STILL not added — awaiting yes
    acts = eng.handle(Proposal(yes=True))
    assert "item_added" in _kinds(acts)
    assert len(eng.lines) == 1 and eng.lines[0].dish.id == "FISH_CURRY"
    assert eng.lines[0].quantity == 1


def test_quantity_is_never_invented():
    eng = _engine()
    acts = eng.handle(Proposal(adds=[AddRequest("fish curry", quantity=None)]))
    assert _kinds(acts) == ["ask_quantity"]      # asks, does not assume 1 or 2
    assert eng.lines == []
    acts = eng.handle(Proposal(quantity_answer=2))
    assert _kinds(acts) == ["confirm_item"]
    assert acts[0].data["quantity"] == 2


def test_saying_no_discards_the_staged_item():
    eng = _engine()
    eng.handle(Proposal(adds=[AddRequest("fish curry", quantity=1)]))  # -> confirm
    acts = eng.handle(Proposal(no=True))
    assert "cancelled_item" in _kinds(acts)
    assert eng.lines == []


def test_not_on_menu_adds_nothing():
    eng = _engine()
    acts = eng.handle(Proposal(adds=[AddRequest("unicorn burger", quantity=1)]))
    assert _kinds(acts) == ["not_on_menu"]
    assert eng.lines == []


# --------------------------------------------------------------------------- #
# Correction vs add — can never double.
# --------------------------------------------------------------------------- #
def test_correction_sets_exact_total_not_additive():
    eng = _engine()
    eng.handle(Proposal(adds=[AddRequest("fish curry", quantity=1)]))
    eng.handle(Proposal(yes=True))
    assert eng.lines[0].quantity == 1
    acts = eng.handle(Proposal(corrections=[("fish curry", 2)]))
    assert "quantity_corrected" in _kinds(acts)
    assert eng.lines[0].quantity == 2          # exactly 2, not 1+2=3
    assert len(eng.lines) == 1                 # no new line created


# --------------------------------------------------------------------------- #
# Spice is a guaranteed step for spice dishes.
# --------------------------------------------------------------------------- #
def test_spice_dish_forces_spice_question():
    eng = _engine()
    eng.handle(Proposal(adds=[AddRequest("paneer tikka", quantity=1)]))
    acts = eng.handle(Proposal(yes=True))       # confirm the item
    assert _kinds(acts) == ["ask_spice"]
    assert len(eng.lines) == 1
    acts = eng.handle(Proposal(choice="medium"))
    assert "item_added" in _kinds(acts)
    assert eng.lines[0].note == "medium"


# --------------------------------------------------------------------------- #
# Full happy path, end to end.
# --------------------------------------------------------------------------- #
def test_full_order_happy_path():
    eng = _engine()
    eng.handle(Proposal(adds=[AddRequest("fish curry", quantity=1)]))
    eng.handle(Proposal(yes=True))                       # item committed
    acts = eng.handle(Proposal(done_adding=True))
    assert eng.phase == Phase.ASK_ALLERGIES
    acts = eng.handle(Proposal(no=True, choice=""))      # no allergies
    assert eng.phase == Phase.ASK_ORDER_TYPE
    acts = eng.handle(Proposal(order_type="pickup"))
    assert eng.phase == Phase.READBACK
    assert acts[-1].kind == "readback"
    assert acts[-1].data["items"] == [{"dish": "Punjabi Fish Curry", "quantity": 1, "note": ""}]
    acts = eng.handle(Proposal(yes=True))                # confirm read-back
    assert eng.phase == Phase.ASK_NAME
    eng.handle(Proposal(name="Sandeep"))
    assert eng.phase == Phase.ASK_PHONE
    acts = eng.handle(Proposal(phone="9413752688"))
    assert eng.phase == Phase.PLACED
    assert acts[-1].kind == "order_placed"
    assert eng.name == "Sandeep" and eng.phone == "9413752688"
    assert eng.total() == 21.99


def test_unclear_utterance_asks_repeat_never_acts():
    eng = _engine()
    acts = eng.handle(Proposal(understood=False))
    assert _kinds(acts) == ["repeat"]
    assert eng.lines == []
