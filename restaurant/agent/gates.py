"""Hard order gates — pure, LLM-free, unit-testable (refactor.md §2.1).

The LLM never decides whether an order may be placed; place_order_blockers
does. Readback staleness is enforced through the cart revision counter: any
mutation after get_order_readback() invalidates the confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    allergies_recorded: bool = False
    allergy_note: str = ""
    readback_revision: int | None = None  # cart.revision at last get_order_readback()
    readback_confirmed: bool = False
    real_user_turns: int = 0


def invalidate_readback(state: OrderSessionState) -> None:
    """Any cart mutation voids a previously confirmed readback."""
    state.readback_confirmed = False


def place_order_blockers(cart: "OrderCart", state: OrderSessionState) -> list[str]:
    """Everything still missing before place_order may run. Empty list = go."""
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
    if not state.allergies_recorded:
        blockers.append("Allergies have not been asked — ask and call record_allergies.")
    if not (state.readback_confirmed and state.readback_revision == cart.revision):
        blockers.append(
            "The order has not been read back and confirmed since the last change — "
            "call get_order_readback, read it verbatim, and get a yes."
        )
    return blockers
