"""Order flow state machine + per-turn LLM guidance (Tier B-3, B-4).

PR 043: single authority for step (`compute_phase`). Checkout speech is
code-owned in agent.py; LLM gets minimal detour-safe guidance only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from restaurant.conversation import (
    CustomerLanguage,
    PICKUP_DELIVERY_QUESTION,
    QUANTITY_QUESTION,
    UserIntent,
    confirm_items_added,
    format_price_reply,
    is_add_intent,
    is_allergies_step_answer,
    is_confirm_yes,
    is_quantity_correction,
    is_readback_ack,
    is_readback_all_clear,
    is_want_to_order_only,
    language_turn_guidance,
    mentions_already_said,
    phrase_anything_else,
    phrase_repeat_request,
    update_preferred_language,
)
from restaurant.stt_noise import utterance_has_explicit_quantity
from restaurant import menu_provider
from restaurant.order_parse import parse_order_lines
from restaurant.orders import OrderCart


class OrderPhase(str, Enum):
    BROWSING = "browsing"
    COLLECTING_ITEMS = "collecting_items"
    AWAITING_MORE = "awaiting_more"
    SPECIAL_INSTRUCTIONS = "special_instructions"
    ORDER_TYPE = "order_type"
    DELIVERY_ADDRESS = "delivery_address"
    READBACK = "readback"
    CUSTOMER_NAME = "customer_name"
    CUSTOMER_PHONE = "customer_phone"
    READY_TO_PLACE = "ready_to_place"
    PLACED = "placed"

    # Analytics / legacy alias — was overloaded in pre-043 builds.
    CONFIRMING = "readback"


COLLECTING_PHASES = frozenset(
    {
        OrderPhase.BROWSING,
        OrderPhase.COLLECTING_ITEMS,
        OrderPhase.AWAITING_MORE,
    }
)

CODE_OWNED_CHECKOUT_PHASES = frozenset(
    {
        OrderPhase.SPECIAL_INSTRUCTIONS,
        OrderPhase.ORDER_TYPE,
        OrderPhase.READBACK,
        OrderPhase.CUSTOMER_NAME,
        OrderPhase.CUSTOMER_PHONE,
        OrderPhase.READY_TO_PLACE,
        OrderPhase.PLACED,
    }
)

DETOUR_INTENTS = frozenset(
    {
        UserIntent.ASK_PRICE,
        UserIntent.ASK_AVAILABILITY,
        UserIntent.ASK_ORDER_STATUS,
        UserIntent.HUMAN,
        UserIntent.ADD_ITEM,
    }
)


@dataclass
class OrderFlowState:
    phase: OrderPhase = OrderPhase.BROWSING
    items_complete: bool = False
    special_instructions_done: bool = False
    allergies_asked: bool = False
    readback_confirmed: bool = False
    readback_spoken: bool = False
    preferred_language: CustomerLanguage = CustomerLanguage.ENGLISH
    last_discussed_item: str | None = None
    last_discussed_price: float | None = None
    last_browse_topic: str | None = None
    quantity_allowed: bool = False


@dataclass
class TurnPlan:
    guidance: str
    quantity_allowed: bool = False


def compute_phase(cart: OrderCart, state: OrderFlowState) -> OrderPhase:
    """Single authority for which step the conversation is on."""
    if cart.placed:
        return OrderPhase.PLACED
    if cart.is_empty:
        if state.phase in (OrderPhase.BROWSING, OrderPhase.COLLECTING_ITEMS):
            return state.phase
        return OrderPhase.COLLECTING_ITEMS
    if not state.items_complete:
        return OrderPhase.AWAITING_MORE
    if not state.special_instructions_done:
        return OrderPhase.SPECIAL_INSTRUCTIONS
    if not cart.order_type:
        return OrderPhase.ORDER_TYPE
    if cart.order_type == "delivery" and not cart.delivery_address:
        return OrderPhase.DELIVERY_ADDRESS
    if not state.readback_confirmed:
        return OrderPhase.READBACK
    if not cart.customer_name:
        return OrderPhase.CUSTOMER_NAME
    if not cart.customer_phone:
        return OrderPhase.CUSTOMER_PHONE
    return OrderPhase.READY_TO_PLACE


# ── Requirements checklist (single source of truth for "what's still needed") ──
# The flow is NOT a rigid ladder: code tracks which facts are still missing
# before an order can be placed, and the LLM decides — like a human host — how
# and in what order to collect them. compute_phase() above stays as the
# analytics/gating label; the checklist below is what steers the conversation.

_SPICE_WORDS_RE = re.compile(
    r"mild|medium|spicy|hot|no\s*spice|less\s*spice|extra\s*spice|"
    r"ਤਿੱਖਾ|ਘੱਟ\s*ਤਿੱਖਾ|ਮਿੱਠਾ|तीखा|कम\s*तीखा|spice",
    re.I,
)


def _note_has_spice(note: str) -> bool:
    return bool(note) and bool(_SPICE_WORDS_RE.search(note))


def _dish_needs_spice(item) -> bool:
    """A cart line still needs a spice choice: it has a Spice Level option and
    no spice was captured in its note yet."""
    return menu_provider.item_has_spice_level(item.name) and not _note_has_spice(item.note)


def format_cart_brief(cart: OrderCart) -> str:
    """One-line factual cart summary for per-turn LLM grounding (no price)."""
    if cart.is_empty:
        return ""
    parts: list[str] = []
    for it in cart.items:
        label = f"{it.quantity}x {it.name}"
        if it.note:
            label += f" ({it.note})"
        parts.append(label)
    return ", ".join(parts)


def outstanding_requirements(cart: OrderCart, state: OrderFlowState) -> list[str]:
    """Plain-English list of everything still missing before this order can be
    placed, most-relevant first. Empty list ⇒ ready to confirm and place.

    This is a soft guide the LLM works through naturally — NOT an enforced
    sequence. The only hard gate is OrderCart.ready_to_place() at place time.
    """
    if cart.is_empty:
        return ["at least one item"]

    reqs: list[str] = []
    for item in cart.items:
        if _dish_needs_spice(item):
            reqs.append(f"spice level for {item.name}")
    if not (state.allergies_asked or state.special_instructions_done):
        reqs.append("ask about allergies / special instructions")
    if not cart.order_type:
        reqs.append("pickup or delivery")
    if cart.order_type == "delivery" and not cart.delivery_address:
        reqs.append("delivery address")
    if not state.readback_confirmed:
        reqs.append("read the order back once and get an OK")
    if not cart.customer_name:
        reqs.append("customer name")
    if not cart.customer_phone:
        reqs.append("phone number")
    return reqs


def is_collecting_phase(phase: OrderPhase) -> bool:
    return phase in COLLECTING_PHASES


def is_code_owned_checkout(phase: OrderPhase) -> bool:
    return phase in CODE_OWNED_CHECKOUT_PHASES


class OrderFlowController:
    """Tracks order conversation phase and builds per-turn guidance for the LLM."""

    def __init__(self, *, is_phone: bool) -> None:
        self.is_phone = is_phone
        self.state = OrderFlowState()

    def note_discussed_item(self, item_name: str, price: float | None = None) -> None:
        self.state.last_discussed_item = item_name
        self.state.last_discussed_price = price
        self.state.last_browse_topic = None

    def note_browse_topic(self, topic: str) -> None:
        self.state.last_browse_topic = topic

    def clear_browse_topic(self) -> None:
        self.state.last_browse_topic = None

    def sync_from_cart(self, cart: OrderCart) -> None:
        self.state.phase = compute_phase(cart, self.state)

    def mark_items_complete(self) -> None:
        self.state.items_complete = True

    def mark_special_instructions_done(self) -> None:
        self.state.special_instructions_done = True

    def mark_allergies_asked(self) -> None:
        self.state.allergies_asked = True

    def mark_readback_confirmed(self) -> None:
        self.state.readback_confirmed = True

    def mark_readback_spoken(self) -> None:
        self.state.readback_spoken = True

    def on_item_added(self) -> None:
        self.state.quantity_allowed = False
        self.state.last_browse_topic = None
        self.state.phase = OrderPhase.AWAITING_MORE

    def reopen_after_add(self) -> None:
        """A new item was added after checkout began — the order changed, so the
        read-back is stale and must happen again before the order is placed.
        Allergies / order-type already collected stay collected (don't re-ask)."""
        self.state.readback_spoken = False
        self.state.readback_confirmed = False

    def _advance_from_user_turn(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
    ) -> None:
        phase = compute_phase(cart, self.state)

        if (
            intent == UserIntent.ORDER_DONE
            and not cart.is_empty
            and is_collecting_phase(phase)
        ):
            self.mark_items_complete()

        if phase == OrderPhase.SPECIAL_INSTRUCTIONS:
            if self.state.allergies_asked and is_allergies_step_answer(user_text, intent):
                self.mark_special_instructions_done()
            elif intent == UserIntent.CONFIRM_NO:
                self.mark_special_instructions_done()

        if phase == OrderPhase.READBACK and (
            intent == UserIntent.CONFIRM_YES
            or is_confirm_yes(user_text)
            or is_readback_ack(user_text)
            or is_readback_all_clear(user_text)
        ):
            self.mark_readback_confirmed()

    def note_customer_language(self, user_text: str) -> None:
        self.state.preferred_language = update_preferred_language(
            self.state.preferred_language,
            user_text,
        )

    def _collecting_guidance(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
        lang: CustomerLanguage,
    ) -> list[str]:
        lines: list[str] = []

        if intent == UserIntent.ASK_PRICE:
            lines.extend(self._price_guidance(user_text))
        elif intent == UserIntent.ASK_AVAILABILITY:
            lines.extend(self._availability_guidance())
        elif intent == UserIntent.ADD_ITEM:
            if is_want_to_order_only(user_text):
                lines.append(
                    f'Customer wants to order but cart is empty or browsing — '
                    f'help them pick items first. Do NOT ask pickup/delivery yet.'
                )
            else:
                parsed = parse_order_lines(user_text)
                if len(parsed) >= 2:
                    entries = [
                        (
                            line.quantity,
                            line.item.get("voice_line")
                            or line.item.get("speak_as")
                            or line.item["name"],
                        )
                        for line in parsed
                    ]
                    confirm = confirm_items_added(entries, lang)
                    follow = phrase_anything_else(lang)
                    names = ", ".join(
                        f"{line.quantity}x {line.item['name']}" for line in parsed
                    )
                    lines.append(
                        f"Customer listed {len(parsed)} items in one sentence: {names}. "
                        "Call add_to_order for EACH item in this turn before speaking. "
                        "Do NOT call check_menu_item first. Do NOT ask what the second item is. "
                        "Do NOT mention price, cart, menu, or portion counts like two pieces. "
                        f'SAY EXACTLY after all added: "{confirm} {follow}"'
                    )
                else:
                    qty_note = (
                        " Quantity is already in the customer's words — "
                        "call add_to_order with that qty; do NOT ask how many."
                        if utterance_has_explicit_quantity(user_text)
                        else ""
                    )
                    # Live-call regression (PR 052): caller named ONE missed
                    # item ("I also said dal makhani") and the LLM re-called
                    # add_to_order for an item already in the cart too,
                    # doubling it — "two Palak Paneer" when only one was ever
                    # asked for.
                    correction_note = (
                        " Customer says they ALREADY mentioned this item "
                        "earlier — call add_to_order ONLY for this named "
                        "item. Do NOT re-call add_to_order for any item "
                        "already confirmed in the cart above."
                        if mentions_already_said(user_text)
                        else ""
                    )
                    lines.append(
                        "Customer wants to add. Call add_to_order when the dish name is clear — "
                        "do NOT call check_menu_item first unless the name is truly unclear. "
                        "If tool says item is NOT on menu: say that once, suggest search_menu_items, "
                        f'then ask: "{phrase_anything_else(lang)}" — stay on collecting step. '
                        f"Use SAY EXACTLY from the tool result. Do NOT mention price unless customer asked."
                        f"{qty_note}{correction_note}"
                    )
        elif intent == UserIntent.ORDER_DONE:
            if not cart.is_empty:
                lines.append(
                    "Customer is done ordering. System will ask allergies next — "
                    "do NOT ask allergies, pickup, or read-back yourself."
                )
        elif intent == UserIntent.HUMAN:
            lines.append("Call transfer_to_human immediately after one short line.")

        if not lines and cart.is_empty:
            lines.append("Help customer browse or add first item — use menu tools.")

        phase = compute_phase(cart, self.state)
        if phase == OrderPhase.AWAITING_MORE and intent != UserIntent.ORDER_DONE:
            q = phrase_anything_else(lang)
            lines.append(f'After confirming an add, ask: "{q}"')

        return lines

    def _checkout_detour_guidance(self, intent: UserIntent) -> list[str]:
        if intent == UserIntent.ASK_PRICE:
            return self._price_guidance("")
        if intent == UserIntent.ASK_AVAILABILITY:
            return self._availability_guidance()
        if intent == UserIntent.ADD_ITEM:
            return [
                "Customer wants to add or change an item — that's totally fine, "
                "even mid-checkout. Call add_to_order for a new dish, or "
                "update_item_quantity to correct a quantity. The system re-reads "
                "the updated order before placing, so just help them naturally."
            ]
        if intent == UserIntent.HUMAN:
            return ["Call transfer_to_human immediately after one short line."]
        return [
            "Answer briefly if they asked menu/price/status. "
            "Do NOT restart checkout or repeat the order."
        ]

    def build_turn_plan(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
    ) -> TurnPlan:
        self.note_customer_language(user_text)
        self._advance_from_user_turn(user_text, intent, cart)
        self.sync_from_cart(cart)

        lang = self.state.preferred_language
        phase = self.state.phase
        reqs = outstanding_requirements(cart, self.state)
        cart_brief = format_cart_brief(cart)

        lines: list[str] = [
            f"[ORDER STATUS] phase={phase.value} intent={intent.value} lang={lang.value}",
            f"In cart: {cart_brief}." if cart_brief else "Cart is empty so far.",
        ]
        if reqs:
            lines.append("Still needed before you can place this order: " + "; ".join(reqs) + ".")
        else:
            lines.append(
                "Everything needed is collected — confirm briefly and call place_order()."
            )

        lines.append(
            "You are a warm, real human host — never robotic. Cooperate with the "
            "customer and let the conversation flow: you do NOT have to follow a "
            "fixed order. If they add, change, or correct something, handle that "
            "FIRST, then continue. Work through the needed items above ONE at a "
            "time, in the customer's language."
        )
        lines.append(language_turn_guidance(lang))
        if self.state.last_browse_topic:
            lines.append(
                f'Customer was browsing "{self.state.last_browse_topic}" — they may be '
                "picking a dish now; do NOT re-list the options unless they ask again."
            )
        lines.append(f'If unclear audio, prefer: "{phrase_repeat_request(lang)}"')
        lines.append(
            "Do NOT mention price, dollars, totals, or ਡਾਲਰ in speech unless "
            "customer asked price this turn (ASK_PRICE intent)."
        )

        if not cart.is_empty and is_quantity_correction(user_text):
            lines.append(
                "Customer is CORRECTING a quantity already in the order — call "
                "update_item_quantity with the correct TOTAL amount. NEVER use "
                "add_to_order for a correction; it adds on top and doubles the mistake."
            )

        quantity_allowed = (
            is_collecting_phase(phase)
            and (is_add_intent(user_text) or intent == UserIntent.ADD_ITEM)
            and not utterance_has_explicit_quantity(user_text)
        )

        if is_collecting_phase(phase):
            lines.extend(self._collecting_guidance(user_text, intent, cart, lang))
        else:
            lines.extend(self._checkout_guidance(user_text, intent, cart, lang, reqs))

        if quantity_allowed:
            lines.append(
                f'If you need a quantity, ask naturally like: "{QUANTITY_QUESTION}" '
                "(English number words one/two/three only — never ik/do or invented Punjabi)."
            )
        else:
            lines.append(
                "Do NOT ask how many / ਕਿੰਨਾ until customer clearly wants to add or order the item."
            )

        lines.append("Reply in ONE short, natural sentence. ONE question only.")

        self.state.quantity_allowed = quantity_allowed
        return TurnPlan(
            guidance="\n".join(lines),
            quantity_allowed=quantity_allowed,
        )

    def _checkout_guidance(
        self,
        user_text: str,
        intent: UserIntent,
        cart: OrderCart,
        lang: CustomerLanguage,
        reqs: list[str],
    ) -> list[str]:
        """Soft, flexible steering once items are collected. The LLM leads the
        conversation; code still owns the grounded read-back, contact capture,
        and the final place-order gate (see agent.py handlers)."""
        lines: list[str] = []

        if intent in DETOUR_INTENTS:
            lines.extend(self._checkout_detour_guidance(intent))

        # Accuracy-critical lines stay code-owned — don't let the LLM improvise them.
        lines.append(
            "The order read-back, the phone-number read-back, and placing the "
            "order are handled exactly by the system — don't invent the item "
            "list, totals, or a phone read-back yourself."
        )
        if reqs:
            lines.append(f'Naturally ask the customer for the next thing: {reqs[0]}.')
        return lines

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
