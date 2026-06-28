"""Order flow state machine + per-turn LLM guidance (Tier B-3, B-4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from restaurant.conversation import UserIntent, format_price_reply, is_add_intent
from restaurant import menu_provider
from restaurant.orders import OrderCart


class OrderPhase(str, Enum):
    BROWSING = "browsing"
    COLLECTING_ITEMS = "collecting_items"
    AWAITING_MORE = "awaiting_more"
    SPECIAL_INSTRUCTIONS = "special_instructions"
    ORDER_TYPE = "order_type"
    DELIVERY_ADDRESS = "delivery_address"
    CUSTOMER_NAME = "customer_name"
    CUSTOMER_PHONE = "customer_phone"
    CONFIRMING = "confirming"
    PLACED = "placed"


@dataclass
class OrderFlowState:
    phase: OrderPhase = OrderPhase.BROWSING
    items_complete: bool = False
    special_instructions_done: bool = False
    last_discussed_item: str | None = None
    last_discussed_price: float | None = None
    quantity_allowed: bool = False  # B-4 gate


@dataclass
class TurnPlan:
    guidance: str
    quantity_allowed: bool = False


class OrderFlowController:
    """Tracks order conversation phase and builds per-turn guidance for the LLM."""

    def __init__(self, *, is_phone: bool) -> None:
        self.is_phone = is_phone
        self.state = OrderFlowState()

    def note_discussed_item(self, item_name: str, price: float | None = None) -> None:
        self.state.last_discussed_item = item_name
        self.state.last_discussed_price = price

    def sync_from_cart(self, cart: OrderCart) -> None:
        if cart.placed:
            self.state.phase = OrderPhase.PLACED
            return
        if cart.is_empty:
            if self.state.phase not in (OrderPhase.BROWSING, OrderPhase.COLLECTING_ITEMS):
                self.state.phase = OrderPhase.COLLECTING_ITEMS
            return
        if not self.state.items_complete:
            self.state.phase = OrderPhase.AWAITING_MORE
            return
        if not self.state.special_instructions_done:
            self.state.phase = OrderPhase.SPECIAL_INSTRUCTIONS
            return
        if not cart.order_type:
            self.state.phase = OrderPhase.ORDER_TYPE
            return
        if cart.order_type == "delivery" and not cart.delivery_address:
            self.state.phase = OrderPhase.DELIVERY_ADDRESS
            return
        if not cart.customer_name:
            self.state.phase = OrderPhase.CUSTOMER_NAME
            return
        if not cart.customer_phone:
            self.state.phase = OrderPhase.CUSTOMER_PHONE
            return
        self.state.phase = OrderPhase.CONFIRMING

    def mark_items_complete(self) -> None:
        self.state.items_complete = True
        self.state.phase = OrderPhase.SPECIAL_INSTRUCTIONS

    def mark_special_instructions_done(self) -> None:
        self.state.special_instructions_done = True

    def on_item_added(self) -> None:
        self.state.quantity_allowed = False
        self.state.phase = OrderPhase.AWAITING_MORE

    def build_turn_plan(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
    ) -> TurnPlan:
        self.sync_from_cart(cart)

        # B-4: quantity gate from caller intent
        if is_add_intent(user_text) or intent == UserIntent.ADD_ITEM:
            self.state.quantity_allowed = True

        lines: list[str] = [f"[TURN GUIDANCE] phase={self.state.phase.value} intent={intent.value}"]

        # Intent-specific rules (B-3)
        if intent == UserIntent.ASK_PRICE:
            lines.extend(self._price_guidance(user_text))
        elif intent == UserIntent.ASK_AVAILABILITY:
            lines.extend(self._availability_guidance())
        elif intent == UserIntent.ADD_ITEM:
            lines.append(
                "Customer wants to add/order. Confirm item, ask quantity if unknown, "
                "then required modifiers ONE at a time. Spice only if Options include Spice Level."
            )
            self.state.quantity_allowed = True
        elif intent == UserIntent.ORDER_DONE:
            if not cart.is_empty:
                self.state.items_complete = True
                lines.append(
                    'Customer is done adding items. Ask ONCE: "Any allergies or special instructions?" '
                    "then proceed to pickup/delivery."
                )
        elif intent == UserIntent.HUMAN:
            lines.append("Call transfer_to_human immediately after one short line.")

        # Phase nudges when not overridden by intent
        lines.extend(self._phase_guidance(cart))

        # B-4 quantity gate
        if not self.state.quantity_allowed:
            lines.append(
                "Do NOT ask how many / ਕਿੰਨਾ until customer clearly wants to add or order the item."
            )

        lines.append("Reply in ONE short sentence. ONE question only.")

        return TurnPlan(
            guidance="\n".join(lines),
            quantity_allowed=self.state.quantity_allowed,
        )

    def _price_guidance(self, user_text: str) -> list[str]:
        item = menu_provider.resolve_item_in_text(user_text)
        if not item and self.state.last_discussed_item:
            item = menu_provider.find_item(self.state.last_discussed_item)

        out = [
            "Customer asked PRICE only.",
            "Do NOT ask quantity, spice, or modifiers this turn.",
            "Do NOT add marketing fluff — one English price line only.",
        ]
        if item:
            price = float(item.get("price") or (item.get("price_cents", 0) / 100))
            template = format_price_reply(price)
            out.append(f'Use this exact price line: "{template}"')
            if menu_provider.item_has_spice_level(item["name"]):
                out.append("Do NOT ask spice on this turn — price question only.")
        else:
            out.append("Call check_menu_item first if dish name unclear, then give ONE price line.")
        return out

    def _availability_guidance(self) -> list[str]:
        return [
            "Customer asked AVAILABILITY only.",
            "Answer yes/no; name at most TWO items from tool results.",
            "Do NOT ask quantity or spice unless customer also said add/order.",
            "Do NOT mention price unless they asked.",
        ]

    def _phase_guidance(self, cart: OrderCart) -> list[str]:
        p = self.state.phase
        if p == OrderPhase.AWAITING_MORE:
            return ['After confirming an add, ask: "Anything else?"']
        if p == OrderPhase.SPECIAL_INSTRUCTIONS:
            return ['Ask: "Any allergies or special instructions for anything?"']
        if p == OrderPhase.ORDER_TYPE:
            return ['Ask: "Pickup or delivery?" then call set_order_type.']
        if p == OrderPhase.DELIVERY_ADDRESS:
            return ["Ask for full delivery address, then call set_delivery_address."]
        if p == OrderPhase.CUSTOMER_NAME:
            return ['Ask: "Can I get a name for the order?"']
        if p == OrderPhase.CUSTOMER_PHONE:
            return [
                "Ask for phone number. Read back digits in ENGLISH. "
                "Call set_customer_info only after name AND phone confirmed."
            ]
        if p == OrderPhase.CONFIRMING:
            return [
                "Call get_order_summary(), read back with voice_line names, "
                "then total. Ask 'All good?' Once yes → place_order()."
            ]
        if p == OrderPhase.COLLECTING_ITEMS and cart.is_empty:
            return ["Help customer browse or add first item — use menu tools."]
        return []
