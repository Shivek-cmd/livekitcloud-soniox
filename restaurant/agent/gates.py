"""Hard order gates — pure, LLM-free, unit-testable (refactor.md §2.1).

The LLM never decides whether an order may be placed; place_order_blockers
does. Readback staleness is enforced through the cart revision counter: any
mutation after get_order_readback() invalidates the confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from restaurant.agent.language import CustomerLanguage
from restaurant.customer_info import extract_phone_digits, is_valid_customer_name

if TYPE_CHECKING:
    from restaurant.orders import OrderCart

# The one place the "Spice Level" magic string is defined. order_submit.py,
# menu.py and clover/models.py match this literal in Clover modifier-group
# names — never rename it.
SPICE_GROUP = "Spice Level"

SPICE_LEVELS = ("Mild", "Medium", "Spicy", "Extra Spicy")


@dataclass
class OrderSessionState:
    preferred_language: CustomerLanguage = CustomerLanguage.ENGLISH
    additional_requests_recorded: bool = False
    allergy_note: str = ""
    readback_revision: int | None = None  # cart.revision at last get_order_readback()
    readback_confirmed: bool = False
    # PR 078 — spoken-readback capture: pending is set by get_order_readback,
    # every assistant line while pending lands in readback_spoken, and the
    # verifier checks the buffer at confirm_readback.
    readback_pending: bool = False
    readback_spoken: list[str] = field(default_factory=list)
    # PR 081 — queries add_item refused this turn; the next assistant line is
    # checked against them for a false "I've added …" claim.
    pending_add_refusals: list[str] = field(default_factory=list)
    # PR 082 — code-side phone digit custody: digits stitched across turns while
    # the phone is being collected. Owned by accumulate_phone, never the LLM.
    phone_buffer: str = ""
    real_user_turns: int = 0


def invalidate_readback(state: OrderSessionState) -> None:
    """Any cart mutation voids a previously confirmed readback — and any
    in-flight spoken-readback capture (the customer heard a stale order)."""
    state.readback_confirmed = False
    state.readback_pending = False
    state.readback_spoken.clear()
    # PR 081 — a successful mutation in the same turn means the upcoming
    # confirm is (at least partly) legitimate; don't flag mixed multi-add turns.
    state.pending_add_refusals.clear()


def readback_blockers(cart: "OrderCart", state: OrderSessionState) -> list[str]:
    """Everything that must be complete before the order can be read back.

    Same texts as place_order_blockers minus the readback-confirmation check —
    get_order_readback refuses with these so the LLM is told exactly what to
    collect next.
    """
    blockers: list[str] = []
    if cart.is_empty:
        blockers.append("The order is empty — add at least one item.")
    if not cart.order_type:
        blockers.append("Pickup or delivery has not been set — ask and call set_order_type.")
    if cart.order_type == "delivery" and not cart.delivery_address:
        blockers.append("Delivery needs an address — ask and call set_delivery_address.")
    if not (cart.customer_name and is_valid_customer_name(cart.customer_name)):
        blockers.append("A valid customer name is missing — ask and call set_customer_contact.")
    if not (cart.customer_phone and extract_phone_digits(cart.customer_phone)):
        blockers.append("A valid 10-digit phone number is missing — ask and call set_customer_contact.")
    if not state.additional_requests_recorded:
        blockers.append(
            "The final additional-requests question (spice preferences, allergies, "
            "special instructions) has not been asked — ask it and call "
            "record_additional_requests."
        )
    return blockers


def place_order_blockers(cart: "OrderCart", state: OrderSessionState) -> list[str]:
    """Everything still missing before place_order may run. Empty list = go."""
    blockers = readback_blockers(cart, state)
    if not (state.readback_confirmed and state.readback_revision == cart.revision):
        blockers.append(
            "The order has not been read back and confirmed since the last change — "
            "call get_order_readback, read it verbatim, and get a yes."
        )
    return blockers


def additional_requests_blockers(cart: "OrderCart") -> list[str]:
    """Must have at least one item before the closing additional-requests
    question makes sense."""
    if cart.is_empty:
        return [
            "The order is empty — add at least one item before asking the "
            "additional-requests question."
        ]
    return []


def order_type_blockers(cart: "OrderCart", state: OrderSessionState) -> list[str]:
    """Pickup/delivery is asked only after items are in and the final
    additional-requests question has been recorded (prompt.py _your_job order)."""
    blockers = additional_requests_blockers(cart)
    if not state.additional_requests_recorded:
        blockers.append(
            "The final additional-requests question (spice preferences, "
            "allergies, special instructions) has not been asked yet — ask "
            "it and call record_additional_requests before pickup/delivery."
        )
    return blockers


def contact_blockers(cart: "OrderCart", state: OrderSessionState) -> list[str]:
    """set_customer_contact may not run until items, additional requests, and
    order type (+ delivery address) are already settled — this is the check
    that stops the LLM from inventing a name/phone before the flow has
    actually reached that point."""
    blockers = order_type_blockers(cart, state)
    if not cart.order_type:
        blockers.append(
            "Pickup or delivery has not been set — ask and call "
            "set_order_type before collecting the name/phone."
        )
    elif cart.order_type == "delivery" and not cart.delivery_address:
        blockers.append(
            "Delivery needs an address — ask and call set_delivery_address "
            "before collecting the name/phone."
        )
    return blockers
