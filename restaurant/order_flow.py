"""Order flow state machine + per-turn LLM guidance (Tier B-3, B-4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    CONFIRM_CLOSE,
    PICKUP_DELIVERY_QUESTION,
    QUANTITY_QUESTION,
    UserIntent,
    format_order_readback,
    format_price_reply,
    is_add_intent,
    is_allergies_step_answer,
    is_want_to_order_only,
)
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
    allergies_asked: bool = False
    readback_confirmed: bool = False
    last_discussed_item: str | None = None
    last_discussed_price: float | None = None
    quantity_allowed: bool = False


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
        if not self.state.readback_confirmed:
            self.state.phase = OrderPhase.CONFIRMING
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

    def mark_allergies_asked(self) -> None:
        self.state.allergies_asked = True

    def mark_readback_confirmed(self) -> None:
        self.state.readback_confirmed = True

    def on_item_added(self) -> None:
        self.state.quantity_allowed = False
        self.state.phase = OrderPhase.AWAITING_MORE

    def _advance_from_user_turn(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
    ) -> None:
        if intent == UserIntent.ORDER_DONE and not cart.is_empty:
            self.mark_items_complete()

        if self.state.phase == OrderPhase.SPECIAL_INSTRUCTIONS:
            if self.state.allergies_asked and is_allergies_step_answer(user_text, intent):
                self.mark_special_instructions_done()
            elif intent == UserIntent.CONFIRM_NO:
                self.mark_special_instructions_done()

        if self.state.phase == OrderPhase.CONFIRMING and intent == UserIntent.CONFIRM_YES:
            self.mark_readback_confirmed()

    def build_turn_plan(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
    ) -> TurnPlan:
        self._advance_from_user_turn(user_text, intent, cart)
        self.sync_from_cart(cart)

        if is_add_intent(user_text) or intent == UserIntent.ADD_ITEM:
            self.state.quantity_allowed = True

        lines: list[str] = [f"[TURN GUIDANCE] phase={self.state.phase.value} intent={intent.value}"]

        if intent == UserIntent.ASK_PRICE:
            lines.extend(self._price_guidance(user_text))
        elif intent == UserIntent.ASK_AVAILABILITY:
            lines.extend(self._availability_guidance())
        elif intent == UserIntent.ADD_ITEM:
            if is_want_to_order_only(user_text):
                lines.append(
                    f'SAY EXACTLY: "{PICKUP_DELIVERY_QUESTION}" '
                    "(English — do not invent Punjabi for pickup/delivery)."
                )
            else:
                lines.append(
                    "Customer wants to add/order. Call add_to_order for each item. "
                    "If dish differs from what you last suggested, confirm the name once. "
                    "Ask quantity if unknown, then required modifiers ONE at a time. "
                    "Spice only if Options include Spice Level."
                )
            self.state.quantity_allowed = True
        elif intent == UserIntent.ORDER_DONE:
            if not cart.is_empty:
                self.mark_items_complete()
                self.sync_from_cart(cart)
                lines.append(
                    f'SAY EXACTLY: "{ALLERGIES_QUESTION}" '
                    "(English — do not translate special instructions into Punjabi)."
                )
                self.mark_allergies_asked()
        elif intent == UserIntent.PICKUP:
            lines.append(
                'Customer chose pickup. Call set_order_type("pickup") now. '
                "Do NOT ask pickup/delivery again if already set."
            )
        elif intent == UserIntent.DELIVERY:
            lines.append(
                'Customer chose delivery. Call set_order_type("delivery") now, then ask for address. '
                "Do NOT ask pickup/delivery again if already set."
            )
        elif intent == UserIntent.HUMAN:
            lines.append("Call transfer_to_human immediately after one short line.")
        elif intent == UserIntent.CONFIRM_YES and self.state.phase == OrderPhase.CONFIRMING:
            lines.append("Customer confirmed read-back. Call place_order() now.")

        lines.extend(self._phase_guidance(cart, intent))

        if self.state.quantity_allowed:
            lines.append(
                f'If asking quantity, SAY: "{QUANTITY_QUESTION}" '
                "(English number words one/two/three only — never ik/do or invented Punjabi)."
            )
        else:
            lines.append(
                "Do NOT ask how many / ਕਿੰਨਾ until customer clearly wants to add or order the item."
            )

        lines.append("Reply in ONE short sentence. ONE question only.")
        lines.append("Never ask permission to read the order — just read it when at confirming step.")

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

    def _phase_guidance(self, cart: OrderCart, intent: UserIntent) -> list[str]:
        p = self.state.phase
        if p == OrderPhase.AWAITING_MORE:
            return ['After confirming an add, ask: "Anything else?"']
        if p == OrderPhase.SPECIAL_INSTRUCTIONS:
            if not self.state.allergies_asked:
                return [
                    f'SAY EXACTLY: "{ALLERGIES_QUESTION}" '
                    "(keep special instructions in English)."
                ]
            return [
                f'If not asked yet, SAY EXACTLY: "{ALLERGIES_QUESTION}"',
            ]
        if p == OrderPhase.ORDER_TYPE:
            return [
                f'SAY EXACTLY: "{PICKUP_DELIVERY_QUESTION}"',
                'Then call set_order_type("pickup") or set_order_type("delivery").',
                "Do NOT read order total or confirm yet — pickup/delivery comes first.",
            ]
        if p == OrderPhase.DELIVERY_ADDRESS:
            return ["Ask for full delivery address, then call set_delivery_address."]
        if p == OrderPhase.CUSTOMER_NAME:
            return [
                'Ask: "Can I get a name for the order?"',
                "Only ask name AFTER customer confirmed the read-back (All good? → yes).",
            ]
        if p == OrderPhase.CUSTOMER_PHONE:
            return [
                "Ask for phone number. Read back digits in ENGLISH. "
                "Call set_customer_info only after name AND phone confirmed.",
            ]
        if p == OrderPhase.CONFIRMING:
            readback = format_order_readback(cart)
            out = [
                "FINAL CONFIRMATION — call get_order_summary() first.",
                "Do NOT ask if you may read the order — read it now.",
                f'SAY EXACTLY (adjust name if needed): "{readback}"',
                f'Close with "{CONFIRM_CLOSE}" — never "ਕਿਉਂਕਿ" or permission questions.',
                "Do NOT use Roman ik/do — English one/two only.",
            ]
            if (
                self.state.readback_confirmed
                and cart.customer_name
                and cart.customer_phone
            ):
                out.append("Contact info collected. Call place_order() now.")
            elif self.state.readback_confirmed:
                out.append("After read-back yes → collect name, then phone, then place_order().")
            else:
                out.append("After yes → advance to name/phone, then place_order().")
            return out
        if p == OrderPhase.COLLECTING_ITEMS and cart.is_empty:
            return ["Help customer browse or add first item — use menu tools."]
        return []
