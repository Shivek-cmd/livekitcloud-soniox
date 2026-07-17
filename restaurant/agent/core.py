"""RestaurantAgent — LLM talks, code owns the cart (refactor.md §2.2).

The LLM drives the conversation with full chat context, but can only touch the
order through the validating/resolving tools below. Every item tool routes
through one resolution choke point that abstains (AMBIGUOUS with real options,
NOT FOUND, unavailable) instead of guessing, adds use the resolved menu payload
only, the readback text is generated from the code cart and revision-gated,
and place_order is hard-gated by gates.place_order_blockers.

on_user_turn_completed is channel hygiene ONLY — no intent regexes, no
auto-add, no checkout ladder.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Annotated

from livekit.agents import Agent, JobContext, function_tool
from livekit.agents.llm import StopResponse

from restaurant import menu_provider
from restaurant import reservations as res_store
from restaurant.agent.gates import (
    SPICE_GROUP,
    SPICE_LEVELS,
    OrderSessionState,
    invalidate_readback,
    place_order_blockers,
    readback_blockers,
)
from restaurant.agent.facts import (
    format_cart_facts,
    format_contact_reply,
    format_mutation_reply,
)
from restaurant.agent.language import update_preferred_language
from restaurant.agent.prompt import build_system_prompt
from restaurant.agent.replies import (
    background_repeat_phrase,
    echo_recovery_phrase,
    format_order_readback,
    format_order_status,
    order_placed_goodbye,
)
from restaurant.channels.call_control import hangup_after_order_enabled, schedule_call_hangup
from restaurant.clover.order_submit import (
    CloverOrderSubmitError,
    clover_submit_enabled,
    submit_cart_to_clover,
)
from restaurant.customer_info import (
    _INDIC_NUMERAL_MAP,
    _spoken_words_to_digits,
    extract_phone_digits,
    format_phone_spoken,
    is_valid_customer_name,
    parse_customer_name,
)
from restaurant.menu import DELIVERY_CHARGE
from restaurant.orders import CartItem, CartMutation, OrderCart
from restaurant.channels.phone_background import (
    _question_pending,
    is_likely_background_speech,
)
from restaurant.channels.phone_echo import is_greeting_tail_echo, is_likely_phone_echo
from restaurant.session_config import (
    phone_background_filter_enabled,
)
from restaurant.analytics.session_recorder import SessionRecorder
from restaurant.channels.stt_noise import is_likely_stt_noise
from restaurant.channels.web_sync import WebSync

logger = logging.getLogger("restaurant-agent")


def _add_clarify_min_conf() -> float:
    """Below this match confidence, add_item asks 'did you mean X?' instead of
    silently adding a possibly-misheard dish. Above the matcher abstain floor
    (0.55) but below certainty."""
    try:
        return float(os.getenv("ADD_CLARIFY_MIN_CONF", "0.7"))
    except ValueError:
        return 0.7


_ADD_CLARIFY_MIN_CONF = _add_clarify_min_conf()

_MAX_ITEM_QTY = 20

_NO_ALLERGIES_RE = re.compile(
    r"^\s*(?:no|none|nope|nah|nothing|no allergies|nahi+n?|ਨਹੀਂ|नहीं|कोई नहीं)[\s.!]*$",
    re.I,
)

_SPICE_NOTE_RE = re.compile(r"\b(?:extra[ -]spicy|medium|mild|spicy)\b", re.I)

_ORDER_COMPLETE_SENTINEL = (
    "ORDER COMPLETE — goodbye already spoken to the customer. "
    "Do NOT generate any assistant speech."
)


def _canonical_spice(spice_level: str) -> str | None:
    """Map free-form spice input to one of the four Clover levels, or None."""
    s = (spice_level or "").strip().lower().replace("-", " ")
    for level in SPICE_LEVELS:
        if s == level.lower():
            return level
    return None


def _note_with_spice(spice: str | None, note: str) -> str:
    """Compose the cart-line note in the shape order_submit._match_spice_modifier
    maps back to the Clover Spice Level modifier (lowercase level word first)."""
    clean = (note or "").strip()
    if spice:
        clean = _SPICE_NOTE_RE.sub("", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip(" ,.-")
        return f"{spice.lower()}, {clean}" if clean else spice.lower()
    return clean


class RestaurantAgent(Agent):
    def __init__(self, *, is_phone: bool = False):
        super().__init__(instructions=build_system_prompt(is_phone=is_phone))
        self.cart = OrderCart()
        self.state = OrderSessionState()
        self.is_phone = is_phone
        self._session = None
        self._recorder: SessionRecorder | None = None
        self._web_sync: WebSync | None = None
        self._job_ctx: JobContext | None = None
        self._recent_agent_lines: list[str] = []
        self._echo_reprompt_done = False
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._background_ignore_streak = 0
        self._background_reprompt_done = False
        self._hangup_started = False
        self._goodbye_spoken = False
        self.menu_source = menu_provider.menu_source_label()
        logger.info(f"Menu source: {self.menu_source} | phone={is_phone}")

    # ── bindings / plumbing ──────────────────────────────────────────────────

    def bind_session(self, session) -> None:
        self._session = session

    def bind_web_sync(self, web_sync: WebSync) -> None:
        self._web_sync = web_sync

    def bind_recorder(self, recorder: SessionRecorder) -> None:
        self._recorder = recorder

    def bind_job_context(self, job_ctx: JobContext) -> None:
        self._job_ctx = job_ctx

    def _channel_label(self) -> str:
        return "phone" if self.is_phone else "web"

    def _record_tool(self, name: str, args: dict, result: str) -> None:
        if self._recorder is not None:
            self._recorder.log_tool(name, args, result)

    def _cart_snapshot(self) -> dict:
        return self.cart.to_state_dict()

    async def _sync_web(self) -> None:
        """Push the current cart to the web UI (no-op on phone)."""
        if self._web_sync is not None:
            await self._web_sync.publish_order_state()

    def _speech_in_flight(self) -> bool:
        """True if the session is currently speaking/about to speak (PR 042)."""
        if not self._session:
            return False
        handle = self._session.current_speech
        return handle is not None and not handle.done()

    def note_agent_speech(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        self._recent_agent_lines.append(line)
        self._recent_agent_lines = self._recent_agent_lines[-6:]

    # ── phone reprompts (carried over from the old agent) ───────────────────

    def _schedule_echo_reprompt(self, *, greeting_only: bool = False) -> None:
        if not self.is_phone or not self._session:
            return
        if greeting_only:
            if self._echo_reprompt_done:
                return
            self._echo_reprompt_done = True
        else:
            if self._echo_recovery_scheduled:
                return
            self._echo_recovery_scheduled = True
        asyncio.create_task(self._echo_reprompt(greeting_only=greeting_only))

    async def _echo_reprompt(self, *, greeting_only: bool = False) -> None:
        """Invite the caller to speak after echo — avoids dead air on phone."""
        await asyncio.sleep(1.2 if greeting_only else 0.8)
        if not self._session or self._speech_in_flight():
            return
        if greeting_only and self.state.real_user_turns > 0:
            return
        line = (
            "ਹਾਂ ਜੀ — go ahead, I'm listening."
            if greeting_only
            else echo_recovery_phrase()
        )
        try:
            await self._session.say(line, allow_interruptions=True)
        except Exception:
            logger.exception("Echo reprompt failed")
        finally:
            if not greeting_only:
                self._echo_recovery_scheduled = False

    def _schedule_background_reprompt(self) -> None:
        if not self.is_phone or self._background_reprompt_done:
            return
        self._background_reprompt_done = True
        asyncio.create_task(self._background_reprompt())

    async def _background_reprompt(self) -> None:
        if not self.is_phone or not self._session:
            return
        await asyncio.sleep(0.6)
        if not self._session or self._speech_in_flight():
            return
        try:
            await self._session.say(background_repeat_phrase(), allow_interruptions=True)
        except Exception:
            logger.exception("Background reprompt failed")

    # ── turn hook: channel hygiene ONLY, no ladder ───────────────────────────

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text = (new_message.text_content or "").strip()

        if self.is_phone:
            if is_likely_phone_echo(user_text, self._recent_agent_lines, intent=None):
                logger.info("Ignoring phone echo turn: %s", user_text)
                if self._recorder is not None:
                    if self._recorder.current_turn is None:
                        self._recorder.begin_user_turn(user_text)
                    self._recorder.mark_filtered("echo")
                # Only one post-greeting reprompt — never speak again on echo.
                if is_greeting_tail_echo(user_text) and not self._echo_reprompt_done:
                    self._greeting_echo_pending_reprompt = True
                    self._schedule_echo_reprompt(greeting_only=True)
                raise StopResponse()

            if is_likely_background_speech(
                user_text,
                None,
                enabled=phone_background_filter_enabled(),
            ):
                logger.info("Ignoring phone background turn: %s", user_text)
                if self._recorder is not None:
                    if self._recorder.current_turn is None:
                        self._recorder.begin_user_turn(user_text)
                    self._recorder.mark_filtered("background")
                self._background_ignore_streak += 1
                # PR 073 — if Sierra just asked a question, don't wait for a
                # streak of drops before reprompting; a single false-positive
                # drop right after a question would otherwise cause dead air.
                threshold = 1 if _question_pending(self._recent_agent_lines) else 3
                if self._background_ignore_streak >= threshold:
                    self._schedule_background_reprompt()
                raise StopResponse()

        if is_likely_stt_noise(user_text):
            logger.info("Ignoring STT-noise turn: %s", user_text[:80])
            if self._recorder is not None:
                if self._recorder.current_turn is None:
                    self._recorder.begin_user_turn(user_text)
                self._recorder.mark_filtered("stt_noise")
            if self._session and not self._speech_in_flight():
                line = background_repeat_phrase()
                await self._session.say(line, allow_interruptions=True)
                self.note_agent_speech(line)
            raise StopResponse()

        self.state.preferred_language = update_preferred_language(
            self.state.preferred_language, user_text
        )
        self.state.real_user_turns += 1
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._background_ignore_streak = 0

        if self._recorder is not None:
            self._recorder.complete_turn(cart_snapshot=self._cart_snapshot())

    # ── resolution choke point ───────────────────────────────────────────────

    def _resolve_menu_item(self, query: str) -> tuple[dict | None, str | None]:
        """(resolved item, None) or (None, refusal text for the LLM).

        The single path every item mutation goes through — the LLM can never
        write a name/price into the cart; adds use the resolved payload only.
        """
        raw = (query or "").strip()
        if not raw:
            return None, "Empty item name — ask the customer what they'd like."

        lookup = menu_provider.extract_dish_query(raw) or raw
        item = menu_provider.find_item(lookup)

        if item and item.get("unavailable"):
            return None, (
                f"'{item['name']}' is not available right now — apologize and "
                "offer an alternative. Do NOT add it."
            )
        if item and float(item.get("match_confidence", 1.0)) >= _ADD_CLARIFY_MIN_CONF:
            return item, None

        options = menu_provider.disambiguation_options(lookup, limit=3)
        if len(options) >= 2:
            names = ", ".join(o["name"] for o in options)
            return None, (
                f"AMBIGUOUS — '{raw}' could mean: {names}. Ask the customer "
                "which ONE they want — do NOT add anything yet, do NOT pick "
                "for them, and do NOT add more than one dish."
            )
        if len(options) == 1:
            return None, (
                f'AMBIGUOUS — did the customer mean "{options[0]["name"]}"? '
                "Confirm with a quick yes/no before adding — do NOT add yet."
            )
        if item:  # matched but below the clarify gate, with no other options
            return None, (
                f'AMBIGUOUS — did the customer mean "{item["name"]}"? '
                "Confirm with a quick yes/no before adding — do NOT add yet."
            )
        return None, (
            f"NOT FOUND — '{raw}' is not on our menu. Never invent a dish; "
            "ask the customer to clarify or call search_menu."
        )

    def _find_cart_line(self, item_query: str) -> CartItem | None:
        q = (item_query or "").strip().lower()
        if not q:
            return None
        for item in self.cart.items:
            if q in item.name.lower() or item.name.lower() in q:
                return item
            if item.voice_line and (
                q in item.voice_line.lower() or item.voice_line.lower() in q
            ):
                return item
        resolved, _refusal = self._resolve_menu_item(item_query)
        if resolved:
            for item in self.cart.items:
                if item.name.lower() == resolved["name"].lower():
                    return item
        return None

    def _not_in_cart(self, item_query: str) -> str:
        status = format_order_status(self.cart, include_price=False)
        return (
            f"'{item_query}' is not in the order. INTERNAL current order: "
            f"{status} Ask the customer to clarify which item they mean."
        )

    # ── ORDER TOOLS ──────────────────────────────────────────────────────────

    @function_tool
    async def add_item(
        self,
        item_query: Annotated[str, "The dish the customer named, in their words (English or Punjabi)"],
        quantity: Annotated[int, "How many — exactly what the customer said; 1 if they gave no number"] = 1,
        spice_level: Annotated[str, "Mild, Medium, Spicy, or Extra Spicy — required for dishes that take a spice level ('no preference' = Medium)"] = "",
        note: Annotated[str, "Required modifier choices and special instructions, e.g. 'butter naan, no onions'"] = "",
    ) -> str:
        """Add one menu item to the order. Works at ANY point in the call — a
        dish added after the readback just forces a fresh readback. If the
        customer listed several dishes, call once per item in the same turn."""
        if not isinstance(quantity, int) or quantity < 1:
            quantity = 1
        quantity = min(quantity, _MAX_ITEM_QTY)

        item, refusal = self._resolve_menu_item(item_query)
        if refusal:
            self._record_tool("add_item", {"item_query": item_query}, refusal)
            return refusal
        assert item is not None

        spice: str | None = None
        if menu_provider.item_has_spice_level(item["name"]):
            if not spice_level:
                result = (
                    f"NEEDS SPICE — {item['name']} needs a spice level. Ask the "
                    "customer: Mild, Medium, Spicy, or Extra Spicy? ('No "
                    "preference' = Medium.) Then re-call add_item with "
                    "spice_level. Do NOT add without it."
                )
                self._record_tool("add_item", {"item_query": item_query}, result)
                return result
            spice = _canonical_spice(spice_level)
            if spice is None:
                result = (
                    f"INVALID SPICE — '{spice_level}' is not a spice level. "
                    "Use exactly one of: Mild, Medium, Spicy, Extra Spicy."
                )
                self._record_tool("add_item", {"item_query": item_query}, result)
                return result

        required = [
            g
            for g in menu_provider.required_modifier_groups(item.get("clover_item_id") or "")
            if g != SPICE_GROUP
        ]
        if required and not (note or "").strip():
            groups = ", ".join(required)
            result = (
                f"NEEDS INFO — {item['name']} requires a choice for: {groups}. "
                "Ask the customer, then re-call add_item with their choice in "
                "note. Do NOT add without it."
            )
            self._record_tool("add_item", {"item_query": item_query}, result)
            return result

        mutation = self.cart.add_item(item, quantity, _note_with_spice(spice, note))
        result = (
            format_mutation_reply(mutation, self.cart)
            if isinstance(mutation, CartMutation)
            else mutation
        )
        invalidate_readback(self.state)
        await self._sync_web()
        self._record_tool(
            "add_item",
            {
                "item_query": item_query,
                "quantity": quantity,
                "spice_level": spice or "",
                "note": note,
            },
            result,
        )
        return result

    @function_tool
    async def set_item_quantity(
        self,
        item_query: Annotated[str, "The item already in the order"],
        quantity: Annotated[int, "The CORRECT total quantity (not an amount to add); 0 removes the item"],
    ) -> str:
        """Correct the quantity of an item already in the order — exact set,
        never additive. Use this (never add_item) when the customer corrects a
        quantity you already have ("I said one, not two", "make that three")."""
        line = self._find_cart_line(item_query)
        if line is None:
            result = self._not_in_cart(item_query)
            self._record_tool("set_item_quantity", {"item_query": item_query}, result)
            return result
        if isinstance(quantity, int) and quantity > _MAX_ITEM_QTY:
            quantity = _MAX_ITEM_QTY
        mutation = self.cart.update_item_quantity(line.name, quantity)
        result = (
            format_mutation_reply(mutation, self.cart)
            if isinstance(mutation, CartMutation)
            else mutation
        )
        invalidate_readback(self.state)
        await self._sync_web()
        self._record_tool(
            "set_item_quantity", {"item_query": item_query, "quantity": quantity}, result
        )
        return result

    @function_tool
    async def remove_item(
        self,
        item_query: Annotated[str, "The item to remove from the order"],
    ) -> str:
        """Remove an item from the customer's order entirely."""
        line = self._find_cart_line(item_query)
        if line is None:
            result = self._not_in_cart(item_query)
            self._record_tool("remove_item", {"item_query": item_query}, result)
            return result
        mutation = self.cart.remove_item(line.name)
        result = (
            format_mutation_reply(mutation, self.cart)
            if isinstance(mutation, CartMutation)
            else mutation
        )
        invalidate_readback(self.state)
        await self._sync_web()
        self._record_tool("remove_item", {"item_query": item_query}, result)
        return result

    @function_tool
    async def set_item_spice(
        self,
        item_query: Annotated[str, "The item already in the order"],
        spice_level: Annotated[str, "Mild, Medium, Spicy, or Extra Spicy"],
    ) -> str:
        """Change the spice level of an item already in the order
        ("make the butter chicken spicy")."""
        line = self._find_cart_line(item_query)
        if line is None:
            result = self._not_in_cart(item_query)
            self._record_tool("set_item_spice", {"item_query": item_query}, result)
            return result
        spice = _canonical_spice(spice_level)
        if spice is None:
            result = (
                f"INVALID SPICE — '{spice_level}' is not a spice level. "
                "Use exactly one of: Mild, Medium, Spicy, Extra Spicy."
            )
            self._record_tool("set_item_spice", {"item_query": item_query}, result)
            return result
        line.note = _note_with_spice(spice, line.note)
        self.cart.revision += 1
        invalidate_readback(self.state)
        await self._sync_web()
        voice = line.voice_line or line.name
        result = (
            f"SPICE SET: {voice} is now {spice.lower()}.\n"
            f"{format_cart_facts(self.cart)}\n"
            "GUIDE: confirm the spice change briefly in the customer's "
            "language, then keep the order moving."
        )
        self._record_tool(
            "set_item_spice", {"item_query": item_query, "spice_level": spice}, result
        )
        return result

    @function_tool
    async def record_allergies(
        self,
        response: Annotated[str, "The customer's answer to the allergies question, e.g. 'no' or 'peanut allergy'"],
    ) -> str:
        """Record the customer's answer after asking about allergies. Must be
        called (even for 'no') before the order can be placed."""
        text = (response or "").strip()
        self.state.allergies_recorded = True
        if not text or _NO_ALLERGIES_RE.match(text):
            self.state.allergy_note = ""
            result = "Allergies recorded: none. Continue — pickup or delivery?"
        else:
            self.state.allergy_note = text
            result = (
                f'Allergy noted for the kitchen: "{text}". '
                "Continue — pickup or delivery?"
            )
        self._record_tool("record_allergies", {"response": text}, result)
        return result

    @function_tool
    async def set_order_type(
        self,
        order_type: Annotated[str, "Either 'pickup' or 'delivery'"],
    ) -> str:
        """Set whether the order is for pickup or delivery."""
        order_type = (order_type or "").lower().strip()
        if order_type not in ("pickup", "delivery"):
            return "order_type must be 'pickup' or 'delivery'."
        changed = self.cart.order_type != order_type
        self.cart.order_type = order_type
        if changed:
            # Order type appears in the spoken readback (and changes the
            # total) — a previously confirmed readback is now stale.
            self.cart.revision += 1
            invalidate_readback(self.state)
        await self._sync_web()
        if order_type == "delivery":
            if self.is_phone:
                result = (
                    "Set to delivery. INTERNAL: delivery charge applies — do "
                    "NOT mention price unless the customer asked. Ask for the "
                    "delivery address."
                )
            else:
                result = (
                    f"Set to delivery. Delivery charge ${DELIVERY_CHARGE} will "
                    "be added. Ask for the delivery address."
                )
        else:
            result = "Set to pickup. Continue the flow."
        self._record_tool("set_order_type", {"order_type": order_type}, result)
        return result

    @function_tool
    async def set_delivery_address(
        self,
        address: Annotated[str, "Full delivery address including street and area"],
    ) -> str:
        """Save the delivery address for a delivery order."""
        clean = (address or "").strip()
        if len(clean) < 8 or " " not in clean:
            result = (
                "That does not look like a full address — ask for street, "
                "number, and area, then re-call set_delivery_address."
            )
            self._record_tool("set_delivery_address", {"address": clean}, result)
            return result
        self.cart.delivery_address = clean
        await self._sync_web()
        result = f"Delivery address saved: {clean}."
        self._record_tool("set_delivery_address", {"address": clean}, result)
        return result

    @function_tool
    async def set_customer_contact(
        self,
        name: Annotated[str, "Customer's name, exactly as they said it"] = "",
        phone: Annotated[str, "Customer's phone number (10 digits, or 11 with leading 1)"] = "",
    ) -> str:
        """Save the customer's name and/or phone for the order. Ask for the
        name first, then the phone on the next turn."""
        facts: list[str] = []
        guides: list[str] = []

        if name and name.strip():
            clean = parse_customer_name(name) or name.strip()
            if not is_valid_customer_name(clean):
                result = format_contact_reply(
                    [f'NAME NOT SAVED: "{name}" does not look like a real name.'],
                    ["ask for the customer's name again."],
                )
                self._record_tool("set_customer_contact", {"name": name}, result)
                return result
            if self.cart.customer_name and self.cart.customer_name != clean:
                # Name appears in the spoken readback — force a fresh one.
                self.cart.revision += 1
                invalidate_readback(self.state)
            self.cart.customer_name = clean
            facts.append(f'NAME SAVED: "{clean}".')
            guides.append(
                "confirm the name briefly in the customer's language."
            )
            if not self.cart.customer_phone and not (phone and phone.strip()):
                guides.append("Then ask for their phone number.")

        if phone and phone.strip():
            digits = extract_phone_digits(phone)
            if not digits:
                # PR 072 -- report what WAS captured (even if word-dictated
                # and short) so the LLM can stitch a number spoken across
                # turns instead of blindly re-asking from scratch.
                normalized = _spoken_words_to_digits(
                    phone.translate(_INDIC_NUMERAL_MAP)
                )
                captured = re.sub(r"\D", "", normalized)
                if captured:
                    facts.append(
                        f"PHONE NOT SAVED: heard only {len(captured)} "
                        f"digit(s) ({captured})."
                    )
                    guides.append(
                        "ask for the full 10-digit number, then pass ALL "
                        "digits together in one call."
                    )
                else:
                    facts.append("PHONE NOT SAVED: no usable digits heard.")
                    guides.append(
                        "ask the customer to repeat the number slowly."
                    )
            else:
                self.cart.customer_phone = digits
                spoken = format_phone_spoken(digits)
                facts.append(f"PHONE SAVED: {spoken}.")
                guides.append(
                    "the number is already saved — do NOT ask the customer "
                    "to repeat or re-say it. Confirm it back once yourself, "
                    "speaking it as English word digits exactly as in PHONE "
                    "SAVED (never numerals, never Punjabi/Hindi number "
                    "words), then continue the order."
                )

        if not facts:
            return "Nothing to save — pass name and/or phone."

        await self._sync_web()
        result = format_contact_reply(facts, guides)
        self._record_tool(
            "set_customer_contact", {"name": name, "phone": phone}, result
        )
        return result

    @function_tool
    async def get_order_readback(self) -> str:
        """Get the exact final read-back line for the order. Call after all
        details are collected, and again after ANY change to the order. Read
        the returned line back to the customer VERBATIM."""
        blockers = readback_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot read back yet:\n- " + "\n- ".join(blockers)
            self._record_tool("get_order_readback", {}, result)
            return result
        text = format_order_readback(self.cart, include_price=not self.is_phone)
        self.state.readback_revision = self.cart.revision
        self.state.readback_confirmed = False
        result = (
            "READ THIS BACK VERBATIM, then wait for the customer's yes:\n"
            f'"{text}"'
        )
        self._record_tool("get_order_readback", {}, result)
        return result

    @function_tool
    async def confirm_readback(self) -> str:
        """Call when the customer confirms the read-back is correct ("yes",
        "that's right"). Must come after get_order_readback."""
        if self.state.readback_revision is None:
            result = (
                "No read-back has been given yet — call get_order_readback "
                "first and read it to the customer."
            )
        elif self.state.readback_revision != self.cart.revision:
            result = (
                "The order changed since the last read-back — call "
                "get_order_readback again and read the NEW version to the "
                "customer before confirming."
            )
        else:
            self.state.readback_confirmed = True
            result = "Read-back confirmed. Call place_order now."
        self._record_tool("confirm_readback", {}, result)
        return result

    @function_tool
    async def place_order(self) -> str:
        """Finalize and place the order. Only call after confirm_readback
        succeeded."""
        if self.cart.placed or self._goodbye_spoken:
            return (
                "ORDER COMPLETE — goodbye already spoken. "
                "Do NOT generate any assistant speech."
            )

        blockers = place_order_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot place order:\n- " + "\n- ".join(blockers)
            self._record_tool("place_order", {}, result)
            return result

        clover_order_id: str | None = None
        clover_meta: dict = {}
        if clover_submit_enabled():
            from restaurant.tenants.config import get_default_tenant

            try:
                # submit_cart_to_clover is synchronous urllib — never block
                # the audio event loop with it.
                result = await asyncio.to_thread(
                    submit_cart_to_clover,
                    self.cart,
                    tenant=get_default_tenant(),
                    session_id=(
                        self._recorder.session_id if self._recorder is not None else None
                    ),
                    channel=self._channel_label(),
                    allergy_note=self.state.allergy_note or None,
                )
            except CloverOrderSubmitError as e:
                logger.error("Clover submit failed: %s", e)
                return f"Cannot place order: {e}"
            except Exception:
                logger.exception("Clover submit unexpected error")
                return (
                    "Cannot place order: could not reach the restaurant POS. "
                    "Apologize and offer to try again in a moment."
                )
            clover_order_id = result.clover_order_id
            clover_meta = {
                "clover_order_id": result.clover_order_id,
                "clover_total_cents": result.total_cents,
                "clover_customer_id": result.customer_id,
                "clover_printed": result.printed,
            }

        order_data = {
            "items": [
                {"name": i.name, "qty": i.quantity, "price": i.price, "note": i.note}
                for i in self.cart.items
            ],
            "type": self.cart.order_type,
            "subtotal": self.cart.subtotal,
            "total": self.cart.total,
            "customer": self.cart.customer_name,
            "phone": self.cart.customer_phone,
            "address": self.cart.delivery_address,
            "allergy_note": self.state.allergy_note,
            **clover_meta,
        }
        logger.info(f"ORDER_PLACED: {json.dumps(order_data, ensure_ascii=False)}")
        if self._recorder is not None:
            self._recorder.set_outcome("placed")
            self._recorder.add_event("order_placed", order_data)

        eta = "30-40 min" if self.cart.order_type == "delivery" else "20-25 min"
        self.cart.mark_placed(order_id=clover_order_id, eta=eta)
        await self._sync_web()

        # GHL/n8n CRM sync — fail-open; never block goodbye / hang-up.
        try:
            from restaurant.integrations.n8n_webhook import notify_order_placed

            await notify_order_placed(
                channel=self._channel_label(),
                customer_name=self.cart.customer_name,
                customer_phone=self.cart.customer_phone,
                order_type=self.cart.order_type,
                items=[
                    {
                        "name": i.name,
                        "qty": i.quantity,
                        "price": i.price,
                        "note": i.note,
                    }
                    for i in self.cart.items
                ],
                subtotal=self.cart.subtotal,
                total=self.cart.total,
                address=self.cart.delivery_address,
                allergy_note=self.state.allergy_note or None,
                clover_order_id=clover_order_id,
                clover_submitted=bool(clover_order_id),
                session_id=(
                    self._recorder.session_id if self._recorder is not None else None
                ),
                eta=eta,
                language=getattr(self.state, "preferred_language", None),
            )
        except Exception:
            logger.exception("n8n order.placed notify raised — ignored")

        spoken = order_placed_goodbye(order_type=self.cart.order_type)
        self._record_tool("place_order", {}, "placed")
        self._goodbye_spoken = True

        if (
            hangup_after_order_enabled()
            and self._session is not None
            and self._job_ctx is not None
            and not self._hangup_started
        ):
            self._hangup_started = True
            speech_handle = await self._session.say(spoken, allow_interruptions=False)
            self.note_agent_speech(spoken)
            if self._recorder is not None:
                self._recorder.append_sierra(spoken)
            schedule_call_hangup(
                self._session,
                self._job_ctx,
                reason="order_placed",
                channel=self._channel_label(),
                speech_handle=speech_handle,
            )
            return _ORDER_COMPLETE_SENTINEL + " End your turn silently."

        if self._session:
            await self._session.say(spoken, allow_interruptions=False)
            self.note_agent_speech(spoken)
            if self._recorder is not None:
                self._recorder.append_sierra(spoken)
            return _ORDER_COMPLETE_SENTINEL

        if self.is_phone:
            return (
                f"Order placed! INTERNAL total ${self.cart.total}. "
                f'Tell customer: "{spoken}" Do NOT mention price or dollars.'
            )
        return f"Order placed! Total ${self.cart.total}. Tell customer: {spoken}"

    # ── MENU TOOLS ───────────────────────────────────────────────────────────

    @function_tool
    async def check_menu_item(
        self,
        item_name: Annotated[str, "Item name to look up"],
    ) -> str:
        """Look up one menu item — veg/non-veg, modifier options, voice_line,
        availability. Price is internal."""
        item = menu_provider.resolve_item_dict_from_text(item_name) or menu_provider.find_item(
            menu_provider.extract_dish_query(item_name) or item_name
        )
        if not item:
            lookup = menu_provider.extract_dish_query(item_name) or item_name
            options = menu_provider.disambiguation_options(lookup)
            if len(options) >= 2:
                names = ", ".join(o["name"] for o in options)
                result = (
                    f'"{item_name}" could be: {names}. Ask the customer which '
                    "ONE — do NOT pick for them and do NOT add anything yet."
                )
                self._record_tool("check_menu_item", {"item_name": item_name}, result)
                return result
        result = menu_provider.check_item(item_name)
        self._record_tool("check_menu_item", {"item_name": item_name}, result)
        return result

    @function_tool
    async def search_menu(
        self,
        query: Annotated[str, "Search term e.g. 'paneer', 'combo', 'biryani', 'vegetarian starters'"],
    ) -> str:
        """Search the menu by keyword or category. Use for 'what X dishes do
        you have?' questions."""
        result = menu_provider.search_menu(query)
        self._record_tool("search_menu", {"query": query}, result)
        if self._recorder is not None and "no menu items found" in result.lower():
            self._recorder.add_event("menu_search_empty", {"query": query})
        return result

    @function_tool
    async def get_order_summary(self) -> str:
        """What is in the order so far — use when the customer asks for their
        current order mid-call. Never state the order from memory."""
        result = (
            f"{format_cart_facts(self.cart, label='ORDER SO FAR (state ONLY these items — never from memory)')}\n"
            "GUIDE: state the order in the customer's language using exactly "
            "these dish names and quantities (quantities as words, never digits)."
        )
        self._record_tool("get_order_summary", {}, result)
        return result

    # ── TRANSFER ─────────────────────────────────────────────────────────────

    @function_tool
    async def transfer_to_human(
        self,
        reason: Annotated[str, "Why the call is being transferred, e.g. 'caller requested' or 'two unclear responses'"] = "",
    ) -> str:
        """Transfer the call to a human staff member."""
        logger.info(f"TRANSFER_TO_HUMAN: {reason}")
        if self._recorder is not None:
            self._recorder.set_transfer(reason or "unspecified")
        return (
            "Transfer logged. Tell the customer to please hold, then stay quiet. "
            "A staff member will take over."
        )

    # ── RESERVATION TOOLS ────────────────────────────────────────────────────

    @function_tool
    async def check_table_availability(
        self,
        date: Annotated[str, "Date in YYYY-MM-DD format"],
        time: Annotated[str, "Time in HH:MM 24-hour format e.g. 19:30"],
        party_size: Annotated[int, "Number of people"],
    ) -> str:
        """Check if a table is available for a given date, time and party size."""
        available, message = res_store.check_availability(date, time, party_size)
        return message if not available else f"Table available for {party_size} on {date} at {time}."

    @function_tool
    async def book_reservation(
        self,
        date: Annotated[str, "Date in YYYY-MM-DD format"],
        time: Annotated[str, "Time in HH:MM 24-hour format e.g. 19:30"],
        party_size: Annotated[int, "Number of people"],
        customer_name: Annotated[str, "Customer's name"],
        customer_phone: Annotated[str, "Customer's phone number"],
    ) -> str:
        """Book a table reservation after confirming all details with the customer."""
        available, message = res_store.check_availability(date, time, party_size)
        if not available:
            return message

        record = res_store.book(date, time, party_size, customer_name, customer_phone)
        logger.info(f"RESERVATION_BOOKED: {json.dumps(record, ensure_ascii=False)}")
        if self._recorder is not None:
            self._recorder.add_event("reservation_booked", record)

        return (
            f"Reservation confirmed! Ref: {record['ref']}. "
            f"Tell customer: ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਹੋ ਗਈ ਜੀ! "
            f"Reference number ਹੈ {record['ref']}। ਧੰਨਵਾਦ ਜੀ!"
        )
