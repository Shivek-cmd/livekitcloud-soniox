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
    additional_requests_blockers,
    contact_blockers,
    contact_readback_blockers,
    invalidate_contact_readback,
    invalidate_readback,
    order_type_blockers,
    place_order_blockers,
    readback_blockers,
)
from restaurant.agent.facts import (
    format_cart_facts,
    format_contact_readback_facts,
    format_contact_reply,
    format_mutation_reply,
    format_readback_facts,
)
from restaurant.agent.add_claim_verify import add_claim_verify_mode, falsely_claims_add
from restaurant.agent.additional_requests_verify import (
    additional_requests_verify_mode,
    asks_additional_requests,
)
from restaurant.agent.language import update_preferred_language
from restaurant.agent.persona import PERSONA_REANCHOR_LINE, persona_reanchor_turns
from restaurant.agent.prompt import build_system_prompt
from restaurant.agent.readback_verify import (
    contact_verify_mode,
    readback_verify_mode,
    verify_contact_readback,
    verify_readback,
)
from restaurant.agent.tts_transform import (
    dish_english_enforced_stream,
    phone_enforced_stream,
    tts_dish_english_enforce_enabled,
    tts_phone_enforce_enabled,
)
from restaurant.agent.replies import (
    background_repeat_phrase,
    contact_readback_line,
    echo_recovery_phrase,
    false_add_correction_phrase,
    format_order_status,
    order_placed_goodbye,
)
from restaurant.channels.call_control import hangup_after_order_enabled, schedule_call_hangup
from restaurant.clover.order_submit import (
    SPICE_ALIASES,
    CloverOrderSubmitError,
    clover_submit_enabled,
    submit_cart_to_clover,
)
from restaurant.customer_info import (
    accumulate_phone,
    format_phone_spoken,
    is_plausible_phone,
    is_roman_name,
    is_valid_customer_name,
    parse_customer_name,
    phone_digit_custody_enabled,
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

# PR 101 — contact-confirmation capture window. A readback is 1–2 lines; the
# cap only stops the buffer growing across a long unconfirmed stretch.
_CONTACT_SPOKEN_LINES = 12

# PR 101 — confirm_contact attempts allowed before the gate gives up and lets
# the confirm through (so: two refusals, then the third attempt passes). Bounds
# the verifier's blast radius — a gap costs one possibly-unheard readback, never
# a call that can never place its order.
_MAX_CONTACT_CONFIRM_ATTEMPTS = 3

_NO_ALLERGIES_RE = re.compile(
    r"^\s*(?:no|none|nope|nah|nothing|no allergies|nahi+n?|ਨਹੀਂ|नहीं|कोई नहीं)[\s.!]*$",
    re.I,
)

_SPICE_NOTE_RE = re.compile(r"\b(?:extra[ -]spicy|medium|mild|spicy)\b", re.I)

# PR 081 — every _resolve_menu_item refusal leads with this so the LLM can
# never mistake a refusal for a success; the prompt keys off the ⛔ marker.
_REFUSAL_PREFIX = "⛔ NOTHING WAS ADDED — CART UNCHANGED. "

# Why the add was refused. Only NOT_FOUND/UNAVAILABLE may ever be spoken as
# "we don't have that" — AMBIGUOUS means the dish IS on the menu and we just
# need the customer to pick which one.
_REFUSAL_EMPTY = "empty"
_REFUSAL_UNAVAILABLE = "unavailable"
_REFUSAL_AMBIGUOUS = "ambiguous"
_REFUSAL_NOT_FOUND = "not_found"

_ORDER_COMPLETE_SENTINEL = (
    "ORDER COMPLETE — goodbye already spoken to the customer. "
    "Do NOT generate any assistant speech."
)


# PR 094 — spice is now asked on every spiced dish, so the answer arrives in
# the caller's own words far more often. "No preference" is the kitchen
# default; the rest of the vocabulary is SPICE_ALIASES, shared with the Clover
# note→modifier matcher so both sides read the same words the same way.
_NO_SPICE_PREFERENCE = (
    "no preference",
    "no preferences",
    "any",
    "anything",
    "whatever",
    "normal",
    "regular",
    "koi bhi",
    "kuch bhi",
)

_NOT_SPICY_RE = re.compile(r"\b(?:not|no|non|less|little|nahi+n?)\b[\w\s]*\bspic", re.I)


def _canonical_spice(spice_level: str) -> str | None:
    """Map free-form spice input to one of the four Clover levels, or None."""
    s = (spice_level or "").strip().lower().replace("-", " ")
    s = re.sub(r"\s{2,}", " ", s)
    if not s:
        return None
    for level in SPICE_LEVELS:
        if s == level.lower():
            return level
    if s in _NO_SPICE_PREFERENCE:
        return "Medium"
    # "not spicy" / "no spice" is Mild — checked before the alias table, whose
    # substring match would otherwise read the "spicy" inside the negation.
    if _NOT_SPICY_RE.search(s):
        return "Mild"
    # SPICE_ALIASES is ordered longest-label-first, so "extra spicy" can never
    # be swallowed by the "spicy" entry.
    for label, aliases in SPICE_ALIASES.items():
        if any(a in s for a in aliases):
            return next(
                (lvl for lvl in SPICE_LEVELS if lvl.lower() == label), None
            )
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
        self._false_add_reanchor: tuple[str, str] | None = None
        self._refusal_kinds: dict[str, str] = {}
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

    def _in_phone_collection(self) -> bool:
        """PR 082 phase predicate for phone custody: name captured, phone still
        missing, order type set. The order-type condition keeps custody from
        firing on digit fragments (quantities) during item taking."""
        return bool(
            self.cart.customer_name
            and not self.cart.customer_phone
            and self.cart.order_type
        )

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

    def tts_node(self, text, model_settings):
        """PR 079 — phone-digit enforcement in the REAL audio path: whatever
        the LLM wrote, TTS only ever hears the stored phone as English word
        digits. Rollback: TTS_PHONE_ENFORCE=0.

        PR 085 — dish-name backstop runs FIRST: any Gurmukhi rendition of an
        english-mode dish (ਲੈਮ ਬਿਰਿਆਨੀ) is rewritten to its English voice_line
        before phone enforcement sees the stream. Rollback: TTS_DISH_ENGLISH_ENFORCE=0."""
        if tts_dish_english_enforce_enabled():
            text = dish_english_enforced_stream(
                text, menu_provider.english_dish_reverse_map
            )
        if tts_phone_enforce_enabled():
            text = phone_enforced_stream(
                text, lambda: self.cart.customer_phone or None
            )
        return Agent.default.tts_node(self, text, model_settings)

    def note_agent_speech(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        self._recent_agent_lines.append(line)
        self._recent_agent_lines = self._recent_agent_lines[-6:]
        # PR 078 — capture the spoken readback for the confirm-time verifier.
        if self.state.readback_pending:
            self.state.readback_spoken.append(line)
        # PR 092/101 — same capture for the name/phone confirmation step, but
        # armed by having details to confirm rather than by a getter call: the
        # correction path (set_customer_contact then re-read) skips the getter,
        # and gating on it made the strict gate permanently unsatisfiable.
        if (
            not self.state.contact_confirmed
            and self.cart.customer_name
            and self.cart.customer_phone
        ):
            self.state.contact_spoken.append(line)
            # Bounded — capture now spans turns, and a readback is 1–2 lines.
            del self.state.contact_spoken[:-_CONTACT_SPOKEN_LINES]
        # PR 095 — the wrap-up question must be heard by the customer before
        # its answer can be recorded. Any line that raises allergies or
        # special instructions arms record_additional_requests.
        if not self.state.additional_requests_asked and asks_additional_requests(line):
            self.state.additional_requests_asked = True
        # PR 081 — after add_item refused, the very next spoken line must not
        # claim the item was added (one-shot check; the cart never changed).
        if self.state.pending_add_refusals:
            refusals = list(self.state.pending_add_refusals)
            self.state.pending_add_refusals.clear()
            mode = add_claim_verify_mode()
            if mode != "off":
                hit = next(
                    (q for q in refusals if falsely_claims_add(line, q)), None
                )
                if hit:
                    logger.warning(
                        "False add claim after refusal of %r: %s", hit, line
                    )
                    if self._recorder is not None:
                        self._recorder.add_event(
                            "false_add_claim", {"query": hit, "spoken": line}
                        )
                    if mode == "strict":
                        kind = self._refusal_kinds.get(hit, _REFUSAL_NOT_FOUND)
                        self._false_add_reanchor = (hit, kind)
                        self._schedule_false_add_correction(hit, kind)
            self._refusal_kinds.clear()

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

    def _schedule_false_add_correction(self, query: str, kind: str) -> None:
        if not self._session:
            return
        asyncio.create_task(self._false_add_correction(query, kind))

    async def _false_add_correction(self, query: str, kind: str) -> None:
        """PR 081 strict mode — speak a correction after the LLM claimed a
        refused item was added; the customer must not believe it's on the
        order. Waits out the in-flight false claim first."""
        await asyncio.sleep(0.5)
        for _ in range(20):
            if not self._session:
                return
            if not self._speech_in_flight():
                break
            await asyncio.sleep(0.5)
        line = false_add_correction_phrase(
            query,
            language=self.state.preferred_language.value,
            ambiguous=(kind == _REFUSAL_AMBIGUOUS),
        )
        try:
            await self._session.say(line, allow_interruptions=True)
        except Exception:
            logger.exception("False-add correction failed")

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
        # PR 081 — a new user turn stales any unchecked add refusal.
        self.state.pending_add_refusals.clear()
        self._refusal_kinds.clear()
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._background_ignore_streak = 0

        # PR 082 — code-side phone digit custody. The LLM is an unreliable
        # courier for digits (in the live repro it never called
        # set_customer_contact with a phone during the whole retry loop), so
        # while the phone is being collected, code captures it from the
        # transcript and injects a system message. No StopResponse — the LLM
        # must still speak the progress/confirm turn.
        if phone_digit_custody_enabled() and self._in_phone_collection():
            new_buffer, event = accumulate_phone(self.state.phone_buffer, user_text)
            self.state.phone_buffer = new_buffer
            if event == "saved":
                self.cart.customer_phone = new_buffer
                self.state.phone_buffer = ""
                await self._sync_web()
                if self._recorder is not None:
                    self._recorder.add_event(
                        "phone_captured_code_side", {"phone": new_buffer}
                    )
                try:
                    turn_ctx.add_message(
                        role="system",
                        content=(
                            "PHONE CAPTURED AND SAVED by the system: "
                            f"{format_phone_spoken(new_buffer)}. Do NOT ask for "
                            "the number again — confirm it back once as English "
                            "word digits, then continue the order."
                        ),
                    )
                except Exception:
                    logger.exception("Phone-captured injection failed")
            elif event in ("append", "reset") and new_buffer:
                try:
                    turn_ctx.add_message(
                        role="system",
                        content=(
                            f"PHONE IN PROGRESS: the system has {len(new_buffer)} "
                            f"of 10 digits ({new_buffer}). Ask only for the "
                            "REMAINING digits — do not restart, do not call "
                            "set_customer_contact until the customer finishes."
                        ),
                    )
                except Exception:
                    logger.exception("Phone-progress injection failed")

        # Persona drift re-anchor (PR 077, 4c): every N real turns, re-inject a
        # one-line reminder next to the generation point — the system prompt
        # loses gravity as context grows and one robotic turn breeds more.
        n = persona_reanchor_turns()
        if n > 0 and self.state.real_user_turns % n == 0:
            try:
                turn_ctx.add_message(role="system", content=PERSONA_REANCHOR_LINE)
            except Exception:
                logger.exception("Persona re-anchor injection failed")

        # PR 081 — after a strict false-add-claim hit, re-anchor the LLM so it
        # stops believing the refused item is in the cart.
        if self._false_add_reanchor:
            query, kind = self._false_add_reanchor
            self._false_add_reanchor = None
            if kind == _REFUSAL_AMBIGUOUS:
                # The dish EXISTS — we only failed to pin down which one. Saying
                # "not available" here denies a real menu item.
                tail = (
                    "Never claim it was added, and do NOT say we don't have it — "
                    "we could not tell WHICH dish they meant. Ask them which one."
                )
            else:
                tail = (
                    "Never claim it was added; tell the customer it isn't "
                    "available and help them pick something else."
                )
            try:
                turn_ctx.add_message(
                    role="system",
                    content=(
                        f"RE-ANCHOR: '{query}' was NOT added — the cart is "
                        f"unchanged. {tail}"
                    ),
                )
            except Exception:
                logger.exception("False-add re-anchor injection failed")

        if self._recorder is not None:
            self._recorder.complete_turn(cart_snapshot=self._cart_snapshot())

    # ── resolution choke point ───────────────────────────────────────────────

    def _resolve_menu_item(
        self, query: str
    ) -> tuple[dict | None, str | None, str | None]:
        """(resolved item, None, None) or (None, refusal text, refusal kind).

        The single path every item mutation goes through — the LLM can never
        write a name/price into the cart; adds use the resolved payload only.

        The refusal KIND matters downstream: AMBIGUOUS means the dish exists
        and we only need to know which one, so it must never be spoken as
        "we don't have that" (live-call bug — real dishes got denied).
        """
        raw = (query or "").strip()
        if not raw:
            return None, _REFUSAL_PREFIX + (
                "Empty item name — ask the customer what they'd like."
            ), _REFUSAL_EMPTY

        lookup = menu_provider.extract_dish_query(raw) or raw
        item = menu_provider.find_item(lookup)

        if item and item.get("unavailable"):
            return None, _REFUSAL_PREFIX + (
                f"'{item['name']}' is not available right now — apologize and "
                "offer an alternative. Do NOT add it."
            ), _REFUSAL_UNAVAILABLE
        if item and float(item.get("match_confidence", 1.0)) >= _ADD_CLARIFY_MIN_CONF:
            return item, None, None

        options = menu_provider.disambiguation_options(lookup, limit=3)
        if len(options) >= 2:
            names = ", ".join(o["name"] for o in options)
            return None, _REFUSAL_PREFIX + (
                f"AMBIGUOUS — '{raw}' could mean: {names}. Ask the customer "
                "which ONE they want — do NOT add anything yet, do NOT pick "
                "for them, and do NOT add more than one dish."
            ), _REFUSAL_AMBIGUOUS
        if len(options) == 1:
            return None, _REFUSAL_PREFIX + (
                f'AMBIGUOUS — did the customer mean "{options[0]["name"]}"? '
                "Confirm with a quick yes/no before adding — do NOT add yet."
            ), _REFUSAL_AMBIGUOUS
        if item:  # matched but below the clarify gate, with no other options
            return None, _REFUSAL_PREFIX + (
                f'AMBIGUOUS — did the customer mean "{item["name"]}"? '
                "Confirm with a quick yes/no before adding — do NOT add yet."
            ), _REFUSAL_AMBIGUOUS
        return None, _REFUSAL_PREFIX + (
            f"NOT FOUND — '{raw}' is not on our menu. Never invent a dish; "
            "ask the customer to clarify or call search_menu."
        ), _REFUSAL_NOT_FOUND

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
        resolved, _refusal, _kind = self._resolve_menu_item(item_query)
        if resolved:
            for item in self.cart.items:
                if item.name.lower() == resolved["name"].lower():
                    return item
        return None

    def _cart_line_has_spice(self, name: str) -> bool:
        """True if this dish is already in the order with a spice level set."""
        return any(
            line.name.lower() == (name or "").lower()
            and _SPICE_NOTE_RE.search(line.note or "")
            for line in self.cart.items
        )

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
        spice_level: Annotated[str, "Mild, Medium, Spicy, or Extra Spicy — required for any dish that takes a spice level; ask the customer if they haven't said ('no preference' = Medium)"] = "",
        note: Annotated[str, "Required modifier choices and special instructions, e.g. 'butter naan, no onions'"] = "",
    ) -> str:
        """Add one menu item to the order. Works at ANY point in the call — a
        dish added after the readback just forces a fresh readback. If the
        customer listed several dishes, call once per item in the same turn."""
        if not isinstance(quantity, int) or quantity < 1:
            quantity = 1
        quantity = min(quantity, _MAX_ITEM_QTY)

        item, refusal, kind = self._resolve_menu_item(item_query)
        if refusal:
            # PR 081 — arm the false-add-claim check for the next spoken line.
            self.state.pending_add_refusals.append(item_query)
            self._refusal_kinds[item_query] = kind or _REFUSAL_NOT_FOUND
            self._record_tool("add_item", {"item_query": item_query}, refusal)
            return refusal
        assert item is not None

        # PR 094 — per-dish spice at add time, same rule the Store enforces:
        # a dish with a Spice Level group does not enter the cart until the
        # customer has named a level.
        takes_spice = menu_provider.item_has_spice_level(item["name"])
        spice: str | None = None
        if spice_level and takes_spice:
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
        missing_groups = required if not (note or "").strip() else []
        # "One more of those" keeps the level the customer already chose — the
        # line merges by name, so asking again would be asking twice. spice
        # stays None so the merge leaves the existing note (and anything else
        # in it) untouched.
        needs_spice = (
            takes_spice and spice is None and not self._cart_line_has_spice(item["name"])
        )
        if needs_spice or missing_groups:
            # One refusal covers everything still missing, so a dish that needs
            # both a spice level and another choice costs one question, not two.
            parts: list[str] = []
            if needs_spice:
                parts.append(
                    f"NEEDS SPICE — {item['name']} comes Mild, Medium, Spicy or "
                    "Extra Spicy. Ask the customer which they want ('no "
                    "preference' = Medium), then re-call add_item with "
                    "spice_level. If other dishes in this turn also need one, "
                    "ask about them in the SAME question but NAME EACH DISH in "
                    "it, so the customer can give a different level per dish "
                    "(e.g. 'how spicy for the Chicken Biryani, and for the "
                    "Chicken Tikka Masala?'). They may answer for all of them "
                    "in one breath — map each level to the dish it was said "
                    "for, and re-call add_item once per dish with THAT dish's "
                    "level. Only a level stated for all of them (or one level "
                    "with no dish named) goes on every dish."
                )
            if missing_groups:
                groups = ", ".join(missing_groups)
                lead = "Also needs" if needs_spice else f"NEEDS INFO — {item['name']} needs"
                parts.append(
                    f"{lead} a choice for: {groups}. Ask the customer, then "
                    "re-call add_item with their choice in note."
                )
            result = _REFUSAL_PREFIX + " ".join(parts)
            # Deliberately NOT armed with pending_add_refusals: "sure, two
            # Butter Chicken — how spicy?" reads as an add claim, but the dish
            # is real and lands a turn later, and PR 081's strict correction
            # ("I don't have that on our menu") would be flat wrong here. The ⛔
            # prefix still tells the LLM the cart did not change.
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
            "GUIDE: confirm the spice change in the customer's language, "
            "warm and in your own words, then keep the order moving."
        )
        self._record_tool(
            "set_item_spice", {"item_query": item_query, "spice_level": spice}, result
        )
        return result

    def _apply_default_spice(self) -> list[str]:
        """'No preference = Medium': fill Medium on every spiced dish whose
        note still has no spice word. Deterministic, code-side — never an LLM
        guess. Returns the voice labels of the lines it filled.

        Since PR 094 add_item refuses a spiced dish with no level, this is the
        safety net for the paths that bypass that gate — web-RPC adds
        (channels/web_sync.py) above all — not the normal voice route."""
        defaulted: list[str] = []
        for line in self.cart.items:
            if not menu_provider.item_has_spice_level(line.name):
                continue
            if _SPICE_NOTE_RE.search(line.note or ""):
                continue
            line.note = _note_with_spice("Medium", line.note)
            defaulted.append(line.voice_line or line.name)
        if defaulted:
            self.cart.revision += 1
            invalidate_readback(self.state)
        return defaulted

    def _unasked_additional_requests_refusal(self) -> str | None:
        """PR 095 — the live gap: the LLM cleared the placement blocker by
        calling this tool silently, so the customer was never asked about
        allergies or special instructions. Recording an answer requires the
        question to have been SPOKEN. strict (default): refuse; warn: log +
        analytics, allow; off: rollback."""
        if self.state.additional_requests_asked:
            return None
        mode = additional_requests_verify_mode()
        if mode == "off":
            return None
        if mode == "warn":
            logger.warning("Additional-requests answer recorded without asking")
            if self._recorder is not None:
                self._recorder.add_event("additional_requests_verify_warn", {})
            return None
        # Same wording shape as the Roman-name refusal (PR 086): lead with the
        # nothing-was-saved marker, name the required next action, and forbid
        # the model from moving on — a plain "not recorded" let it carry on to
        # the read-back as if the question had been asked.
        return (
            "⛔ NOTHING WAS RECORDED — YOU HAVE NOT ASKED THE CUSTOMER ABOUT "
            "ALLERGIES OR SPECIAL INSTRUCTIONS YET. The order cannot be read "
            "back or placed until this question is actually asked out loud.\n"
            "REQUIRED NEXT ACTION: ask the ONE final additional-requests "
            "question now, in your own words in the customer's language — it "
            "must cover BOTH allergies and any special instructions for the "
            "kitchen — then call record_additional_requests again with what "
            "they answer (including 'no'). Do not move on to the read-back."
        )

    @function_tool
    async def record_additional_requests(
        self,
        response: Annotated[str, "The customer's answer to the final additional-requests question (allergies, special instructions), e.g. 'no', 'peanut allergy', 'extra napkins please'"],
    ) -> str:
        """Record the customer's answer to the ONE final additional-requests
        question (allergies + special instructions), asked once when they are
        done adding items. Spice is NOT part of this question — it is already
        settled per dish at add time. Must be called (even for 'no') before the
        order can be read back or placed. If the customer changes a spice level
        here anyway, call set_item_spice for each dish FIRST, then call this."""
        blockers = additional_requests_blockers(self.cart)
        if blockers:
            result = "Cannot record additional requests yet:\n- " + "\n- ".join(blockers)
            self._record_tool("record_additional_requests", {"response": response}, result)
            return result
        refusal = self._unasked_additional_requests_refusal()
        if refusal:
            self._record_tool(
                "record_additional_requests", {"response": response}, refusal
            )
            return refusal
        text = (response or "").strip()
        self.state.additional_requests_recorded = True
        if not text or _NO_ALLERGIES_RE.match(text):
            self.state.allergy_note = ""
            lines = ["ADDITIONAL REQUESTS RECORDED: none."]
        else:
            self.state.allergy_note = text
            lines = [f'ADDITIONAL REQUESTS RECORDED for the kitchen: "{text}".']
        defaulted = self._apply_default_spice()
        if defaulted:
            lines.append(
                "SPICE DEFAULTED: "
                + "; ".join(defaulted)
                + " set to medium (added without a level — use set_item_spice "
                "if the customer actually named one)."
            )
        lines.append(format_cart_facts(self.cart))
        lines.append(
            "GUIDE: acknowledge warmly in the customer's language, in your "
            "own words — do NOT re-ask about allergies, and never re-ask "
            "spice (it was settled per dish at add time) — then keep "
            "the order moving (pickup or delivery next if not set yet)."
        )
        result = "\n".join(lines)
        await self._sync_web()
        self._record_tool("record_additional_requests", {"response": text}, result)
        return result

    @function_tool
    async def set_order_type(
        self,
        order_type: Annotated[str, "Either 'pickup' or 'delivery'"],
    ) -> str:
        """Set whether the order is for pickup or delivery."""
        blockers = order_type_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot set pickup/delivery yet:\n- " + "\n- ".join(blockers)
            self._record_tool("set_order_type", {"order_type": order_type}, result)
            return result
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
        blockers = contact_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot collect contact details yet:\n- " + "\n- ".join(blockers)
            self._record_tool(
                "set_customer_contact", {"name": name, "phone": phone}, result
            )
            return result

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
            if not is_roman_name(clean):
                # The LLM already heard the name — it transliterates, code just
                # refuses the wrong script. Wording is load-bearing and was
                # tuned against gpt-4.1-mini: a plain "NAME NOT SAVED … write
                # it in Roman letters" made the model skip the retry and tell
                # the customer the name was saved (0/6). Leading with the ⛔
                # nothing-saved marker, naming the required next tool call, and
                # forbidding speech this turn recovers 6/6.
                result = (
                    "⛔ NOTHING WAS SAVED — THE ORDER HAS NO NAME ON IT. "
                    f'set_customer_contact rejected name="{clean}" because it '
                    "is not in English/Roman letters.\n"
                    "REQUIRED NEXT ACTION: call set_customer_contact again "
                    "immediately with name set to the Roman spelling of "
                    f'"{clean}" (examples: ਅਮਨ ਸਿੰਘ → Aman Singh, ਜਸ਼ਨ → '
                    "Jashan, राहुल → Rahul). Produce no speech in this turn. "
                    "Do not ask the customer anything — you already have the "
                    "name."
                )
                self._record_tool("set_customer_contact", {"name": name}, result)
                return result
            if self.cart.customer_name and self.cart.customer_name != clean:
                # Name appears in the spoken readback — force a fresh one.
                self.cart.revision += 1
                invalidate_readback(self.state)
            self.cart.customer_name = clean
            # A new/changed name has not been confirmed by the customer yet.
            invalidate_contact_readback(self.state)
            facts.append(f'NAME SAVED: "{clean}".')
            guides.append(
                "acknowledge briefly in the customer's language and move on — "
                "get_contact_readback reads the name back, not you."
            )
            if not self.cart.customer_phone and not (phone and phone.strip()):
                guides.append("Then ask for their phone number.")

        if phone and phone.strip():
            # PR 082 — accumulate through the same reducer as code-side custody,
            # so digits dictated across separate tool calls stitch together
            # instead of the tool replacing (and losing) prior progress.
            new_buffer, event = accumulate_phone(self.state.phone_buffer, phone)
            if event == "saved" and not is_plausible_phone(new_buffer):
                self.state.phone_buffer = ""
                facts.append(
                    f'PHONE NOT SAVED: "{phone}" does not look like a real '
                    "phone number."
                )
                guides.append(
                    "ask the customer to say their phone number again, one "
                    "digit at a time if needed."
                )
            elif event == "saved":
                self.cart.customer_phone = new_buffer
                self.state.phone_buffer = ""
                invalidate_contact_readback(self.state)
                spoken = format_phone_spoken(new_buffer)
                facts.append(f"PHONE SAVED: {spoken}.")
                guides.append(
                    "the number is already saved — do NOT ask the customer "
                    "to repeat or re-say it. Call get_contact_readback next: "
                    "it speaks the name and the number to the customer for "
                    "you, so never say either of them in your own line."
                )
            else:
                self.state.phone_buffer = new_buffer
                if new_buffer:
                    facts.append(
                        f"PHONE PARTIAL: have {len(new_buffer)} of 10 "
                        f"({new_buffer})."
                    )
                    guides.append(
                        "ask only for the REMAINING digits — do not restart, "
                        "and do not re-send digits already captured."
                    )
                else:
                    facts.append("PHONE NOT SAVED: no usable digits heard.")
                    guides.append(
                        "ask the customer to repeat the number slowly."
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
    async def get_contact_readback(self) -> str:
        """Read the customer's saved name and phone back to them for
        confirmation, right after collecting them. This SPEAKS the details
        itself. Call again after any correction to either one."""
        blockers = contact_readback_blockers(self.cart)
        if blockers:
            result = "Cannot read the contact details back yet:\n- " + "\n- ".join(
                blockers
            )
            self._record_tool("get_contact_readback", {}, result)
            return result
        # Start a fresh capture window — only the readback that follows this
        # call should be able to satisfy the confirm.
        self.state.contact_spoken.clear()
        spoken = await self._speak_contact_readback()
        result = format_contact_readback_facts(self.cart, spoken_by_code=spoken)
        self._record_tool("get_contact_readback", {}, result)
        return result

    async def _speak_contact_readback(self) -> bool:
        """PR 101 — speak the name-spelling and phone digits from code, so the
        script they are spoken in can't depend on the LLM. Returns False when
        there is no session to speak through (web RPC path, tests), where the
        LLM reads the facts out itself as before."""
        if self._session is None:
            return False
        line = contact_readback_line(
            name=self.cart.customer_name,
            phone=self.cart.customer_phone,
            language=getattr(self.state, "preferred_language", None),
        )
        try:
            # Uninterruptible, like the greeting and the goodbye: the confirm
            # gate treats this line as proof the customer heard their details,
            # so a half-spoken number must not be able to satisfy it.
            await self._session.say(line, allow_interruptions=False)
        except Exception:
            # Never lose the readback to a session hiccup — fall back to the
            # facts block and let the LLM read them, verifier still armed.
            logger.exception("Contact readback say() failed — LLM will read it")
            return False
        # Feeds the confirm-time verifier exactly like an LLM line would, so the
        # gate is satisfied by speech that is correct by construction.
        self.note_agent_speech(line)
        if self._recorder is not None:
            self._recorder.append_sierra(line)
        return True

    @function_tool
    async def confirm_contact(self) -> str:
        """Call when the customer confirms their name and phone number are
        correct — only once you have actually spoken the name and every phone
        digit to them, which this checks."""
        blockers = contact_readback_blockers(self.cart)
        if blockers:
            result = "Cannot confirm contact details:\n- " + "\n- ".join(blockers)
            self._record_tool("confirm_contact", {}, result)
            return result
        result = self._verified_contact_confirm()
        self._record_tool("confirm_contact", {}, result)
        return result

    def _verified_contact_confirm(self) -> str:
        """PR 092 — the customer can only confirm details they actually heard,
        so check the SPOKEN contact readback covers the name and every phone
        digit. strict (default): refuse and force a re-read; warn: log +
        analytics, allow; off: rollback."""
        mode = contact_verify_mode()
        if mode != "off":
            check = verify_contact_readback(
                "\n".join(self.state.contact_spoken), self.cart
            )
            if not check.ok:
                attempt = self.state.contact_verify_refusals + 1
                if mode == "strict" and attempt < _MAX_CONTACT_CONFIRM_ATTEMPTS:
                    self.state.contact_verify_refusals = attempt
                    # The buffer restarts so stale speech can't satisfy the next
                    # check; the re-read that follows is captured regardless of
                    # whether the LLM calls get_contact_readback again.
                    self.state.contact_spoken.clear()
                    return (
                        "CONTACT READBACK INCOMPLETE — the customer has not "
                        "heard their details:\n- " + "\n- ".join(check.problems)
                        + "\nRead the name and the phone number back to the "
                        "customer, then call confirm_contact again."
                    )
                if mode == "strict":
                    # PR 101 — a call must never be trapped by the verifier. The
                    # live repro looped here until the caller gave up, so the
                    # last attempt is allowed through and the gap is recorded
                    # instead of refused again.
                    logger.warning(
                        "Contact verify forced through after %d refusals: %s",
                        self.state.contact_verify_refusals,
                        check.problems,
                    )
                    if self._recorder is not None:
                        self._recorder.add_event(
                            "contact_verify_forced",
                            {
                                "problems": check.problems,
                                "refusals": self.state.contact_verify_refusals,
                            },
                        )
                else:
                    logger.warning(
                        "Contact verify (warn mode) problems: %s", check.problems
                    )
                    if self._recorder is not None:
                        self._recorder.add_event(
                            "contact_verify_warn", {"problems": check.problems}
                        )
        self.state.contact_confirmed = True
        self.state.contact_verify_refusals = 0
        return (
            "Name and phone confirmed. Continue with the order read-back "
            "(get_order_readback)."
        )

    @function_tool
    async def get_order_readback(self) -> str:
        """Get the final read-back facts for the order. Call after all
        details are collected, and again after ANY change to the order. Read
        ALL the facts back to the customer in their language, then ask if
        everything is correct."""
        blockers = readback_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot read back yet:\n- " + "\n- ".join(blockers)
            self._record_tool("get_order_readback", {}, result)
            return result
        # Safety net for spiced dishes added AFTER the additional-requests
        # step — they must never reach placement spice-unset.
        if self._apply_default_spice():
            await self._sync_web()
        result = format_readback_facts(self.cart, include_total=not self.is_phone)
        self.state.readback_revision = self.cart.revision
        self.state.readback_confirmed = False
        self.state.readback_pending = True
        self.state.readback_spoken.clear()
        self._record_tool("get_order_readback", {}, result)
        return result

    @function_tool
    async def confirm_readback(self) -> str:
        """Call when the customer confirms the read-back is correct ("yes",
        "that's right"). Must come after get_order_readback. On success this
        finalizes and places the order itself — do not call place_order
        afterward."""
        if self.state.readback_revision is None:
            result = (
                "No read-back has been given yet — call get_order_readback "
                "first and read it to the customer."
            )
            self._record_tool("confirm_readback", {}, result)
            return result
        if self.state.readback_revision != self.cart.revision:
            result = (
                "The order changed since the last read-back — call "
                "get_order_readback again and read the NEW version to the "
                "customer before confirming."
            )
            self._record_tool("confirm_readback", {}, result)
            return result
        result = self._verified_confirm()
        if self.state.readback_confirmed:
            # _finalize_order records itself under this tool_name — don't
            # double-record the same call.
            return await self._finalize_order(tool_name="confirm_readback")
        self._record_tool("confirm_readback", {}, result)
        return result

    def _verified_confirm(self) -> str:
        """PR 078 — check the SPOKEN readback covers every item/qty/order-type
        before granting confirmation. warn (default): log + analytics, allow;
        strict: refuse and force a re-read; off: rollback."""
        mode = readback_verify_mode()
        if mode != "off":
            spoken = "\n".join(self.state.readback_spoken)
            check = verify_readback(
                spoken, self.cart, check_total=not self.is_phone
            )
            for warning in check.warnings:
                logger.warning("Readback verify warning: %s", warning)
            if not check.ok:
                if mode == "strict":
                    # Keep pending so the fresh re-read is captured; the buffer
                    # restarts so stale speech can't satisfy the next check.
                    self.state.readback_spoken.clear()
                    return (
                        "READBACK INCOMPLETE — the customer has not heard the "
                        "full order:\n- " + "\n- ".join(check.problems) + "\n"
                        "Read ALL the READBACK FACTS again in the customer's "
                        "language, then ask again if everything is correct."
                    )
                logger.warning(
                    "Readback verify (warn mode) problems: %s", check.problems
                )
                if self._recorder is not None:
                    self._recorder.add_event(
                        "readback_verify_warn", {"problems": check.problems}
                    )
        self.state.readback_confirmed = True
        self.state.readback_pending = False
        # confirm_readback overrides this with the finalized-order result —
        # this string only surfaces if _verified_confirm is ever called from
        # somewhere that doesn't immediately finalize.
        return "Read-back confirmed."

    @function_tool
    async def place_order(self) -> str:
        """Finalize and place the order. Normally triggered automatically by
        confirm_readback on success — call this directly only as a fallback
        if placement needs to be retried explicitly."""
        return await self._finalize_order()

    async def _finalize_order(self, tool_name: str = "place_order") -> str:
        if self.cart.placed or self._goodbye_spoken:
            return (
                "ORDER COMPLETE — goodbye already spoken. "
                "Do NOT generate any assistant speech."
            )

        blockers = place_order_blockers(self.cart, self.state)
        if blockers:
            result = "Cannot place order:\n- " + "\n- ".join(blockers)
            self._record_tool(tool_name, {}, result)
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

        spoken = order_placed_goodbye(
            order_type=self.cart.order_type,
            language=getattr(self.state, "preferred_language", None),
        )
        self._record_tool(tool_name, {}, "placed")
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
        """Browse the menu by category or keyword — 'what X dishes do you
        have?'. For a question about ONE dish the customer named ('do you have
        gajar halwa?'), use check_menu_item instead. Never tell the customer a
        dish is unavailable unless a tool said so."""
        result = menu_provider.search_menu(query)
        self._record_tool("search_menu", {"query": query}, result)
        if self._recorder is not None and "no menu items found" in result.lower():
            self._recorder.add_event("menu_search_empty", {"query": query})
        return result

    @function_tool
    async def get_recommendations(
        self,
        preference: Annotated[str, "veg, non-veg, or any — what the customer asked for"] = "any",
        category: Annotated[str, "optional: starters, mains, breads, drinks, dessert"] = "",
    ) -> str:
        """Call whenever the customer asks what's good, wants a suggestion, or
        can't decide. Recommendations may ONLY come from this tool's results —
        never from memory."""
        result = menu_provider.get_recommendations(preference, category)
        self._record_tool(
            "get_recommendations", {"preference": preference, "category": category}, result
        )
        if self._recorder is not None and "no matching items" in result.lower():
            self._recorder.add_event(
                "recommendations_empty", {"preference": preference, "category": category}
            )
        return result

    @function_tool
    async def get_order_summary(self) -> str:
        """What is in the order so far — use when the customer asks for their
        current order mid-call. Never state the order from memory."""
        result = (
            f"{format_cart_facts(self.cart, label='ORDER SO FAR (state ONLY these items — never from memory)')}\n"
            "GUIDE: state the order conversationally in the customer's "
            "language, in your own words, using exactly these dish names and "
            "quantities (quantities as words, never digits)."
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
            "TRANSFER STARTED.\n"
            "GUIDE: tell the customer in their language, one short warm line, "
            "that you're connecting them to a staff member — then stay quiet; "
            "a human takes over."
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

        ref = record["ref"]
        ref_spoken = ", ".join(
            format_phone_spoken(ch) if ch.isdigit() else ch for ch in ref
        )
        return (
            f"RESERVATION BOOKED: table for {party_size} on {date} at {time}, "
            f"name {customer_name}. ref={ref}\n"
            "GUIDE: confirm the booking warmly in the customer's language and "
            f'give the reference spoken character by character as "{ref_spoken}" '
            "— digits ALWAYS as English words, never numerals."
        )
