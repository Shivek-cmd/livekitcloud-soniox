"""Structured tool-reply facts — the LLM phrases, code owns the data (PR 075).

Mutating tools no longer script speech (SAY EXACTLY). They return three lines:
a fact head (ADDED / CORRECTED / REMOVED / …), an ORDER NOW cart snapshot, and
a GUIDE the LLM follows in its own words. Facts must never be contradicted;
phrasing is the LLM's. `total=` stays in the facts so "how much?" is
answerable without another tool call — the no-price-on-phone policy lives in
the prompt, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from restaurant.orders import CartMutation, OrderCart

_QTY_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def _qty_word(n: int) -> str:
    return _QTY_WORDS.get(n, str(n))


def _money(amount: float) -> str:
    if abs(amount - round(amount)) < 0.001:
        return f"${int(round(amount))}"
    return f"${amount:.2f}"


def _dish_label(name: str, voice_line: str) -> str:
    """voice_line first (that's what gets spoken), English name for grounding."""
    voice = voice_line or name
    if voice == name:
        return voice
    return f"{voice} ({name})"


def format_cart_facts(cart: "OrderCart", *, label: str = "ORDER NOW") -> str:
    """The canonical one-line cart snapshot appended to every mutation reply."""
    if cart.is_empty:
        return f"{label}: empty. total={_money(0)}"
    parts = []
    for item in cart.items:
        part = f"{item.quantity} x {_dish_label(item.name, item.voice_line)}"
        if item.note:
            part += f" [{item.note}]"
        parts.append(part)
    return f"{label}: " + "; ".join(parts) + f". total={_money(cart.total)}"


def _mutation_head(mutation: "CartMutation") -> str:
    label = _dish_label(mutation.name, mutation.voice_line)
    note = f", note: {mutation.note}" if mutation.note else ""
    if mutation.kind == "added":
        return f"ADDED: {mutation.quantity} x {label}{note}."
    if mutation.kind == "merged":
        return (
            f"ADDED MORE: {label} is now {mutation.quantity} total{note}."
        )
    if mutation.kind == "updated":
        return f"CORRECTED (not added): {label} is now {mutation.quantity} total."
    if mutation.kind == "removed":
        return f"REMOVED: {label}."
    return f"{mutation.kind.upper()}: {label}."


def _mutation_guide(mutation: "CartMutation") -> str:
    # Each GUIDE carries a short persona re-anchor (PR 077, 4c): this text sits
    # right next to the generation point, so it steers style far more than the
    # distant system prompt — facts stay facts, the nudge is about delivery.
    qty = _qty_word(mutation.quantity)
    if mutation.kind in ("added", "merged"):
        return (
            "GUIDE: confirm the add in the customer's language — warm and in "
            "your own words, never reading these lines aloud — using the exact "
            f'dish name and quantity above (quantity spoken as "{qty}", '
            "never a digit), then keep the order moving."
        )
    if mutation.kind == "updated":
        return (
            "GUIDE: reassure the customer in their language, in your own "
            f'words, that it is fixed — "{qty}" total, not a second add.'
        )
    return (
        "GUIDE: confirm the removal in the customer's language, warm and "
        "natural, then keep the order moving."
    )


def format_mutation_reply(mutation: "CartMutation", cart: "OrderCart") -> str:
    """Three-line facts reply for add/update/remove tool results."""
    return "\n".join(
        [
            _mutation_head(mutation),
            format_cart_facts(cart),
            _mutation_guide(mutation),
        ]
    )


def format_contact_reply(facts: list[str], guides: list[str]) -> str:
    """Fact line(s) + one merged GUIDE line for set_customer_contact results.

    Same shape as mutation replies — the old prose ("Phone saved. Read it
    back as English word digits ONLY: ...") read as an instruction the model
    relayed to the CUSTOMER ("please say your number as separate English
    digits") instead of a confirmation it should speak itself.
    """
    return "\n".join([*facts, "GUIDE: " + " ".join(guides)])
